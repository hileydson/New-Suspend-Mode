"""Standby wake sources: what may wake the console, and the watcher listening to them."""
import os
import time
import struct
import select
import fcntl
import asyncio
from typing import List

from .constants import (
    logger,
    INPUT_EVENT_FORMAT,
    INPUT_EVENT_SIZE,
    EV_KEY,
    EVIOCGRAB,
    WAKE_COOLDOWN_SECONDS,
    POWER_KEY_GRACE_SECONDS,
    BUS_BLUETOOTH,
    WAKE_BUTTON_CODES,
    HIDRAW_LEARN_SECONDS,
)


class StandbyWakeMixin:
    """Standby wake sources: what may wake the console, and the watcher listening to them."""

    def _setup_standby_wake_sources(self):
        """
        Opens the controllers that are allowed to wake the console.

        Two ways in, because Steam Input holds controllers exclusively and an EVIOCGRAB
        can therefore fail:
          - Grabbed exclusively: we get clean button events and Steam gets nothing. Best
            case, and the device is left out of the kernel inhibit so we can keep reading.
          - Raw HID: when the grab fails, the evdev node is inhibited like everything else
            (so no button can act on the UI unseen) and the controller's hidraw reports
            are watched instead, which the inhibit does not stop.
        """
        self._teardown_standby_wake_sources()

        # The snapshot of what is already connected is taken even when button wake is
        # off: without it every pad already paired would look newly connected on the
        # first pass and wake the console immediately.
        pads = self._find_external_gamepads()
        self.standby_known_gamepads = {p["input_dir"] for p in pads}
        # Also seed the bluez baseline so a pad already connected (but, for example, not
        # yet enumerated with a js* node) does not look "newly connected" on the first
        # pass and wake the console at once.
        for address in self._bluez_connected_gamepads().keys():
            self.standby_known_gamepads.add(f"bt:{address}")
        logger.info(
            f"Standby: {len(pads)} external controller(s) present: "
            f"{[(p['name'], 'bluetooth' if p['bustype'] == BUS_BLUETOOTH else 'usb') for p in pads] or 'none'}"
        )
        if not self.settings.get("wake_on_controller_button", True):
            logger.info("Standby: wake on controller button is off; only the power button will wake.")
            return

        for pad in pads:
            event_path, name = pad["event_path"], pad["name"]
            fd = None
            try:
                fd = os.open(event_path, os.O_RDONLY | os.O_NONBLOCK)
                fcntl.ioctl(fd, EVIOCGRAB, 1)
            except Exception as e:
                if fd is not None:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
                fd = None
                logger.info(f"Standby: could not take '{name}' exclusively ({e}); falling back to raw HID.")

            if fd is not None:
                self.wake_event_fds[event_path] = fd
                self.wake_source_paths.add(event_path)
                logger.info(f"Standby wake source (exclusive input): '{name}' on {event_path}.")
                continue

            hidraw = self._hidraw_for_input(pad["input_dir"])
            if hidraw and os.path.exists(hidraw):
                try:
                    hfd = os.open(hidraw, os.O_RDONLY | os.O_NONBLOCK)
                    self.wake_hidraw_fds[hidraw] = hfd
                    self.hidraw_state[hidraw] = {
                        "baseline": None,
                        "noisy": set(),
                        "learn_until": time.time() + HIDRAW_LEARN_SECONDS,
                        "hits": 0,
                        "name": name,
                    }
                    logger.info(f"Standby wake source (raw HID): '{name}' on {hidraw}.")
                    continue
                except Exception as e:
                    logger.warning(f"Standby: could not open {hidraw} for '{name}': {e}")

            logger.warning(
                f"Standby: '{name}' cannot wake the console (not grabbable, no hidraw node). "
                "Use the power button, or connect it over Bluetooth."
            )

    def _teardown_standby_wake_sources(self):
        for path, fd in list(self.wake_event_fds.items()):
            try:
                fcntl.ioctl(fd, EVIOCGRAB, 0)
            except Exception:
                pass
            try:
                os.close(fd)
            except Exception:
                pass
        for path, fd in list(self.wake_hidraw_fds.items()):
            try:
                os.close(fd)
            except Exception:
                pass
        self.wake_event_fds.clear()
        self.wake_hidraw_fds.clear()
        self.wake_source_paths.clear()
        self.hidraw_state.clear()
        self.standby_known_gamepads.clear()

    def _hidraw_report_is_button_press(self, path: str, data: bytes) -> bool:
        """
        Decides whether a raw HID report means a button was pressed.

        Report layouts are device specific, so rather than decoding them this learns which
        bytes move on their own - sticks drift, gyros never sit still, some pads put a
        sequence counter in every report - and only a change in the quiet bytes counts.
        A pad that reports only on change says nothing during the learning window, so its
        first report afterwards is itself the press.
        """
        state = self.hidraw_state.get(path)
        if state is None or not data:
            return False

        now = time.time()
        learning = now < state["learn_until"]
        baseline = state["baseline"]

        if baseline is None:
            state["baseline"] = bytes(data)
            # Silent until now and past the learning window: this report IS the activity.
            return not learning

        changed = {i for i in range(min(len(baseline), len(data))) if baseline[i] != data[i]}
        if learning:
            state["noisy"] |= changed
            return False

        if not (changed - state["noisy"]):
            state["hits"] = 0
            return False

        state["hits"] += 1
        return state["hits"] >= 2  # Debounce: two consecutive reports showing the change

    def _standby_wake_watcher_worker(self):
        """
        Waits for a controller to ask for the console back while it sits in standby.
        Idle (and costing nothing) whenever standby is not active.
        """
        logger.info("Standby wake watcher started (idle until standby mode).")
        while not self.stop_threads:
            if not self.standby_mode or not (self.wake_event_fds or self.wake_hidraw_fds):
                time.sleep(0.5)
                continue

            event_by_fd = {fd: path for path, fd in self.wake_event_fds.items()}
            hidraw_by_fd = {fd: path for path, fd in self.wake_hidraw_fds.items()}
            try:
                rlist, _, _ = select.select(list(event_by_fd) + list(hidraw_by_fd), [], [], 0.3)
            except Exception as e:
                logger.error(f"Standby wake watcher select failed: {e}")
                time.sleep(1.0)
                continue

            in_standby_for = time.time() - self.background_mode_entered_time
            for fd in rlist:
                try:
                    if fd in event_by_fd:
                        data = os.read(fd, INPUT_EVENT_SIZE * 32)
                        pressed = None
                        while len(data) >= INPUT_EVENT_SIZE:
                            chunk, data = data[:INPUT_EVENT_SIZE], data[INPUT_EVENT_SIZE:]
                            _, _, ev_type, ev_code, ev_value = struct.unpack(INPUT_EVENT_FORMAT, chunk)
                            if ev_type == EV_KEY and ev_code in WAKE_BUTTON_CODES and ev_value == 1:
                                pressed = ev_code
                        if pressed is None:
                            continue
                        source = f"{event_by_fd[fd]} (button {pressed})"
                    else:
                        data = os.read(fd, 128)
                        if not self._hidraw_report_is_button_press(hidraw_by_fd[fd], data):
                            continue
                        source = f"{hidraw_by_fd[fd]} (raw HID activity)"
                except (BlockingIOError, OSError):
                    continue
                except Exception as e:
                    logger.error(f"Standby wake watcher read failed: {e}")
                    continue

                if in_standby_for < POWER_KEY_GRACE_SECONDS:
                    continue  # A button still held from before standby started
                logger.info(f"Controller asked for the console back: {source} -> waking.")
                self._request_wake("controller_button")
                break

    def _request_wake(self, reason: str):
        """Leaves standby from a worker thread."""
        self.wake_cooldown_until = time.time() + WAKE_COOLDOWN_SECONDS
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.exit_background_mode(reason, time.monotonic()), self.loop)

    def _newly_connected_bluetooth_gamepads(self) -> List[str]:
        """
        Bluetooth controllers that have connected since standby began.

        Checked two ways, because they catch different cases:

          * The input layer: a new /sys/class/input/input* directory with a `js*`
            symlink. Fast and exact for anything the kernel has finished enumerating.
          * Bluez over D-Bus: finds a paired controller the moment the bluez stack marks
            it as connected, even if the kernel's joystick layer has not published a
            `js*` node yet. This is the only path that catches the Sony DualSense (PS5
            controller), which the hid-playstation driver registers in a way that the
            `js*` node sometimes appears a few seconds AFTER bluez reports the connection
            and the user has already given up.
        """
        names: List[str] = []
        # Keep the original session's set: an in-flight Bluetooth query may finish
        # after teardown or after another entry created a new baseline.
        known = self.standby_known_gamepads
        for pad in self._find_external_gamepads():
            if pad["bustype"] != BUS_BLUETOOTH or pad["input_dir"] in known:
                continue
            known.add(pad["input_dir"])
            names.append(pad["name"] or pad["input_dir"])
        for address, name in self._bluez_connected_gamepads().items():
            key = f"bt:{address}"
            if key in known:
                continue
            known.add(key)
            if name not in names:
                names.append(f"{name} (bluez)")
        return names

    def _refresh_standby_wake_sources(self) -> int:
        """
        Picks up USB/dongle gamepads that connected AFTER standby began.

        Without this, a controller plugged in during the mode had no wake capability (not
        opened as a wake source) AND its input was accepted (not grabbed, not inhibited
        until the next loop pass). The exact scenario is: a dongle controller is turned
        off, then back on, Steam re-enumerates it and the kernel registers it, and in
        the window before the next pass the user's buttons act on the console.

        The lockout is extended first: a new pad is unbound/inhibited by the usual pass
        in the monitor loop a moment later anyway, but doing it here closes the window.
        """
        added = 0
        for pad in self._find_external_gamepads():
            if pad["input_dir"] in self.standby_known_gamepads:
                continue
            if pad["event_path"] in self.wake_event_fds:
                continue
            self.standby_known_gamepads.add(pad["input_dir"])

            # Try to open it as a wake source now, so a button press on it can bring the
            # console back the same way one on a controller present at entry does.
            if self.settings.get("wake_on_controller_button", True):
                event_path, name = pad["event_path"], pad["name"]
                try:
                    fd = os.open(event_path, os.O_RDONLY | os.O_NONBLOCK)
                    try:
                        fcntl.ioctl(fd, EVIOCGRAB, 1)
                        self.wake_event_fds[event_path] = fd
                        self.wake_source_paths.add(event_path)
                        added += 1
                        logger.info(f"Standby: new controller '{name}' added as a wake source.")
                        continue
                    except Exception:
                        os.close(fd)
                except Exception as e:
                    logger.info(f"Standby: new controller '{name}' could not be grabbed ({e}).")

                hidraw = self._hidraw_for_input(pad["input_dir"])
                if hidraw and os.path.exists(hidraw):
                    try:
                        hfd = os.open(hidraw, os.O_RDONLY | os.O_NONBLOCK)
                        self.wake_hidraw_fds[hidraw] = hfd
                        self.hidraw_state[hidraw] = {
                            "baseline": None, "noisy": set(),
                            "learn_until": time.time() + HIDRAW_LEARN_SECONDS,
                            "hits": 0, "name": name,
                        }
                        added += 1
                        logger.info(f"Standby: new controller '{name}' added as a raw HID wake source.")
                    except Exception as e:
                        logger.warning(f"Standby: could not open hidraw for new '{name}': {e}")
        return added
