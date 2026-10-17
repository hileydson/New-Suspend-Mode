import os
import sys
import json
import glob
import time
import struct
import select
import fcntl
import re
import asyncio
import logging
import threading
import subprocess
from typing import Dict, Any, Optional, List, Set

# Setup Decky compatibility
try:
    import decky
except ImportError:
    # Dummy mock for standalone linting / local testing outside Decky
    class DummyDecky:
        DECKY_PLUGIN_SETTINGS_DIR = os.path.expanduser("~/.config/DownloadInBackground")
        DECKY_PLUGIN_LOG_DIR = os.path.expanduser("~/.config/DownloadInBackground/logs")
        DECKY_USER_HOME = os.path.expanduser("~")
        DECKY_HOME = os.path.expanduser("~/homebrew")
        logger = logging.getLogger("DownloadInBackground")
        @staticmethod
        async def emit(event_name: str, *args):
            pass
    decky = DummyDecky()

logging.basicConfig(level=logging.INFO)
logger = decky.logger

DEFAULT_SETTINGS: Dict[str, Any] = {
    "enabled": True,
    "min_battery_threshold": 15,
    "hud_timeout_seconds": 5,
    "auto_suspend_delay_seconds": 15,
    "throttle_cpu": True,
    "throttle_gpu": True,
    "mute_audio": True,
    "turn_off_backlight": True,
    "oled_black_screen": True,
}

INPUT_EVENT_FORMAT = "qqHHi"
INPUT_EVENT_SIZE = struct.calcsize(INPUT_EVENT_FORMAT)
EV_KEY = 1
KEY_POWER = 116
KEY_SLEEP = 142


