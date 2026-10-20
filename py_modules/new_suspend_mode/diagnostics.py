"""Input and power diagnostics written to the plugin log."""
import os
import glob
from typing import Dict, List

from .constants import logger


class DiagnosticsMixin:
    """Input and power diagnostics written to the plugin log."""

    def _map_device_readers(self) -> Dict[str, List[str]]:
        """
        Which processes currently hold each /dev/input/event* or /dev/hidraw* open.

        This is the answer to 'how is Steam still seeing my buttons': a reader on an
        event node means the evdev path, a reader on a hidraw node means Steam is talking
        to the controller over raw HID, where no amount of evdev work can stop it.
        """
        readers: Dict[str, List[str]] = {}
        for proc_dir in glob.glob("/proc/[0-9]*"):
            pid = os.path.basename(proc_dir)
            try:
                with open(os.path.join(proc_dir, "comm"), "r") as f:
                    comm = f.read().strip()
            except Exception:
                continue
            for fd_link in glob.glob(os.path.join(proc_dir, "fd", "*")):
                try:
                    target = os.readlink(fd_link)
                except Exception:
                    continue
                if target.startswith("/dev/input/event") or target.startswith("/dev/hidraw"):
                    entry = f"{comm}({pid})"
                    if entry not in readers.setdefault(target, []):
                        readers[target].append(entry)
        return readers

    def _log_input_diagnostics(self, phase: str):
        """Dumps the full input picture to the plugin log. Enabled by the debug setting."""
        if not self.settings.get("debug_logging", True):
            return
        try:
            readers = self._map_device_readers()
            lines = [f"===== DIB INPUT DIAGNOSTICS [{phase}] ====="]

            by_comm: Dict[str, List[int]] = {}
            states: Dict[int, str] = {}
            for pid, comm, _, _ in self._iter_process_scheduling():
                by_comm.setdefault(comm.lower(), []).append(pid)
            for name in ("steam", "steamwebhelper", "gamescope", "hhd", "inputplumber"):
                pids = by_comm.get(name, [])
                shown = []
                for pid in pids[:6]:
                    try:
                        with open(f"/proc/{pid}/stat", "r") as f:
                            stat = f.read()
                        states[pid] = stat[stat.rfind(")") + 2:].split()[0]
                    except Exception:
                        states[pid] = "?"
                    shown.append(f"{pid}:{states[pid]}")
                lines.append(f"  proc {name:16} {', '.join(shown) if shown else '(not running)'}")
            lines.append("  (process state: R/S running, T stopped by us, D uninterruptible)")

            lines.append("  --- input devices (evdev) ---")
            for input_dir, event_path, name, phys in self._iter_input_devices():
                flags = []
                if self._is_power_input(name, phys):
                    flags.append("POWER-KEPT-LIVE")
                if event_path and event_path in self.power_grabbed_paths:
                    flags.append("power-grab")
                if event_path and event_path in self.grabbed_gamepad_fds:
                    flags.append("grabbed-by-us")
                seen = self.lockout_event_counts.get(event_path, 0)
                if seen:
                    flags.append(f"events-seen={seen}")
                lines.append(
                    f"  {os.path.basename(event_path) or '(no node)':11} "
                    f"inhibited={self._read_attr(input_dir, 'inhibited') or '-'} "
                    f"{' '.join(flags):34} name='{name}' phys='{phys}' "
                    f"readers={readers.get(event_path, [])}"
                )

            lines.append("  --- raw HID devices (hidraw) ---")
            for hidraw_dir in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
                node = f"/dev/{os.path.basename(hidraw_dir)}"
                hid_name = hid_id = driver = ""
                try:
                    hid_dev = os.path.realpath(os.path.join(hidraw_dir, "device"))
                    hid_id = os.path.basename(hid_dev)
                    driver_link = os.path.join(hid_dev, "driver")
                    if os.path.exists(driver_link):
                        driver = os.path.basename(os.path.realpath(driver_link))
                    with open(os.path.join(hid_dev, "uevent"), "r") as f:
                        for line in f:
                            if line.startswith("HID_NAME="):
                                hid_name = line.split("=", 1)[1].strip()
                except Exception:
                    pass
                lines.append(
                    f"  {os.path.basename(node):9} hid={hid_id:28} driver={driver:14} "
                    f"name='{hid_name}' readers={readers.get(node, [])}"
                )

            lines.append("  --- unbound by us ---")
            lines.append(f"  {self.unbound_hid_devices or '(none)'}")
            lines.append("===== END DIB INPUT DIAGNOSTICS =====")
            logger.info("\n".join(lines))
        except Exception as e:
            logger.error(f"Failed to write input diagnostics: {e}")

    def _log_power_telemetry(self):
        """One line with temperature, fan speed, APU power, CPU clock and download rate."""
        if not self.settings.get("debug_logging", True):
            return
        try:
            temps, fans, pwms = [], [], []
            for hwmon in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
                chip = self._read_attr(hwmon, "name") or os.path.basename(hwmon)
                for temp_file in sorted(glob.glob(os.path.join(hwmon, "temp*_input")))[:4]:
                    raw = self._read_attr(os.path.dirname(temp_file), os.path.basename(temp_file))
                    if raw.isdigit():
                        label = self._read_attr(hwmon, os.path.basename(temp_file).replace("_input", "_label"))
                        temps.append(f"{chip}/{label or os.path.basename(temp_file)}={int(raw) / 1000:.1f}C")
                for fan_file in sorted(glob.glob(os.path.join(hwmon, "fan*_input"))):
                    raw = self._read_attr(os.path.dirname(fan_file), os.path.basename(fan_file))
                    if raw.isdigit():
                        fans.append(f"{chip}/{os.path.basename(fan_file)}={raw}rpm")
                for pwm_file in sorted(glob.glob(os.path.join(hwmon, "pwm[0-9]"))):
                    raw = self._read_attr(os.path.dirname(pwm_file), os.path.basename(pwm_file))
                    if raw.isdigit():
                        pwms.append(f"{chip}/{os.path.basename(pwm_file)}={raw}")

            power_w = ""
            for power_file in glob.glob("/sys/class/drm/card*/device/hwmon/hwmon*/power1_average"):
                raw = self._read_attr(os.path.dirname(power_file), "power1_average")
                if raw.isdigit():
                    power_w = f"{int(raw) / 1_000_000:.2f}W"
                    break

            freqs = []
            for cpu in ("cpu0", "cpu1"):
                raw = self._read_attr(f"/sys/devices/system/cpu/{cpu}/cpufreq", "scaling_cur_freq")
                if raw.isdigit():
                    freqs.append(f"{cpu}={int(raw) / 1000:.0f}MHz")

            net_mb = self.detector.get_network_rx_rate() / (1024 * 1024)
            logger.info(
                f"[NSM TELEMETRY] net={net_mb:.2f}MB/s apu={power_w or 'n/a'} "
                f"cpu=[{' '.join(freqs) or 'n/a'}] fans=[{' '.join(fans) or 'none reported'}] "
                f"pwm=[{' '.join(pwms) or 'n/a'}] temps=[{' '.join(temps[:8]) or 'n/a'}] "
                f"quota={'on' if self.saved_cpu_quota else 'off'} "
                f"netcap={self.throttled_interfaces or 'off'}"
            )
        except Exception as e:
            logger.error(f"Failed to write telemetry: {e}")
