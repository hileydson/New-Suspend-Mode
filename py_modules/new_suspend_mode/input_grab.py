"""Taking gamepad input away while the screen is off, and handing it back."""
import os
import glob
import time
import fcntl

from .constants import logger, INPUT_EVENT_SIZE, EVIOCGRAB


class InputGrabMixin:
    """Taking gamepad input away while the screen is off, and handing it back."""

    def _flush_grabbed_inputs(self):
        """
        Drains buffered events from the devices we hold, counting them.

        The count is what tells us afterwards whether a device was still producing input
        during the lockout, which is the difference between 'blocked' and 'we just never
        saw it'. It shows up in the diagnostics dump.
        """
        with self.input_lock:
            for path, fd in list(self.grabbed_gamepad_fds.items()):
                count = 0
                try:
                    while True:
                        data = os.read(fd, INPUT_EVENT_SIZE * 64)
                        if not data:
                            break
                        count += len(data) // INPUT_EVENT_SIZE
                except (BlockingIOError, OSError):
                    pass
                if count:
                    self.lockout_event_counts[path] = self.lockout_event_counts.get(path, 0) + count

    def _grab_all_gamepad_inputs(self):
        """
        Locks out every input except the physical power button.

        Four layers, in this order on purpose:
          1. External USB/Bluetooth pads are detached from their HID driver, which removes
             their hidraw node too (Steam reads pads through hidraw, where EVIOCGRAB has
             no effect). This happens BEFORE anything is frozen, because unbinding a
             device whose owning daemon is stopped can block in the kernel.
          2. The controller mapping daemons are frozen, so they stop translating presses.
          3. Every remaining evdev node is grabbed exclusively. This often fails with
             EBUSY, because Steam Input holds the controller itself, hence layer 4.
          4. The kernel is told to inhibit every input device but the power button, which
             drops events before any client gets them - including a client that already
             holds an exclusive grab. This is the layer that actually blocks the buttons.

        The built-in controller of a handheld and the virtual devices HHD/InputPlumber
        create over uhid are deliberately NOT unbound: tearing those down and rebuilding
        them crashes the session on some consoles. Inhibiting the physical device they
        read from stops them at the source instead.
        """
        self.lockout_event_counts.clear()
        deep = bool(self.settings.get("deep_input_lockout", True))

        # Whatever mode this is, the Bluetooth controllers go first: it saves their
        # battery, and in standby their reconnection is the signal to come back.
        if self._disconnect_bluetooth_controllers():
            time.sleep(0.4)  # Short settle; the disconnect already waits for the nodes

        if self.standby_mode:
            # In standby the external controllers are the way back in, so they are never
            # detached here, and they are opened as wake sources before the inhibit runs.
            if self.settings.get("wake_on_bluetooth_connect", True):
                self._ensure_bluetooth_powered()
            self._setup_standby_wake_sources()
        elif deep:
            self._unbind_external_gamepads()
        if deep:
            self._pause_controller_daemons()

        # Refresh which devices are the real power/sleep buttons: those stay untouched so
        # the hardware wake can never be blocked.
        self._power_key_candidates()
        logger.info(f"Input lockout: power devices kept free: {sorted(self.power_device_paths)}")

        self._grab_new_inputs(verbose=True)
        self._inhibit_all_inputs(verbose=True)
        self._log_input_diagnostics("after lockout")

    def _grab_new_inputs(self, verbose: bool = False):
        """
        Grabs every input device not already grabbed. Called on entry and periodically
        while the screen is off, so a controller that connects (or a virtual device that
        is recreated) mid-session is locked out too.
        """
        with self.input_lock:
            count = 0
            for path in sorted(glob.glob("/dev/input/event*")):
                if (
                    path in self.grabbed_gamepad_fds
                    or path in self.power_device_paths
                    or path in self.power_grabbed_paths
                    or path in self.wake_source_paths
                ):
                    continue
                try:
                    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                except Exception as oe:
                    if verbose:
                        logger.info(f"Input lockout: could not open {path}: {oe}")
                    continue
                try:
                    fcntl.ioctl(fd, EVIOCGRAB, 1)
                except Exception as ge:
                    os.close(fd)
                    if verbose:
                        # Usually means a controller daemon already holds it exclusively,
                        # which is fine: it is frozen and its output device is unbound.
                        logger.info(f"Input lockout: {path} ({self._get_input_name(path)}) already held: {ge}")
                    continue
                self.grabbed_gamepad_fds[path] = fd
                count += 1
            if count:
                logger.info(f"Input lockout: exclusively grabbed {count} input device(s).")
            return count

    def _get_input_name(self, path: str) -> str:
        try:
            with open(path, "rb") as f:
                name_buf = bytearray(256)
                fcntl.ioctl(f.fileno(), 0x82004506, name_buf)  # EVIOCGNAME(256)
                return name_buf.split(b"\x00")[0].decode("utf-8", errors="ignore")
        except Exception:
            return "Unknown Device"

    def _hid_provides_power_key(self, dev: str) -> bool:
        """True if an HID device also carries the power/sleep button (never unbind those)."""
        for name_file in glob.glob(os.path.join(dev, "input", "input*", "name")):
            try:
                with open(name_file, "r") as f:
                    name = f.read().strip().lower()
            except Exception:
                continue
            if "power button" in name or "sleep button" in name:
                return True
        return False

    # ASUS ROG Ally, Valve Steam Deck, Lenovo Legion Go. Their built-in controllers are
    # never unbound: on some consoles tearing the internal HID device down and probing it
    # again on wake takes the whole session (or the kernel) with it. The same goes for the
    # uhid devices HHD/InputPlumber create, whose driver teardown talks to a daemon that
    # is frozen at that moment. Freezing those daemons already silences them.
    INTERNAL_HID_VENDORS = {"0B05", "28DE", "17EF"}

    def _unbind_external_gamepads(self):
        """
        Detaches external USB/Bluetooth gamepads from their HID driver, which removes their
        evdev AND hidraw nodes, so neither Steam nor a game can read them while the screen
        is off. EVIOCGRAB alone cannot do this, because Steam talks to pads over hidraw.
        """
        # Opt-in escalation for consoles where Steam reads the built-in pad over hidraw.
        # uhid devices stay excluded either way: unbinding one while the daemon that owns
        # it is frozen is what used to take the whole session down.
        include_internal = bool(self.settings.get("block_controller_hidraw", False))

        for dev in sorted(glob.glob("/sys/bus/hid/devices/*")):
            try:
                dev_id = os.path.basename(dev)
                parts = dev_id.split(":")
                if len(parts) < 3:
                    continue
                bus, vendor = parts[0].upper(), parts[1].upper()
                if bus not in ("0003", "0005"):
                    continue  # Not a USB/Bluetooth device
                if vendor in self.INTERNAL_HID_VENDORS and not include_internal:
                    continue  # Built-in controller of a handheld
                if "uhid" in os.path.realpath(dev):
                    continue  # Virtual device from a controller daemon
                if not glob.glob(os.path.join(dev, "input", "input*", "js*")):
                    continue  # Not a gamepad/joystick
                if self._hid_provides_power_key(dev):
                    continue
                driver_link = os.path.join(dev, "driver")
                if not os.path.exists(driver_link):
                    continue
                driver = os.path.basename(os.path.realpath(driver_link))
                if self._write_sysfs(f"/sys/bus/hid/drivers/{driver}/unbind", dev_id):
                    self.unbound_hid_devices.append((driver, dev_id))
                    logger.info(f"Input lockout: unbound external pad {dev_id} from {driver}.")
                else:
                    logger.warning(f"Input lockout: failed to unbind external pad {dev_id} from {driver}.")
            except Exception as e:
                logger.warning(f"Error unbinding HID device {dev}: {e}")

    def _rebind_gamepad_hids(self):
        for driver, dev_id in list(self.unbound_hid_devices):
            ok = self._write_sysfs(f"/sys/bus/hid/drivers/{driver}/bind", dev_id)
            if not ok:
                ok = self._write_sysfs("/sys/bus/hid/drivers_probe", dev_id)
            logger.info(f"Rebound HID gamepad {dev_id} to {driver}: {'ok' if ok else 'failed'}.")
        self.unbound_hid_devices.clear()

    def _release_all_gamepad_inputs(self):
        """
        Gives input back in the order that keeps a press made during the lockout from
        acting on the console.

        A frozen controller daemon still has every button pressed during the lockout
        queued on its input fds, and replays them as soon as it runs again. So the
        daemons are thawed FIRST and given a moment to drain, which is the window the
        frontend spends dismissing any menu that replay may open (see closeSteamSideMenus
        in index.tsx). Only then are our own grabs flushed and dropped and the external
        pads rebound, so nothing is still pending by the time the user's first real press
        arrives.
        """
        was_frozen = bool(self.frozen_daemons)
        had_lockout = bool(
            self.grabbed_gamepad_fds or self.unbound_hid_devices or was_frozen or self.inhibited_inputs
        )
        if had_lockout:
            # A /proc/*/fd scan is diagnostic work, not part of handing input back.
            # Keep a cheap snapshot now; the full scan runs after games can resume.
            self.input_diagnostics_pending = True
            logger.info(
                f"Input release: grabs={len(self.grabbed_gamepad_fds)} "
                f"inhibited={len(self.inhibited_inputs)} frozen={self.frozen_daemons} "
                f"unbound={len(self.unbound_hid_devices)}"
            )

        # Standby's wake sources go first: the controller that just woke the console has
        # to answer to Steam again, not to us.
        self._teardown_standby_wake_sources()

        # 0. Let the kernel deliver events again. Done first so the console answers the
        # user's next press immediately; releases of anything held down come with it.
        self._uninhibit_all_inputs()

        # 1. Let the daemons drain their queued presses into the still-unbound virtual device.
        if was_frozen or self._controller_daemons_look_frozen():
            self._resume_controller_daemons(quiet=not had_lockout)
            time.sleep(0.4)

        # 2. Drop everything queued on our own grabs, then release them.
        released_count = len(self.grabbed_gamepad_fds)
        self._flush_grabbed_inputs()
        with self.input_lock:
            for path, fd in list(self.grabbed_gamepad_fds.items()):
                try:
                    fcntl.ioctl(fd, EVIOCGRAB, 0)
                except Exception:
                    pass
                try:
                    os.close(fd)
                except Exception:
                    pass
            self.grabbed_gamepad_fds.clear()

        # 3. Bring the controllers back, with no backlog behind them.
        self._rebind_gamepad_hids()
        if released_count > 0:
            logger.info(f"Released {released_count} input devices (controls fully restored).")
