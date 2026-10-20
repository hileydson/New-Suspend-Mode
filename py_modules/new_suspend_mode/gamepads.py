"""External gamepads and Bluetooth controllers."""
import os
import glob
import time
import re
import subprocess
import shutil
from typing import Dict, Optional, List, Tuple

from .constants import logger, BUS_USB, BUS_BLUETOOTH


class GamepadDevicesMixin:
    """External gamepads and Bluetooth controllers."""

    # ==========================================
    # Standby: console off, wakes on a controller
    # ==========================================
    def _find_external_gamepads(self) -> List[Dict[str, str]]:
        """
        Every external USB or Bluetooth controller, as candidates for waking the console.

        The built-in pad of a handheld is excluded on purpose: pressing its buttons with
        the screen off must stay dead, which is the whole point of the input lockout.
        Only the power button brings the console itself back.
        """
        found: List[Dict[str, str]] = []
        for input_dir, event_path, name, phys in self._iter_input_devices():
            if not event_path or not glob.glob(os.path.join(input_dir, "js*")):
                continue  # Not a gamepad/joystick
            id_dir = os.path.join(input_dir, "id")
            bustype = self._read_attr(id_dir, "bustype").lower()
            vendor = self._read_attr(id_dir, "vendor").upper()
            if bustype not in (BUS_USB, BUS_BLUETOOTH) or vendor in self.INTERNAL_HID_VENDORS:
                continue
            found.append({
                "input_dir": input_dir,
                "event_path": event_path,
                "name": name,
                "bustype": bustype,
                "vendor": vendor,
            })
        return found

    def _hidraw_for_input(self, input_dir: str) -> Optional[str]:
        """The /dev/hidraw* node behind an input device, if it has one."""
        try:
            probe = os.path.realpath(os.path.join(input_dir, "device"))
            for _ in range(4):
                nodes = sorted(glob.glob(os.path.join(probe, "hidraw", "hidraw*")))
                if nodes:
                    return f"/dev/{os.path.basename(nodes[0])}"
                parent = os.path.dirname(probe)
                if parent == probe:
                    break
                probe = parent
        except Exception:
            pass
        return None

    # bluez reports gamepads with one of these icons. Used to make sure a Bluetooth
    # headset or keyboard is never dropped along with the controllers.
    GAMEPAD_BT_ICONS = {"input-gaming", "input-gamepad", "input-joystick"}
    # Vendor IDs of controller makers whose Bluetooth pads sometimes register with no
    # icon at all (xpadneo-driven Xbox controllers, 8BitDo, etc.). Used as a backup
    # identifier: a connected Bluetooth device whose modalias names one of these is
    # taken as a controller even without the icon.
    GAMEPAD_BT_VENDORS = {
        "045E",  # Microsoft (Xbox One / Series)
        "054C",  # Sony (PlayStation 4 / 5)
        "057E",  # Nintendo (Switch Pro, Joy-Cons)
        "28DE",  # Valve (Steam Controller / Deck)
        "2DC8",  # 8BitDo
        "20D6",  # PowerA
        "0738",  # Mad Catz
        "0F0D",  # HORI
        "3285",  # Nacon
        "0C45",  # BigBigWon / Microdia
    }
    MAC_RE = re.compile(r"^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$")

    def _bt_adapters(self) -> List[str]:
        """Adapter names (hci0, hci1, ...) present on this machine."""
        return sorted(os.path.basename(p) for p in glob.glob("/sys/class/bluetooth/hci*"))

    def _bt_get_property(self, object_path: str, name: str) -> Optional[str]:
        """
        Reads one org.bluez device property over D-Bus.

        busctl is used instead of bluetoothctl on purpose: bluetoothctl drops into its
        interactive shell whenever it does not like an argument, and then blocks reading
        stdin until the timeout kills it. That is exactly how a disconnect can silently
        end up doing nothing, which is why the controller stayed connected.
        """
        if not shutil.which("busctl"):
            return None
        try:
            res = subprocess.run(
                ["busctl", "--no-pager", "get-property", "org.bluez", object_path,
                 "org.bluez.Device1", name],
                capture_output=True, text=True, check=False, timeout=6.0,
                stdin=subprocess.DEVNULL,
            )
        except Exception:
            return None
        if res.returncode != 0:
            return None
        # busctl prints '<signature> <value>', e.g. 'b true' or 's "input-gaming"'.
        parts = (res.stdout or "").strip().split(" ", 1)
        if len(parts) != 2:
            return None
        return parts[1].strip().strip('"')

    def _bt_object_path(self, address: str) -> Optional[str]:
        """The org.bluez object path of a remote device, found by asking each adapter."""
        node = "dev_" + address.upper().replace(":", "_")
        for hci in self._bt_adapters():
            path = f"/org/bluez/{hci}/{node}"
            if self._bt_get_property(path, "Connected") is not None:
                return path
        return None

    def _bluetooth_input_addresses(self) -> Dict[str, str]:
        """
        {address: name} for every connected Bluetooth gamepad that has an input node.

        Unlike the HID unbind path this does not filter by vendor: the built-in pad of a
        handheld is never on Bluetooth, so whatever shows up here is an external pad.
        """
        found: Dict[str, str] = {}
        have_busctl = bool(shutil.which("busctl"))
        for input_dir, _event_path, name, phys in self._iter_input_devices():
            if not glob.glob(os.path.join(input_dir, "js*")):
                continue
            if self._read_attr(os.path.join(input_dir, "id"), "bustype").lower() != BUS_BLUETOOTH:
                continue
            # Drivers disagree on which field holds the remote address and which holds
            # the adapter's, so both are tried and bluez decides which one is real.
            resolved = False
            for raw in (self._read_attr(input_dir, "uniq"), phys):
                address = (raw or "").strip().upper()
                if not self.MAC_RE.match(address):
                    continue
                if have_busctl and self._bt_object_path(address) is None:
                    continue  # The local adapter's own address, not the controller's
                found[address] = name or address
                resolved = True
                break
            if not resolved:
                logger.info(f"'{name}' is a Bluetooth gamepad but its address could not be resolved.")
        return found

    def _bluez_connected_gamepads(self) -> Dict[str, str]:
        """
        {address: name} for paired devices bluez itself reports as connected gamepads.

        Second source, for a controller whose input node does not expose its address (or
        whose evdev node Steam has already taken over). Paired devices are listed from
        bluez's own state directory and then checked over D-Bus.
        """
        found: Dict[str, str] = {}
        if not shutil.which("busctl"):
            return found
        for dev_dir in glob.glob("/var/lib/bluetooth/*/??:??:??:??:??:??"):
            address = os.path.basename(dev_dir).upper()
            if not self.MAC_RE.match(address) or address in found:
                continue
            path = self._bt_object_path(address)
            if not path or self._bt_get_property(path, "Connected") != "true":
                continue
            icon = (self._bt_get_property(path, "Icon") or "").lower()
            is_gamepad = icon in self.GAMEPAD_BT_ICONS
            if not is_gamepad:
                # Fallback: a Bluetooth device from a known controller vendor with no icon
                # (or with the wrong one - xpadneo-driven Xbox controllers sometimes do
                # this). The modalias is in `usb:vXXXXpYYYYdZZZZ` format; the four hex
                # digits after `v` are the vendor id.
                modalias = (self._bt_get_property(path, "Modalias") or "").lower()
                m = re.match(r"usb:v([0-9a-f]{4})p", modalias)
                if m and m.group(1).upper() in self.GAMEPAD_BT_VENDORS:
                    is_gamepad = True
            if is_gamepad:
                found[address] = self._bt_get_property(path, "Alias") or address
        return found

    def _bluetooth_controller_addresses(self) -> List[Tuple[str, str]]:
        """(address, name) for each connected Bluetooth controller, from both sources."""
        candidates = dict(self._bluez_connected_gamepads())
        candidates.update(self._bluetooth_input_addresses())  # Better names win
        return sorted(candidates.items())

    def _bt_disconnect(self, address: str, name: str) -> bool:
        """Disconnects one Bluetooth device: D-Bus first, bluetoothctl as a fallback."""
        path = self._bt_object_path(address)
        if path:
            try:
                res = subprocess.run(
                    ["busctl", "--no-pager", "call", "org.bluez", path,
                     "org.bluez.Device1", "Disconnect"],
                    capture_output=True, text=True, check=False, timeout=12.0,
                    stdin=subprocess.DEVNULL,
                )
                if res.returncode == 0:
                    logger.info(f"Disconnected Bluetooth controller '{name}' ({address}) over D-Bus.")
                    return True
                logger.warning(
                    f"D-Bus disconnect of '{name}' ({address}) failed: {(res.stderr or '').strip()}"
                )
            except Exception as e:
                logger.warning(f"D-Bus disconnect of '{name}' ({address}) failed: {e}")

        if not shutil.which("bluetoothctl"):
            return False
        try:
            res = subprocess.run(
                ["bluetoothctl", "disconnect", address],
                capture_output=True, text=True, check=False, timeout=12.0,
                stdin=subprocess.DEVNULL,  # Never let it block waiting on its own shell
            )
            output = f"{res.stdout or ''} {res.stderr or ''}".strip()
            if res.returncode == 0 and "fail" not in output.lower():
                logger.info(f"Disconnected Bluetooth controller '{name}' ({address}) via bluetoothctl.")
                return True
            logger.warning(f"Could not disconnect '{name}' ({address}): {output}")
        except Exception as e:
            logger.warning(f"Could not disconnect '{name}' ({address}): {e}")
        return False

    def _disconnect_bluetooth_controllers(self) -> List[str]:
        """
        Drops the connected Bluetooth controllers as the console goes dark.

        Two reasons: the pad powers itself down instead of draining its battery next to a
        console that is supposed to be off, and a controller that stays connected can
        never produce the connection event that is meant to wake the console back up.
        """
        targets = self._bluetooth_controller_addresses()
        if not targets:
            logger.info("No connected Bluetooth controller found to disconnect.")
            return []

        logger.info(f"Disconnecting Bluetooth controllers: {[f'{n} ({a})' for a, n in targets]}")
        disconnected = [name or address for address, name in targets
                        if self._bt_disconnect(address, name)]

        if disconnected:
            # Wait for the input nodes to actually go away before taking stock of what
            # is left, otherwise the lockout still sees a pad that is already gone.
            deadline = time.time() + 2.5
            while time.time() < deadline and self._bluetooth_input_addresses():
                time.sleep(0.2)
            still_there = self._bluetooth_input_addresses()
            if still_there:
                logger.warning(
                    f"Bluetooth controllers still connected after disconnect: {sorted(still_there)}"
                )
            else:
                logger.info(f"Bluetooth controllers disconnected: {', '.join(disconnected)}")
        return disconnected

    def _ensure_bluetooth_powered(self):
        """
        Leaves Bluetooth on while the console is in standby, so a controller can connect
        to it and wake it. Nothing is turned off again on wake: the adapter is left in
        the state the user normally keeps it in.
        """
        if not glob.glob("/sys/class/bluetooth/hci*"):
            logger.info("Standby: no Bluetooth adapter present; Bluetooth wake unavailable.")
            return
        for cmd in (["rfkill", "unblock", "bluetooth"], ["bluetoothctl", "power", "on"]):
            if not shutil.which(cmd[0]):
                continue
            try:
                subprocess.run(
                    cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=5.0, stdin=subprocess.DEVNULL,
                )
            except Exception as e:
                logger.warning(f"Could not run {' '.join(cmd)}: {e}")
        logger.info("Standby: Bluetooth left powered on for controller wake.")