class SteamDownloadDetector:
    """
    Natively inspects Steam library folders, appmanifest files, and network traffic
    to detect downloads with 100% reliability without relying on CEF JavaScript.
    """
    def __init__(self):
        self.cached_libraries: List[str] = []
        self.last_lib_scan: float = 0
        self.last_net_bytes: int = 0
        self.last_net_time: float = time.time()
        self.last_completed_bytes: int = 0
        self.last_dl_calc_time: float = time.time()

    def get_library_paths(self) -> List[str]:
        now = time.time()
        if self.cached_libraries and (now - self.last_lib_scan) < 20:
            return self.cached_libraries

        libs: Set[str] = set()

        # Check decky.DECKY_USER_HOME, /home/* and ~
        candidate_homes = glob.glob("/home/*") + [decky.DECKY_USER_HOME, os.path.expanduser("~")]
        for ch in candidate_homes:
            if not ch or not os.path.isdir(ch):
                continue
            for rel in [".local/share/Steam", ".steam/steam", ".steam/root"]:
                steam_base = os.path.join(ch, rel)
                sa = os.path.join(steam_base, "steamapps")
                if os.path.isdir(sa):
                    libs.add(sa)
                    vdf_file = os.path.join(sa, "libraryfolders.vdf")
                    if os.path.isfile(vdf_file):
                        try:
                            with open(vdf_file, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                            matches = re.findall(r"\"path\"\s*\"([^\"]+)\"", content)
                            for m in matches:
                                extra_sa = os.path.join(m, "steamapps")
                                if os.path.isdir(extra_sa):
                                    libs.add(extra_sa)
                        except Exception:
                            pass

        # Check removable media (SD Card, second NVMe partition, USB)
        for rem in glob.glob("/run/media/*/*") + glob.glob("/media/*/*") + glob.glob("/mnt/*"):
            sa = os.path.join(rem, "steamapps")
            if os.path.isdir(sa):
                libs.add(sa)

        self.cached_libraries = list(libs)
        self.last_lib_scan = now
        return self.cached_libraries

    def get_network_rx_rate(self) -> float:
        """Reads real received bytes per second across all non-lo network interfaces."""
        curr_bytes = 0
        try:
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()[2:]
            for line in lines:
                parts = line.split(":")
                if len(parts) == 2 and parts[0].strip() != "lo":
                    vals = parts[1].split()
                    if vals:
                        curr_bytes += int(vals[0])
        except Exception:
            pass

        now = time.time()
        dt = max(0.1, now - self.last_net_time)
        bps = 0.0
        if self.last_net_bytes > 0 and curr_bytes >= self.last_net_bytes:
            bps = (curr_bytes - self.last_net_bytes) / dt

        self.last_net_bytes = curr_bytes
        self.last_net_time = now
        return bps

    def _has_recent_download_writes(self, libs: List[str], max_age_seconds: float = 6.0) -> bool:
        """Checks if files in steamapps/downloading/ were modified within max_age_seconds."""
        now = time.time()
        for sa in libs:
            dl_dir = os.path.join(sa, "downloading")
            if not os.path.isdir(dl_dir):
                continue
            try:
                count = 0
                for root, dirs, files in os.walk(dl_dir):
                    for fname in files:
                        count += 1
                        if count > 60:
                            break
                        fpath = os.path.join(root, fname)
                        try:
                            if (now - os.path.getmtime(fpath)) <= max_age_seconds:
                                return True
                        except OSError:
                            pass
                    if count > 60:
                        break
            except Exception:
                pass
        return False

    def detect(self) -> Dict[str, Any]:
        libs = self.get_library_paths()
        active_candidates: List[Dict[str, Any]] = []
        paused_candidates: List[Dict[str, Any]] = []

        # Check appmanifest files in all libraries
        for sa in libs:
            manifests = glob.glob(os.path.join(sa, "appmanifest_*.acf"))
            for mf in manifests:
                try:
                    with open(mf, "r", encoding="utf-8", errors="ignore") as f:
                        txt = f.read()

                    state_m = re.search(r"\"StateFlags\"\s*\"(\d+)\"", txt)
                    if not state_m:
                        continue
                    state = int(state_m.group(1))

                    name_m = re.search(r"\"name\"\s*\"([^\"]+)\"", txt)
                    dl_m = re.search(r"\"BytesDownloaded\"\s*\"(\d+)\"", txt)
                    tot_m = re.search(r"\"BytesToDownload\"\s*\"(\d+)\"", txt)

                    name = name_m.group(1) if name_m else "Steam Download"
                    b_dl = int(dl_m.group(1)) if dl_m else 0
                    b_tot = int(tot_m.group(1)) if tot_m else 0
                    pct = (b_dl / b_tot * 100) if b_tot > 0 else 0

                    cand = {
                        "game_title": name,
                        "completed_bytes": b_dl,
                        "total_bytes": b_tot,
                        "progress_percent": pct,
                    }

                    # StateFlags:
                    # 512 = StateUpdatePaused
                    # 1048576 = StateUpdateStopping
                    # 1024 = StateUpdateStarted, 256 = StateUpdateRunning, 131072 = StateDownloading, 262144 = StateStaging, 65536 = StatePreallocating
                    is_paused = bool(state & 512)
                    is_stopping = bool(state & 1048576)
                    is_updating = bool((state & 1024) or (state & 256) or (state & 131072) or (state & 262144) or (state & 65536))

                    if is_paused or is_stopping:
                        paused_candidates.append(cand)
                    elif is_updating:
                        active_candidates.append(cand)
                except Exception:
                    pass

        net_bps = self.get_network_rx_rate()
        has_recent_writes = self._has_recent_download_writes(libs, max_age_seconds=6.0)

        # Case 1: Active updating candidate in manifests
        if active_candidates:
            active_dl = active_candidates[0]
            # Verify network is actually flowing or disk is actively being written
            if net_bps > 15000 or has_recent_writes:
                active_dl["is_downloading"] = True
                active_dl["is_paused"] = False
                active_dl["bytes_per_second"] = net_bps
                if net_bps > 0 and active_dl["total_bytes"] > active_dl["completed_bytes"]:
                    rem_bytes = active_dl["total_bytes"] - active_dl["completed_bytes"]
                    active_dl["estimated_seconds_remaining"] = int(rem_bytes / net_bps)
                else:
                    active_dl["estimated_seconds_remaining"] = 0
                return active_dl

        # Case 2: No active downloads, but games are paused in download queue
        if paused_candidates and not has_recent_writes and net_bps < 30000:
            paused_dl = paused_candidates[0]
            return {
                "is_downloading": False,
                "is_paused": True,
                "game_title": paused_dl["game_title"],
                "completed_bytes": paused_dl["completed_bytes"],
                "total_bytes": paused_dl["total_bytes"],
                "progress_percent": paused_dl["progress_percent"],
                "bytes_per_second": 0,
                "estimated_seconds_remaining": 0,
            }

        # Case 3: High network traffic + active file writes (fallback for unmanifested downloads)
        if net_bps > 50000 and has_recent_writes:
            return {
                "is_downloading": True,
                "is_paused": False,
                "game_title": "Steam Game Download",
                "bytes_per_second": net_bps,
                "completed_bytes": 0,
                "total_bytes": 0,
                "progress_percent": 0,
                "estimated_seconds_remaining": 0,
            }

        # Case 4: Completely idle or paused
        return {
            "is_downloading": False,
            "is_paused": bool(paused_candidates),
            "game_title": paused_candidates[0]["game_title"] if paused_candidates else "",
            "bytes_per_second": net_bps,
            "completed_bytes": 0,
            "total_bytes": 0,
            "progress_percent": 0,
            "estimated_seconds_remaining": 0,
        }


class Plugin:
    def __init__(self):
        self.settings: Dict[str, Any] = DEFAULT_SETTINGS.copy()
        self.settings_file: str = ""
        self.is_background_mode: bool = False
        self.saved_brightness: Dict[str, int] = {}
        self.saved_power_profile: Optional[str] = None
        self.saved_cpu_governors: Dict[str, str] = {}
        self.saved_gpu_dpm: Optional[str] = None

        self.inhibitor_proc: Optional[subprocess.Popen] = None
        self.power_button_thread: Optional[threading.Thread] = None
        self.logind_watcher_thread: Optional[threading.Thread] = None
        self.stop_threads: bool = False

        self.detector = SteamDownloadDetector()
        self.download_info: Dict[str, Any] = {
            "is_downloading": False,
            "is_paused": False,
            "bytes_per_second": 0,
            "progress_percent": 0,
            "game_title": "",
            "total_bytes": 0,
            "completed_bytes": 0,
            "estimated_seconds_remaining": 0,
        }
        self.last_download_active_time: float = time.time()
        self.last_suspend_intercept_time: float = 0
        self.wake_cooldown_until: float = 0.0
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.monitor_task: Optional[asyncio.Task] = None

    # ==========================================
    # Lifecycle Hooks
    # ==========================================
    async def _migration(self):
        try:
            os.makedirs(decky.DECKY_PLUGIN_SETTINGS_DIR, exist_ok=True)
            self.settings_file = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "settings.json")
            self._load_settings()
        except Exception as e:
            logger.error(f"Error during migration: {e}")

    async def _main(self):
        self.loop = asyncio.get_running_loop()
        self.settings_file = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "settings.json")
        self._load_settings()
        self.stop_threads = False

        logger.info("Download in Background plugin started.")

        # 1. Hardware Power Button Listener Thread
        self.power_button_thread = threading.Thread(
            target=self._power_button_listener_worker,
            daemon=True,
            name="DownloadInBackground-PowerButton"
        )
        self.power_button_thread.start()

        # 2. Systemd Logind Journal Watcher Thread (catches UI suspend requests)
        self.logind_watcher_thread = threading.Thread(
            target=self._logind_watcher_worker,
            daemon=True,
            name="DownloadInBackground-LogindWatcher"
        )
        self.logind_watcher_thread.start()

        # 3. Main periodic monitor loop
        self.monitor_task = self.loop.create_task(self._background_monitor_loop())

    async def _unload(self):
        logger.info("Unloading Download in Background plugin...")
        self.stop_threads = True

        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()

        if self.is_background_mode:
            self._restore_system_power_and_display()

        self._release_sleep_inhibitor()

    async def _uninstall(self):
        await self._unload()
        try:
            if os.path.exists(self.settings_file):
                os.remove(self.settings_file)
        except Exception as e:
            logger.error(f"Error cleaning settings: {e}")

    # ==========================================
    # Settings Management
    # ==========================================
    def _load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.settings.update(data)
            else:
                self._save_settings_sync()
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")

    def _save_settings_sync(self):
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    async def get_settings(self) -> Dict[str, Any]:
        return self.settings

    async def save_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        self.settings.update(new_settings)
        self._save_settings_sync()
        logger.info(f"Updated settings: {self.settings}")

        if not self.settings.get("enabled", True):
            if self.is_background_mode:
                await self.exit_background_mode("disabled_in_settings")
            self._release_sleep_inhibitor()
        else:
            self._update_inhibitor_state()

        return self.settings

    # ==========================================
    # Battery & Hardware Status Queries
    # ==========================================
    def _get_battery_info(self) -> Dict[str, Any]:
        capacity = 100
        is_charging = False
        is_plugged = False

        ac_paths = glob.glob("/sys/class/power_supply/AC*") + glob.glob("/sys/class/power_supply/ucsi-source-psy*")
        for p in ac_paths:
            online_file = os.path.join(p, "online")
            if os.path.exists(online_file):
                try:
                    with open(online_file, "r") as f:
                        if f.read().strip() == "1":
                            is_plugged = True
                            break
                except Exception:
                    pass

        bat_paths = glob.glob("/sys/class/power_supply/BAT*")
        for p in bat_paths:
            cap_file = os.path.join(p, "capacity")
            stat_file = os.path.join(p, "status")
            if os.path.exists(cap_file):
                try:
                    with open(cap_file, "r") as f:
                        capacity = int(f.read().strip())
                except Exception:
                    pass
            if os.path.exists(stat_file):
                try:
                    with open(stat_file, "r") as f:
                        status = f.read().strip().lower()
                        if "charging" in status or "full" in status:
                            is_charging = True
                except Exception:
                    pass
            break

        return {
            "capacity": capacity,
            "is_charging": is_charging,
            "is_plugged": is_plugged or is_charging,
        }

    async def get_status(self) -> Dict[str, Any]:
        bat = self._get_battery_info()
        return {
            "is_background_mode": self.is_background_mode,
            "battery_capacity": bat["capacity"],
            "is_charging": bat["is_charging"],
            "power_plugged": bat["is_plugged"],
            "inhibitor_active": self.inhibitor_proc is not None,
            "settings": self.settings,
            "download_info": self.download_info,
        }

    async def update_download_status(self, info: Dict[str, Any]) -> bool:
        """Receives real-time SteamClient download updates from frontend."""
        if not isinstance(info, dict):
            return False

        is_dl = bool(info.get("is_downloading", False))
        is_paused = bool(info.get("is_paused", False))

        self.download_info.update(info)
        self.download_info["is_downloading"] = is_dl and not is_paused
        self.download_info["is_paused"] = is_paused

        if self.download_info["is_downloading"]:
            self.last_download_active_time = time.time()

        self._update_inhibitor_state()
        return True

    # ==========================================
    # Systemd Inhibitor Control
    # ==========================================
    def _acquire_sleep_inhibitor(self):
        if self.inhibitor_proc is not None:
            return

        cmd = [
            "systemd-inhibit",
            "--what=sleep:handle-power-key:handle-suspend-key",
            "--who=DownloadInBackground",
            "--why=Steam game download active in background",
            "--mode=block",
            "cat",
        ]
        try:
            self.inhibitor_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Acquired sleep inhibitor lock (block mode).")
        except Exception as e:
            logger.error(f"Failed to acquire sleep inhibitor: {e}")
            self.inhibitor_proc = None

    def _release_sleep_inhibitor(self):
        if self.inhibitor_proc is not None:
            try:
                self.inhibitor_proc.terminate()
                self.inhibitor_proc.wait(timeout=1.0)
            except Exception:
                try:
                    self.inhibitor_proc.kill()
                except Exception:
                    pass
            self.inhibitor_proc = None
            logger.info("Released sleep inhibitor lock.")

    def _update_inhibitor_state(self):
        if not self.settings.get("enabled", True):
            self._release_sleep_inhibitor()
            return

        is_active_download = (
            self.download_info.get("is_downloading", False)
            and not self.download_info.get("is_paused", False)
        )
        should_inhibit = self.is_background_mode or is_active_download
        if should_inhibit and self.inhibitor_proc is None:
            self._acquire_sleep_inhibitor()
        elif not should_inhibit and self.inhibitor_proc is not None:
            self._release_sleep_inhibitor()

    # ==========================================
    # Suspend Interception & Logind Watcher
    # ==========================================
    def _trigger_suspend_intercepted(self):
        """Called whenever a suspend attempt is detected while downloads are active."""
        now = time.time()
        # Cooldown: Ignore any suspend request if system just woke up within 5 seconds
        if now < self.wake_cooldown_until:
            logger.info("Ignoring suspend attempt because system just woke up from background mode.")
            return

        # Double check: Is download REALLY actively downloading (not paused or idle)?
        is_active_dl = (
            self.download_info.get("is_downloading", False)
            and not self.download_info.get("is_paused", False)
        )
        if not is_active_dl:
            logger.info("Suspend attempt not intercepted: Download is paused or idle. Allowing normal suspend.")
            self._release_sleep_inhibitor()
            return

        # Debounce to prevent double trigger within 3 seconds
        if now - self.last_suspend_intercept_time < 3.0:
            return
        self.last_suspend_intercept_time = now

        logger.info("Suspend attempt intercepted while downloading -> Showing HUD!")
        self._acquire_sleep_inhibitor()

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                decky.emit("on_suspend_intercepted", {
                    "download_info": self.download_info,
                    "hud_timeout": self.settings.get("hud_timeout_seconds", 5),
                }),
                self.loop
            )

    def _logind_watcher_worker(self):
        """Watches systemd-logind journal logs to intercept UI suspend clicks."""
        logger.info("Starting logind journal watcher worker...")
        while not self.stop_threads:
            proc = None
            try:
                cmd = ["journalctl", "-u", "systemd-logind", "-f", "-n", "0", "-o", "cat"]
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1
                )

                while not self.stop_threads and proc.poll() is None:
                    line = proc.stdout.readline()
                    if not line:
                        break

                    # Ignore logind events during wake cooldown
                    if time.time() < self.wake_cooldown_until:
                        continue

                    lower = line.lower()
                    if (
                        "inhibited by downloadinbackground" in lower
                        or "refusing operation" in lower
                        or "power key pressed to suspend" in lower
                        or "suspend key pressed to sleep" in lower
                        or "suspend entry requested" in lower
                    ):
                        logger.info(f"Logind journal suspend event: {line.strip()}")
                        is_active_dl = (
                            self.download_info.get("is_downloading", False)
                            and not self.download_info.get("is_paused", False)
                        )
                        if is_active_dl:
                            self._trigger_suspend_intercepted()
                        else:
                            self._release_sleep_inhibitor()

            except Exception as e:
                logger.error(f"Error in logind watcher: {e}")
            finally:
                if proc:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                time.sleep(2.0)

    # ==========================================
    # Hardware Power / Sleep Key Monitoring
    # ==========================================
    def _find_power_sleep_devices(self) -> List[str]:
        """Finds all input devices with KEY_POWER or KEY_SLEEP using kernel EVIOCGBIT."""
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
                    if has_power or has_sleep:
                        devs.append(path)
            except Exception:
                pass
        return devs

    def _power_button_listener_worker(self):
        logger.info("Starting hardware power key listener worker...")
        while not self.stop_threads:
            device_paths = self._find_power_sleep_devices()
            if not device_paths:
                time.sleep(3.0)
                continue

            fds = []
            for path in device_paths:
                try:
                    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                    fds.append(fd)
                except Exception:
                    pass

            if not fds:
                time.sleep(3.0)
                continue

            try:
                while not self.stop_threads:
                    rlist, _, _ = select.select(fds, [], [], 1.0)
                    for fd in rlist:
                        try:
                            data = os.read(fd, INPUT_EVENT_SIZE * 16)
                            while len(data) >= INPUT_EVENT_SIZE:
                                chunk = data[:INPUT_EVENT_SIZE]
                                data = data[INPUT_EVENT_SIZE:]
                                _, _, ev_type, ev_code, ev_value = struct.unpack(INPUT_EVENT_FORMAT, chunk)

                                if ev_type == EV_KEY and (ev_code == KEY_POWER or ev_code == KEY_SLEEP) and ev_value == 1:
                                    logger.info(f"Hardware key event: code={ev_code}")
                                    self._on_hardware_power_key()
                        except BlockingIOError:
                            pass
                        except Exception as e:
                            logger.error(f"Error reading hardware key event: {e}")
                            break
            finally:
                for fd in fds:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
                time.sleep(1.0)

    def _on_hardware_power_key(self):
        if not self.settings.get("enabled", True):
            return

        # Cooldown check: ignore power button press if system just woke up within 5 seconds
        if time.time() < self.wake_cooldown_until:
            logger.info("Ignoring power key because system just woke up.")
            return

        if self.is_background_mode:
            logger.info("Power button pressed during background mode -> Full system wake to SteamOS Home!")
            self.wake_cooldown_until = time.time() + 5.0
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.exit_background_mode("power_button_wake"),
                    self.loop
                )
            return

        is_active_dl = (
            self.download_info.get("is_downloading", False)
            and not self.download_info.get("is_paused", False)
        )
        if is_active_dl:
            self._trigger_suspend_intercepted()
        else:
            logger.info("Power key pressed with no active downloads (paused/idle) -> Allowing normal suspend.")
            self._release_sleep_inhibitor()
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self.trigger_suspend(), self.loop)

    # ==========================================
    # Power Saving & Screen Control
    # ==========================================
    def _apply_power_saving_and_screen_off(self):
        # 1. Turn off backlight: prioritize amdgpu_bl* on ROG Ally / Steam Deck
        if self.settings.get("turn_off_backlight", True):
            backlight_dirs = glob.glob("/sys/class/backlight/*")
            # Sort amdgpu_bl first
            backlight_dirs.sort(key=lambda p: 0 if "amdgpu" in p else 1)

            for bdir in backlight_dirs:
                brightness_path = os.path.join(bdir, "brightness")
                if os.path.exists(brightness_path):
                    try:
                        with open(brightness_path, "r") as f:
                            curr_b = int(f.read().strip())
                        self.saved_brightness[brightness_path] = curr_b
                        with open(brightness_path, "w") as f:
                            f.write("0")
                        logger.info(f"Set backlight {brightness_path} from {curr_b} to 0.")
                    except Exception as e:
                        logger.error(f"Failed to turn off backlight on {brightness_path}: {e}")

            # Also try brightnessctl if installed
            try:
                subprocess.run(["brightnessctl", "set", "0%"], capture_output=True, check=False)
            except Exception:
                pass

        # 2. CPU governor / Power profile
        if self.settings.get("throttle_cpu", True):
            try:
                res = subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True, check=False)
                if res.returncode == 0:
                    self.saved_power_profile = res.stdout.strip()
                    subprocess.run(["powerprofilesctl", "set", "power-saver"], check=False)
            except Exception:
                pass

            gov_paths = glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor")
            for gp in gov_paths:
                try:
                    with open(gp, "r") as f:
                        curr_gov = f.read().strip()
                    self.saved_cpu_governors[gp] = curr_gov
                    with open(gp, "w") as f:
                        f.write("powersave")
                except Exception:
                    pass

        # 3. AMD GPU DPM clock level
        if self.settings.get("throttle_gpu", True):
            dpm_path = "/sys/class/drm/card0/device/power_dpm_force_performance_level"
            if os.path.exists(dpm_path):
                try:
                    with open(dpm_path, "r") as f:
                        curr_dpm = f.read().strip()
                    self.saved_gpu_dpm = curr_dpm
                    with open(dpm_path, "w") as f:
                        f.write("low")
                except Exception:
                    pass

        # 4. Mute Audio
        if self.settings.get("mute_audio", True):
            try:
                subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1"], check=False)
                subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"], check=False)
            except Exception:
                pass

    def _restore_system_power_and_display(self):
        logger.info("Restoring system power and display settings...")

        # 1. Restore Backlight
        for brightness_path, val in self.saved_brightness.items():
            try:
                if os.path.exists(brightness_path):
                    with open(brightness_path, "w") as f:
                        f.write(str(max(val, 25)))
            except Exception:
                pass
        self.saved_brightness.clear()

        # Fallback restore via brightnessctl if needed
        try:
            subprocess.run(["brightnessctl", "set", "50%"], capture_output=True, check=False)
        except Exception:
            pass

        # 2. Restore Power Profile / CPU Governor
        if self.saved_power_profile:
            try:
                subprocess.run(["powerprofilesctl", "set", self.saved_power_profile], check=False)
            except Exception:
                pass
            self.saved_power_profile = None

        for gp, gov in self.saved_cpu_governors.items():
            try:
                if os.path.exists(gp):
                    with open(gp, "w") as f:
                        f.write(gov)
            except Exception:
                pass
        self.saved_cpu_governors.clear()

        # 3. Restore GPU DPM
        if self.saved_gpu_dpm:
            dpm_path = "/sys/class/drm/card0/device/power_dpm_force_performance_level"
            try:
                if os.path.exists(dpm_path):
                    with open(dpm_path, "w") as f:
                        f.write(self.saved_gpu_dpm)
            except Exception:
                pass
            self.saved_gpu_dpm = None

        # 4. Unmute Audio
        try:
            subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"], check=False)
            subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], check=False)
        except Exception:
            pass

    # ==========================================
    # Background Mode Transitions & Peek Feature
    # ==========================================
    async def peek_display_on(self) -> bool:
        """Temporarily turns backlight on so user can peek at download HUD without restoring full power."""
        logger.info("Peeking display on...")
        for brightness_path, val in self.saved_brightness.items():
            try:
                if os.path.exists(brightness_path):
                    with open(brightness_path, "w") as f:
                        f.write(str(max(val, 25)))
            except Exception:
                pass
        try:
            subprocess.run(["brightnessctl", "set", "50%"], capture_output=True, check=False)
        except Exception:
            pass
        return True

    async def peek_display_off(self) -> bool:
        """Turns backlight back off to 0 after peeking."""
        logger.info("Peeking display off...")
        if self.is_background_mode and self.settings.get("turn_off_backlight", True):
            for brightness_path in self.saved_brightness.keys():
                if os.path.exists(brightness_path):
                    try:
                        with open(brightness_path, "w") as f:
                            f.write("0")
                    except Exception:
                        pass
            try:
                subprocess.run(["brightnessctl", "set", "0%"], capture_output=True, check=False)
            except Exception:
                pass
        return True

    def _navigate_steam_home(self):
        """Forces SteamOS to show the Home Screen."""
        try:
            user = "deck"
            if hasattr(decky, "DECKY_USER_HOME") and decky.DECKY_USER_HOME:
                parts = decky.DECKY_USER_HOME.strip("/").split("/")
                if len(parts) >= 2 and parts[0] == "home":
                    user = parts[1]

            logger.info(f"Navigating Steam to Home screen for user {user}...")
            subprocess.Popen(
                ["su", "-", user, "-c", "steam steam://open/main"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            logger.error(f"Error navigating to Steam home: {e}")

    async def enter_background_mode(self, reason: str = "manual") -> bool:
        if self.is_background_mode:
            return True

        logger.info(f"Entering Background Download Mode (reason: {reason}).")
        self.is_background_mode = True
        self._acquire_sleep_inhibitor()
        self._apply_power_saving_and_screen_off()

        await decky.emit("background_mode_changed", {"is_background_mode": True, "reason": reason})
        return True

    async def exit_background_mode(self, reason: str = "manual") -> bool:
        if not self.is_background_mode:
            return False

        logger.info(f"Exiting Background Download Mode (reason: {reason}).")
        self.wake_cooldown_until = time.time() + 5.0
        self.is_background_mode = False
        self._restore_system_power_and_display()
        self._update_inhibitor_state()

        if reason == "power_button_wake":
            self._navigate_steam_home()

        await decky.emit("background_mode_changed", {"is_background_mode": False, "reason": reason})
        return True

    async def trigger_suspend(self):
        logger.info("Executing systemctl suspend...")
        if self.is_background_mode:
            self._restore_system_power_and_display()
            self.is_background_mode = False

        self._release_sleep_inhibitor()
        await asyncio.sleep(0.5)

        try:
            subprocess.run(["systemctl", "suspend"], check=False)
        except Exception as e:
            logger.error(f"Failed to execute systemctl suspend: {e}")

    # ==========================================
    # Periodic Background Loop (Download & Battery)
    # ==========================================
    async def _background_monitor_loop(self):
        logger.info("Starting background monitor loop...")
        while not self.stop_threads:
            try:
                await asyncio.sleep(1.5)

                if not self.settings.get("enabled", True):
                    continue

                # 1. Native Download Detection
                info = self.detector.detect()
                self.download_info.update(info)
                is_dl = (
                    self.download_info.get("is_downloading", False)
                    and not self.download_info.get("is_paused", False)
                )
                self.download_info["is_downloading"] = is_dl

                if is_dl:
                    self.last_download_active_time = time.time()

                # Sync inhibitor state
                self._update_inhibitor_state()

                # 2. In Background Mode Checks
                if self.is_background_mode:
                    bat = self._get_battery_info()

                    # Condition A: Low battery auto-suspend
                    min_thresh = int(self.settings.get("min_battery_threshold", 15))
                    if not bat["is_charging"] and bat["capacity"] <= min_thresh:
                        logger.warning(
                            f"Battery level {bat['capacity']}% <= {min_thresh}%. "
                            "Auto-suspending to protect battery!"
                        )
                        await decky.emit("battery_critical_suspend", {
                            "capacity": bat["capacity"],
                            "threshold": min_thresh,
                        })
                        await self.exit_background_mode("low_battery")
                        await self.trigger_suspend()
                        continue

                    # Condition B: Downloads finished or paused auto-suspend
                    if not is_dl:
                        elapsed_since_dl = time.time() - self.last_download_active_time
                        auto_sleep_delay = float(self.settings.get("auto_suspend_delay_seconds", 15))

                        if elapsed_since_dl >= auto_sleep_delay:
                            logger.info(
                                f"Downloads inactive or completed ({elapsed_since_dl:.1f}s inactive). "
                                "Auto-suspending system!"
                            )
                            await decky.emit("downloads_completed_suspend", {
                                "elapsed_seconds": elapsed_since_dl,
                            })
                            await self.exit_background_mode("downloads_completed")
                            await self.trigger_suspend()
                            continue

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in background monitor loop: {e}")
                await asyncio.sleep(2.0)
