"""The hardware power/sleep key: finding it, grabbing it, and acting on a press."""
import os
import glob
import time
import struct
import select
import fcntl
import asyncio
from typing import Dict, Optional, List, Tuple

from .constants import (
    logger,
    INPUT_EVENT_FORMAT,
    INPUT_EVENT_SIZE,
    EV_KEY,
    KEY_POWER,
    KEY_SLEEP,
    EVIOCGRAB,
    WAKE_COOLDOWN_SECONDS,
    POWER_KEY_GRACE_SECONDS,
)


class PowerKeyMixin:
    """The hardware power/sleep key: finding it, grabbing it, and acting on a press."""

    # ==========================================
    # Hardware Power / Sleep Key Monitoring
    # ==========================================
    # ACPI buttons report a phys of 'PNP0C0C/button/input0' (power), 'PNP0C0E/...'
    # (sleep), or the LNXPWRBN/LNXSLPBN fixed-feature equivalents.
    POWER_PHYS_TAGS = ("PNP0C0C", "PNP0C0E", "LNXPWRBN", "LNXSLPBN")

    def _is_power_input(self, name: str, phys: str) -> bool:
        """
        True only for the physical power/sleep button of the machine.

        These are the devices that must keep working while every other input is locked
        out, and the only ones worth grabbing to intercept a suspend. Controllers and
        keyboards also advertise KEY_POWER, so matching on the key alone would silence
        the whole keyboard.
        """
        name_lower = (name or "").lower()
        if "power button" in name_lower or "sleep button" in name_lower:
            return True
        phys_upper = (phys or "").upper()
        return any(tag in phys_upper for tag in self.POWER_PHYS_TAGS)

    def _read_attr(self, directory: str, attr: str) -> str:
        try:
            with open(os.path.join(directory, attr), "r") as f:
                return f.read().strip()
        except Exception:
            return ""

    def _is_real_power_button(self, path: str, name: str) -> bool:
        phys = self._read_attr(f"/sys/class/input/{os.path.basename(path)}/device", "phys")
        return self._is_power_input(name, phys)

    def _iter_input_devices(self) -> List[Tuple[str, str, str, str]]:
        """(sysfs input dir, /dev/input/eventN, name, phys) for every input device."""
        devices = []
        for input_dir in sorted(glob.glob("/sys/class/input/input*")):
            event_nodes = sorted(glob.glob(os.path.join(input_dir, "event*")))
            event_path = f"/dev/input/{os.path.basename(event_nodes[0])}" if event_nodes else ""
            devices.append((
                input_dir,
                event_path,
                self._read_attr(input_dir, "name"),
                self._read_attr(input_dir, "phys"),
            ))
        return devices

    def _inhibit_all_inputs(self, verbose: bool = False) -> int:
        """
        Stops every input device except the power/sleep button at the kernel input core.

        This is the only layer that works against a client which already holds the device
        exclusively. Steam Input grabs the controller's evdev node for itself, so the
        plugin's own EVIOCGRAB returns EBUSY and every button kept working no matter how
        many devices were grabbed. Writing 1 to /sys/class/input/inputN/inhibited makes
        the kernel drop that device's events before any client sees them, grab or no grab,
        and it also closes the driver so the hardware can idle. Writing 0 undoes it, and
        the kernel emits the release events for anything held down, so no button sticks.
        """
        # Never inhibit everything without a live way back in.
        live_power = {p for p in (self.power_device_paths | self.power_grabbed_paths) if p}
        if not live_power:
            if verbose:
                logger.error(
                    "Input inhibit skipped: no power/sleep button device was identified, and "
                    "inhibiting every device without one would leave no way to wake the console."
                )
            return 0

        count = 0
        for input_dir, event_path, name, phys in self._iter_input_devices():
            if self._is_power_input(name, phys) or (event_path and event_path in live_power):
                continue
            # A controller we hold exclusively as a standby wake source must stay live:
            # inhibiting it would stop our own reads too, and nothing else can see it.
            if event_path and event_path in self.wake_source_paths:
                continue
            inhibit_file = os.path.join(input_dir, "inhibited")
            if not os.path.exists(inhibit_file):
                continue
            if self._read_attr(input_dir, "inhibited") == "1":
                continue  # Already inhibited by something else: leave it as we found it
            if self._write_sysfs(inhibit_file, "1"):
                self.inhibited_inputs.append(inhibit_file)
                count += 1
            elif verbose:
                logger.warning(f"Could not inhibit {event_path or input_dir} ('{name}').")

        # Quiet on the periodic re-sweep: only a change is worth a line.
        if count > 0:
            logger.info(
                f"Input lockout: inhibited {count} input device(s) at kernel level; "
                f"power devices left live: {sorted(live_power)}."
            )
        return count

    def _uninhibit_all_inputs(self, extra: Optional[List[str]] = None):
        for inhibit_file in list(self.inhibited_inputs) + list(extra or []):
            if os.path.exists(inhibit_file):
                self._write_sysfs(inhibit_file, "0")
        if self.inhibited_inputs:
            logger.info(f"Released kernel input inhibit on {len(self.inhibited_inputs)} device(s).")
        self.inhibited_inputs.clear()

    def _heal_stray_input_inhibits(self) -> int:
        """
        Clears any input device left inhibited by a previous run.

        An inhibited device with no plugin running means a console that answers no
        button at all, so this always runs at startup: nothing else on SteamOS inhibits
        input devices, and leaving one stuck is far worse than clearing someone else's.
        """
        healed = []
        for input_dir, event_path, name, _ in self._iter_input_devices():
            if self._read_attr(input_dir, "inhibited") != "1":
                continue
            if self._write_sysfs(os.path.join(input_dir, "inhibited"), "0"):
                healed.append(f"{os.path.basename(event_path) or input_dir} ('{name}')")
        if healed:
            logger.info(f"Startup repair: re-enabled {len(healed)} input device(s) left inhibited: {', '.join(healed)}.")
        return len(healed)

    def _find_power_sleep_devices(self) -> List[Tuple[str, str, bool]]:
        """
        Finds input devices exposing KEY_POWER or KEY_SLEEP using kernel EVIOCGBIT/EVIOCGNAME.
        Returns (path, name, is_real_power_button) for each.
        """
        devs = []
        for path in sorted(glob.glob("/dev/input/event*")):
            try:
                with open(path, "rb") as f:
                    buf = bytearray(96)
                    fcntl.ioctl(f.fileno(), 0x80604521, buf)  # EVIOCGBIT(EV_KEY, 96)
                    # KEY_POWER = 116 (byte 14, bit 4)
                    has_power = bool(buf[14] & (1 << 4))
                    # KEY_SLEEP = 142 (byte 17, bit 6)
                    has_sleep = bool(buf[17] & (1 << 6))
                    if not (has_power or has_sleep):
                        continue
                    name_buf = bytearray(256)
                    try:
                        fcntl.ioctl(f.fileno(), 0x82004506, name_buf)  # EVIOCGNAME(256)
                        name = name_buf.split(b"\x00")[0].decode("utf-8", errors="ignore")
                    except Exception:
                        name = "Unknown Device"
                devs.append((path, name, self._is_real_power_button(path, name)))
            except Exception:
                pass
        return devs

    def _power_key_candidates(self) -> List[Tuple[str, str]]:
        """The devices to grab in order to intercept the power/sleep key."""
        devices = self._find_power_sleep_devices()
        real = [(p, n) for p, n, is_real in devices if is_real]
        self.power_device_paths = {p for p, _ in real}
        if real:
            return real
        # No ACPI button (some handhelds wire power through gpio-keys or an HID device):
        # fall back to any non-keyboard device carrying the key, as before.
        return [
            (p, n) for p, n, _ in devices
            if "keyboard" not in n.lower() and "remapper" not in n.lower()
        ]

    def _power_button_listener_worker(self):
        """
        Grabs the power key only while the plugin has a reason to intercept it.

        While nothing is downloading, the device is left alone so systemd-logind and
        Steam handle the power button natively, with the stock SteamOS suspend animation.
        """
        logger.info("Power key listener worker started (idle until a download is active).")
        while not self.stop_threads:
            if not self._plugin_should_act():
                time.sleep(0.5)
                continue

            fds: Dict[str, int] = {}
            for path, name in self._power_key_candidates():
                try:
                    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                except Exception as e:
                    logger.debug(f"Could not open power device {path}: {e}")
                    continue
                try:
                    # EVIOCGRAB: grab exclusively so logind and Steam never see this press
                    # and the plugin decides what it means (intercept suspend, or wake).
                    fcntl.ioctl(fd, EVIOCGRAB, 1)
                except Exception as ge:
                    os.close(fd)
                    logger.warning(f"Could not grab power device {name} ({path}): {ge}")
                    continue
                fds[path] = fd
                logger.info(f"Exclusively grabbed power device: {name} ({path})")

            if not fds:
                logger.warning("No power/sleep key device could be grabbed; retrying shortly.")
                time.sleep(2.0)
                continue

            self.power_grabbed_paths = set(fds)
            try:
                while not self.stop_threads and self._plugin_should_act():
                    rlist, _, _ = select.select(list(fds.values()), [], [], 0.3)
                    for fd in rlist:
                        try:
                            data = os.read(fd, INPUT_EVENT_SIZE * 16)
                            while len(data) >= INPUT_EVENT_SIZE:
                                chunk = data[:INPUT_EVENT_SIZE]
                                data = data[INPUT_EVENT_SIZE:]
                                _, _, ev_type, ev_code, ev_value = struct.unpack(INPUT_EVENT_FORMAT, chunk)

                                if ev_type == EV_KEY and ev_code in (KEY_POWER, KEY_SLEEP) and ev_value == 1:
                                    logger.info(f"Hardware power key intercepted (code={ev_code}).")
                                    self._on_hardware_power_key()
                        except BlockingIOError:
                            pass
                        except Exception as e:
                            logger.error(f"Error reading hardware key event: {e}")
                            break
            except Exception as e:
                # Never let the thread die: without it the power button would stop
                # working as a wake trigger for the rest of the session.
                logger.error(f"Power key listener loop failed, restarting it: {e}")
                time.sleep(1.0)
            finally:
                for fd in fds.values():
                    try:
                        fcntl.ioctl(fd, EVIOCGRAB, 0)
                    except Exception:
                        pass
                    try:
                        os.close(fd)
                    except Exception:
                        pass
                self.power_grabbed_paths = set()
                logger.info("Released power key device(s); SteamOS handles the power button again.")

    def _on_hardware_power_key(self):
        if not self._effective_enabled(max_age=0.0):
            return

        now = time.time()
        # Cooldown check: ignore power button press if system just woke up within 12 seconds
        if now < self.wake_cooldown_until or self.transition_in_progress or self.wake_presentation_active:
            logger.info("Ignoring power key because system just woke up.")
            return

        time_in_bg = (now - self.background_mode_entered_time) if self.is_background_mode else 999.0
        if self.is_background_mode:
            # Grace period: ignore initial power key bounce/release right when entering mode
            if time_in_bg < POWER_KEY_GRACE_SECONDS:
                logger.info(f"Ignoring power key in background mode entry grace period ({time_in_bg:.1f}s).")
                return
            logger.info("Power button pressed during background mode -> Full system wake!")
            self.wake_cooldown_until = now + WAKE_COOLDOWN_SECONDS
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.exit_background_mode("power_button_wake", time.monotonic()),
                    self.loop
                )
            return

        # Read the download state right now instead of trusting the last poll: the user
        # may have paused it a second ago and pressed power straight after.
        is_active_dl = self._refresh_download_state()
        if not is_active_dl and not self.download_info.get("is_paused", False):
            # Nothing known and nothing says paused: a download that started seconds ago
            # may not be in a manifest yet, so only a strong sustained rate counts here.
            is_active_dl = self.detector.get_network_rx_rate() > 300000

        if is_active_dl:
            self._trigger_suspend_intercepted("power_button")
            return

        if self.settings.get("standby_on_power_off", False):
            logger.info("Power key pressed with standby enabled -> showing standby splash, then entering.")
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.request_standby("standby_power_off"), self.loop
                )
            return

        logger.info("Power key pressed with no active downloads (paused/idle) -> Allowing normal suspend.")
        self._release_sleep_inhibitor()
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.trigger_suspend(), self.loop)

    def _get_session_user(self) -> str:
        for uid in [1000, 1001]:
            try:
                import pwd
                return pwd.getpwuid(uid).pw_name
            except Exception:
                pass
        return "deck"
