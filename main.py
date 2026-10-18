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
import shutil
from typing import Dict, Any, Optional, List, Set, Tuple

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
    "auto_suspend_delay_seconds": 120,
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
        self.saved_platform_profile: Optional[str] = None
        self.saved_asus_thermal: Optional[str] = None
        self.saved_power_profile: Optional[str] = None
        self.saved_cpu_freqs: Dict[str, str] = {}
        self.saved_cpu_governors: Dict[str, str] = {}
        self.saved_cpu_epp: Dict[str, str] = {}
        self.saved_gpu_dpm: Dict[str, str] = {}
        self.saved_leds: Dict[str, str] = {}
        self.offlined_cpus: List[str] = []
        self.grabbed_gamepad_fds: Dict[str, int] = {}
        self.power_device_paths: Set[str] = set()

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
        self.last_frontend_dl_time: float = 0.0
        self.last_suspend_intercept_time: float = 0
        self.wake_cooldown_until: float = 0.0
        self.last_loop_timestamp: float = time.time()
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

        now = time.time()
        if self.download_info["is_downloading"]:
            self.last_download_active_time = now
            self.last_frontend_dl_time = now

        self._update_inhibitor_state()
        return True

    # ==========================================
    # Systemd Inhibitor & Sleep Target Masking Control
    # ==========================================
    def _mask_sleep_targets(self):
        try:
            subprocess.run(
                ["sudo", "systemctl", "mask", "--runtime", "sleep.target", "suspend.target", "hibernate.target", "hybrid-sleep.target"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Masked systemd sleep/suspend targets (runtime).")
        except Exception as e:
            logger.error(f"Failed to mask sleep targets: {e}")

    def _unmask_sleep_targets(self):
        try:
            subprocess.run(
                ["sudo", "systemctl", "unmask", "--runtime", "sleep.target", "suspend.target", "hibernate.target", "hybrid-sleep.target"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Unmasked systemd sleep/suspend targets (runtime).")
        except Exception as e:
            logger.error(f"Failed to unmask sleep targets: {e}")

    def _acquire_sleep_inhibitor(self):
        self._mask_sleep_targets()
        if self.inhibitor_proc is not None:
            return

        cmd = [
            "sudo",
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
        self._unmask_sleep_targets()
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
        if should_inhibit:
            self._mask_sleep_targets()
            if self.inhibitor_proc is None:
                self._acquire_sleep_inhibitor()
        elif not should_inhibit:
            if self.inhibitor_proc is not None:
                self._release_sleep_inhibitor()
            else:
                self._unmask_sleep_targets()

    # ==========================================
    # Suspend Interception & Logind Watcher
    # ==========================================
    def _trigger_suspend_intercepted(self):
        """Called whenever a suspend attempt is detected while downloads are active."""
        now = time.time()
        # If currently in background mode, any suspend attempt is a WAKE action!
        if self.is_background_mode:
            logger.info("Suspend attempt detected while in background mode -> Waking system!")
            self.wake_cooldown_until = now + 12.0
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.exit_background_mode("suspend_attempt_wake"),
                    self.loop
                )
            return

        # Cooldown: Ignore any suspend request if system just woke up within 12 seconds
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

    async def trigger_suspend_intercept(self) -> bool:
        """API called by frontend when SteamClient intercepts suspend."""
        self._trigger_suspend_intercepted()
        return True

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

                    lower = line.lower()
                    now = time.time()

                    # System resume from sleep detected via logind
                    if (
                        "operation 'sleep' finished" in lower
                        or "system is resuming" in lower
                    ):
                        logger.info("Logind reported system resume from sleep -> Enforcing wake cooldown.")
                        self.wake_cooldown_until = now + 12.0
                        if self.is_background_mode:
                            if self.loop and self.loop.is_running():
                                asyncio.run_coroutine_threadsafe(
                                    self.exit_background_mode("logind_resume"),
                                    self.loop
                                )
                        continue

                    if (
                        "inhibited by downloadinbackground" in lower
                        or "refusing operation" in lower
                        or "power key pressed to suspend" in lower
                        or "suspend key pressed to sleep" in lower
                        or "suspend entry requested" in lower
                    ):
                        logger.info(f"Logind journal suspend event: {line.strip()}")
                        # If in background mode, wake up!
                        if self.is_background_mode:
                            logger.info("Logind suspend event received while in background mode -> Waking system!")
                            self.wake_cooldown_until = now + 12.0
                            if self.loop and self.loop.is_running():
                                asyncio.run_coroutine_threadsafe(
                                    self.exit_background_mode("logind_wake"),
                                    self.loop
                                )
                            continue

                        # Ignore logind events during wake cooldown
                        if now < self.wake_cooldown_until:
                            continue

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
    def _find_power_sleep_devices(self) -> List[Tuple[str, str, bool]]:
        """Finds all input devices with KEY_POWER or KEY_SLEEP using kernel EVIOCGBIT and EVIOCGNAME."""
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
                        name_buf = bytearray(256)
                        try:
                            fcntl.ioctl(f.fileno(), 0x82004506, name_buf)  # EVIOCGNAME(256)
                            name = name_buf.split(b"\x00")[0].decode("utf-8", errors="ignore")
                        except Exception:
                            name = "Unknown Device"

                        name_lower = name.lower()
                        # Power button device (e.g. 'Power Button', 'Sleep Button', 'gpio-keys', 'Asus WMI')
                        # Must NOT be a keyboard (to avoid grabbing user's typing keyboard)
                        is_keyboard = "keyboard" in name_lower
                        is_grab_candidate = (
                            not is_keyboard
                            or "power" in name_lower
                            or "button" in name_lower
                        ) and "remapper" not in name_lower
                        devs.append((path, name, is_grab_candidate))
            except Exception:
                pass
        return devs

    def _power_button_listener_worker(self):
        logger.info("Starting hardware power key listener worker...")
        EVIOCGRAB = 0x40044590
        while not self.stop_threads:
            devices = self._find_power_sleep_devices()
            if not devices:
                time.sleep(3.0)
                continue

            fds = []
            grabbed_fds = set()
            for path, name, should_grab in devices:
                self.power_device_paths.add(path)
                try:
                    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                    if should_grab:
                        try:
                            # EVIOCGRAB: Grab exclusively so systemd-logind and Steam never see KEY_POWER!
                            fcntl.ioctl(fd, EVIOCGRAB, 1)
                            grabbed_fds.add(fd)
                            logger.info(f"Exclusively grabbed power device with EVIOCGRAB: {name} ({path})")
                        except Exception as ge:
                            logger.warning(f"Could not grab {name} ({path}): {ge}")
                    fds.append(fd)
                except Exception as e:
                    logger.debug(f"Could not open {path}: {e}")

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
                                    logger.info(f"Hardware key event intercepted exclusively: code={ev_code}")
                                    self._on_hardware_power_key()
                        except BlockingIOError:
                            pass
                        except Exception as e:
                            logger.error(f"Error reading hardware key event: {e}")
                            break
            finally:
                for fd in fds:
                    try:
                        if fd in grabbed_fds:
                            try:
                                fcntl.ioctl(fd, EVIOCGRAB, 0)
                            except Exception:
                                pass
                        os.close(fd)
                    except Exception:
                        pass
                time.sleep(1.0)

    def _on_hardware_power_key(self):
        if not self.settings.get("enabled", True):
            return

        now = time.time()
        # Cooldown check: ignore power button press if system just woke up within 12 seconds
        if now < self.wake_cooldown_until:
            logger.info("Ignoring power key because system just woke up.")
            return

        if self.is_background_mode:
            logger.info("Power button pressed during background mode -> Full system wake!")
            self.wake_cooldown_until = now + 12.0
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.exit_background_mode("power_button_wake"),
                    self.loop
                )
            return

        net_rx = self.detector.get_network_rx_rate()
        is_active_dl = (
            (self.download_info.get("is_downloading", False)
            and not self.download_info.get("is_paused", False))
            or (net_rx > 20000)
        )
        if is_active_dl:
            self._trigger_suspend_intercepted()
        else:
            logger.info("Power key pressed with no active downloads (paused/idle) -> Allowing normal suspend.")
            self._release_sleep_inhibitor()
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self.trigger_suspend(), self.loop)

    def _is_power_or_sleep_device(self, path: str) -> bool:
        if path in self.power_device_paths:
            return True
        try:
            with open(path, "rb") as f:
                buf = bytearray(96)
                fcntl.ioctl(f.fileno(), 0x80604521, buf)  # EVIOCGBIT(EV_KEY, 96)
                has_power = bool(buf[14] & (1 << 4))
                has_sleep = bool(buf[17] & (1 << 6))
                if has_power or has_sleep:
                    self.power_device_paths.add(path)
                    return True
        except Exception:
            pass
        return False

    def _grab_all_gamepad_inputs(self):
        """
        Exclusively grabs ALL non-power input devices (/dev/input/event*) using EVIOCGRAB.
        This blocks Steam, Gamescope, and OS from receiving any gamepad, button, trigger,
        touchscreen, or joystick inputs while in Background Download Mode.
        The device feels completely asleep and won't wake up or show menus when buttons are pressed.
        """
        EVIOCGRAB = 0x40044590
        count = 0
        for path in sorted(glob.glob("/dev/input/event*")):
            if path in self.grabbed_gamepad_fds or self._is_power_or_sleep_device(path):
                continue
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                try:
                    fcntl.ioctl(fd, EVIOCGRAB, 1)
                    self.grabbed_gamepad_fds[path] = fd
                    count += 1
                except Exception:
                    os.close(fd)
            except Exception:
                pass
        if count > 0:
            logger.info(f"Exclusively grabbed {count} gamepad/button input devices (lockout active).")

    def _release_all_gamepad_inputs(self):
        """
        Releases all grabbed input devices so gamepad, touchscreen, and buttons
        immediately regain normal control upon waking up.
        """
        EVIOCGRAB = 0x40044590
        released_count = len(self.grabbed_gamepad_fds)
        for path, fd in list(self.grabbed_gamepad_fds.items()):
            try:
                # Flush any pending events while grabbed so they don't fire on wake
                try:
                    while os.read(fd, 1024):
                        pass
                except (BlockingIOError, OSError):
                    pass
                fcntl.ioctl(fd, EVIOCGRAB, 0)
            except Exception:
                pass
            try:
                os.close(fd)
            except Exception:
                pass
        self.grabbed_gamepad_fds.clear()
        if released_count > 0:
            logger.info(f"Released {released_count} input devices (gamepad controls fully restored).")

    # ==========================================
    # Power Saving & Screen Control
    # ==========================================
    def _set_audio_mute(self, mute: bool):
        val = "1" if mute else "0"
        amixer_arg = "mute" if mute else "unmute"
        # 1. ALSA hardware master mute (works directly at hardware level)
        try:
            subprocess.run(["amixer", "-q", "set", "Master", amixer_arg], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

        # 2. PipeWire & PulseAudio per-user session sockets
        for uid_dir in glob.glob("/run/user/*"):
            if os.path.basename(uid_dir).isdigit():
                env = os.environ.copy()
                env["XDG_RUNTIME_DIR"] = uid_dir
                try:
                    subprocess.run(
                        ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", val],
                        env=env,
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    subprocess.run(
                        ["pactl", "set-sink-mute", "@DEFAULT_SINK@", val],
                        env=env,
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception:
                    pass

    def _set_gamescope_display(self, sleep: bool):
        arg = "1" if sleep else "0"
        bool_arg = "true" if sleep else "false"
        for uid_dir in glob.glob("/run/user/*"):
            if os.path.basename(uid_dir).isdigit():
                env = os.environ.copy()
                env["XDG_RUNTIME_DIR"] = uid_dir
                for cmd in ["gamescopectl", "/usr/bin/gamescopectl", "/usr/local/bin/gamescopectl"]:
                    try:
                        subprocess.run(
                            [cmd, "drm_sleep_internal_screen", arg],
                            env=env,
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        subprocess.run(
                            [cmd, "drm_sleep_internal_screen", bool_arg],
                            env=env,
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    except Exception:
                        pass

    def _apply_power_saving_and_screen_off(self):
        logger.info("Applying smart suspend power saving and screen off...")

        # 1. Turn off backlight: prioritize amdgpu_bl* on ROG Ally / Steam Deck
        if self.settings.get("turn_off_backlight", True):
            backlight_dirs = glob.glob("/sys/class/backlight/*")
            backlight_dirs.sort(key=lambda p: 0 if "amdgpu" in p else 1)

            for bdir in backlight_dirs:
                brightness_path = os.path.join(bdir, "brightness")
                max_b_path = os.path.join(bdir, "max_brightness")
                bl_power_path = os.path.join(bdir, "bl_power")

                if os.path.exists(brightness_path):
                    try:
                        with open(brightness_path, "r") as f:
                            curr_b = int(f.read().strip())
                        max_b = 255
                        if os.path.exists(max_b_path):
                            with open(max_b_path, "r") as mf:
                                max_b = int(mf.read().strip())

                        if brightness_path not in self.saved_brightness or self.saved_brightness[brightness_path] <= 0:
                            self.saved_brightness[brightness_path] = curr_b if curr_b > int(max_b * 0.05) else int(max_b * 0.6)

                        with open(brightness_path, "w") as f:
                            f.write("0")
                        logger.info(f"Set backlight {brightness_path} from {curr_b} to 0 (saved {self.saved_brightness[brightness_path]}).")
                    except Exception as e:
                        try:
                            subprocess.run(["sudo", "sh", "-c", f"echo 0 > '{brightness_path}'"], check=False)
                        except Exception:
                            pass

                if os.path.exists(bl_power_path):
                    try:
                        # FB_BLANK_POWERDOWN = 4 (completely shuts down backlight power on LCD/IPS panels)
                        with open(bl_power_path, "w") as f:
                            f.write("4")
                        logger.info(f"Set bl_power {bl_power_path} to 4 (FB_BLANK_POWERDOWN).")
                    except Exception as e:
                        try:
                            subprocess.run(["sudo", "sh", "-c", f"echo 4 > '{bl_power_path}'"], check=False)
                        except Exception:
                            pass

            # Also try gamescopectl to put the internal screen to sleep via Gamescope DRM
            self._set_gamescope_display(sleep=True)

            # Also try brightnessctl if installed
            try:
                subprocess.run(["brightnessctl", "set", "0%"], capture_output=True, check=False)
            except Exception:
                pass

        # 2. CPU Power Profile & Deep Low-Power Throttling (Stops fans, cuts power consumption to ~3W)
        if self.settings.get("throttle_cpu", True):
            # A. ACPI platform profile (direct kernel sysfs)
            profile_file = "/sys/firmware/acpi/platform_profile"
            choices_file = "/sys/firmware/acpi/platform_profile_choices"
            if os.path.exists(profile_file):
                try:
                    with open(profile_file, "r") as f:
                        self.saved_platform_profile = f.read().strip()
                    choices = ""
                    if os.path.exists(choices_file):
                        with open(choices_file, "r") as cf:
                            choices = cf.read().strip()
                    target_choice = "low-power" if "low-power" in choices else ("quiet" if "quiet" in choices else "balanced")
                    with open(profile_file, "w") as f:
                        f.write(target_choice)
                    logger.info(f"Set ACPI platform_profile to {target_choice} (was {self.saved_platform_profile}).")
                except Exception as e:
                    logger.debug(f"Direct ACPI platform_profile write failed: {e}")

            # B. ASUS WMI Thermal Policy (0=Normal, 1=Boost, 2=Silent)
            asus_thermal_file = "/sys/devices/platform/asus-nb-wmi/throttle_thermal_policy"
            if os.path.exists(asus_thermal_file):
                try:
                    with open(asus_thermal_file, "r") as f:
                        self.saved_asus_thermal = f.read().strip()
                    with open(asus_thermal_file, "w") as f:
                        f.write("2")
                    logger.info("Set ASUS thermal policy to Silent (2).")
                except Exception:
                    pass

            # C. powerprofilesctl fallback (if available)
            if shutil.which("powerprofilesctl"):
                try:
                    res = subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True, check=False)
                    if res.returncode == 0:
                        self.saved_power_profile = res.stdout.strip()
                        subprocess.run(["powerprofilesctl", "set", "power-saver"], check=False)
                        logger.info(f"Switched platform power profile from {self.saved_power_profile} to power-saver.")
                except Exception as e:
                    logger.debug(f"powerprofilesctl failed: {e}")

            # D. Dynamic CPU Core Offlining:
            # Keep cpu0 and cpu1 online for Steam download I/O; offline all other cores (cpu2..cpu15)
            # This parks secondary cores into deep C6 sleep, eliminating heat and stopping fans!
            self.offlined_cpus.clear()
            candidate_online_files = sorted(
                glob.glob("/sys/devices/system/cpu/cpu[2-9]/online") +
                glob.glob("/sys/devices/system/cpu/cpu[1-9][0-9]/online")
            )
            for online_file in candidate_online_files:
                try:
                    with open(online_file, "r") as f:
                        status = f.read().strip()
                    if status == "1":
                        try:
                            with open(online_file, "w") as f:
                                f.write("0")
                            self.offlined_cpus.append(online_file)
                        except PermissionError:
                            subprocess.run(["sudo", "sh", "-c", f"echo 0 > '{online_file}'"], check=False)
                            self.offlined_cpus.append(online_file)
                except Exception:
                    pass
            if self.offlined_cpus:
                logger.info(f"Offlined {len(self.offlined_cpus)} secondary CPU cores for deep low-power download.")

            # E. Cap max frequency on remaining online cores (cpu0, cpu1)
            self.saved_cpu_freqs.clear()
            for freq_file in glob.glob("/sys/devices/system/cpu/cpu[0-1]/cpufreq/scaling_max_freq"):
                try:
                    with open(freq_file, "r") as f:
                        curr_freq = f.read().strip()
                    self.saved_cpu_freqs[freq_file] = curr_freq
                    with open(freq_file, "w") as f:
                        f.write("1400000")
                except Exception:
                    pass

            # F. Set AMD Energy Performance Preference (EPP) to power
            epp_paths = glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference")
            for ep in epp_paths:
                try:
                    with open(ep, "r") as f:
                        curr_epp = f.read().strip()
                    self.saved_cpu_epp[ep] = curr_epp
                    with open(ep, "w") as f:
                        f.write("power")
                except Exception:
                    pass

        # 3. AMD GPU DPM Clock Level (downclock GPU to minimum power floor)
        if self.settings.get("throttle_gpu", True):
            dpm_paths = glob.glob("/sys/class/drm/card*/device/power_dpm_force_performance_level")
            for dpm_path in dpm_paths:
                try:
                    with open(dpm_path, "r") as f:
                        curr_dpm = f.read().strip()
                    self.saved_gpu_dpm[dpm_path] = curr_dpm
                    try:
                        with open(dpm_path, "w") as f:
                            f.write("low")
                    except PermissionError:
                        subprocess.run(["sudo", "sh", "-c", f"echo low > '{dpm_path}'"], check=False)
                    logger.info(f"Throttled GPU clock {dpm_path} to low (was {curr_dpm}).")
                except Exception as e:
                    logger.error(f"Failed to throttle GPU on {dpm_path}: {e}")

        # 4. Mute Audio (Hardware ALSA Master & PipeWire)
        if self.settings.get("mute_audio", True):
            self._set_audio_mute(True)

        # 5. LEDs / Gamepad Stick RGB Rings / Keyboard Backlight
        led_paths = glob.glob("/sys/class/leds/*/brightness")
        for lp in led_paths:
            lower_lp = lp.lower()
            if "bat" in lower_lp or "charge" in lower_lp or "power" in lower_lp:
                continue
            try:
                with open(lp, "r") as f:
                    curr_led = f.read().strip()
                if curr_led != "0":
                    self.saved_leds[lp] = curr_led
                    try:
                        with open(lp, "w") as f:
                            f.write("0")
                    except PermissionError:
                        subprocess.run(["sudo", "sh", "-c", f"echo 0 > '{lp}'"], check=False)
            except Exception:
                pass

        # 6. Exclusive Gamepad & Button Lockout (EVIOCGRAB on all controllers)
        # Prevents any button, trigger, joystick, or touch from waking the display or triggering menus!
        self._grab_all_gamepad_inputs()

    def _restore_system_power_and_display(self):
        logger.info("Restoring system power and display settings...")

        # 0. Release all gamepad & button locks FIRST so controls respond immediately
        self._release_all_gamepad_inputs()

        # 1. Restore Backlight
        for brightness_path, val in list(self.saved_brightness.items()):
            try:
                if os.path.exists(brightness_path):
                    bdir = os.path.dirname(brightness_path)
                    bl_power_path = os.path.join(bdir, "bl_power")
                    if os.path.exists(bl_power_path):
                        try:
                            with open(bl_power_path, "w") as pf:
                                pf.write("0")
                        except Exception:
                            pass

                    max_b_path = os.path.join(bdir, "max_brightness")
                    max_b = 255
                    if os.path.exists(max_b_path):
                        with open(max_b_path, "r") as mf:
                            max_b = int(mf.read().strip())
                    target = val if val > int(max_b * 0.05) else int(max_b * 0.6)
                    with open(brightness_path, "w") as f:
                        f.write(str(target))
                    logger.info(f"Restored backlight on {brightness_path} to {target}.")
            except Exception as e:
                logger.error(f"Failed to restore backlight on {brightness_path}: {e}")
        self.saved_brightness.clear()

        # Guarantee all backlight devices are unblanked and brightened
        backlight_dirs = glob.glob("/sys/class/backlight/*")
        for bdir in backlight_dirs:
            try:
                bl_power_path = os.path.join(bdir, "bl_power")
                if os.path.exists(bl_power_path):
                    try:
                        with open(bl_power_path, "w") as pf:
                            pf.write("0")
                    except Exception:
                        try:
                            subprocess.run(["sudo", "sh", "-c", f"echo 0 > '{bl_power_path}'"], check=False)
                        except Exception:
                            pass

                brightness_path = os.path.join(bdir, "brightness")
                max_b_path = os.path.join(bdir, "max_brightness")
                if os.path.exists(brightness_path) and os.path.exists(max_b_path):
                    with open(brightness_path, "r") as f:
                        curr_b = int(f.read().strip())
                    if curr_b <= 0:
                        with open(max_b_path, "r") as mf:
                            max_b = int(mf.read().strip())
                        with open(brightness_path, "w") as f:
                            f.write(str(int(max_b * 0.6)))
            except Exception:
                pass

        # Wake up internal display via Gamescope
        self._set_gamescope_display(sleep=False)

        # Fallback restore via brightnessctl
        try:
            subprocess.run(["brightnessctl", "set", "60%"], capture_output=True, check=False)
        except Exception:
            pass

        # 2. Restore CPU Cores & Power Profiles
        # A. Restore offlined CPU cores
        for online_file in self.offlined_cpus:
            try:
                try:
                    with open(online_file, "w") as f:
                        f.write("1")
                except PermissionError:
                    subprocess.run(["sudo", "sh", "-c", f"echo 1 > '{online_file}'"], check=False)
            except Exception:
                pass
        if self.offlined_cpus:
            logger.info(f"Restored {len(self.offlined_cpus)} offlined CPU cores to online state.")
        self.offlined_cpus.clear()

        # B. Restore CPU max frequencies
        for freq_file, orig_freq in list(self.saved_cpu_freqs.items()):
            try:
                if os.path.exists(freq_file):
                    with open(freq_file, "w") as f:
                        f.write(orig_freq)
            except Exception:
                pass
        self.saved_cpu_freqs.clear()

        # C. Restore ACPI platform profile
        if self.saved_platform_profile and os.path.exists("/sys/firmware/acpi/platform_profile"):
            try:
                with open("/sys/firmware/acpi/platform_profile", "w") as f:
                    f.write(self.saved_platform_profile)
                logger.info(f"Restored ACPI platform_profile to {self.saved_platform_profile}.")
            except Exception:
                pass
        self.saved_platform_profile = None

        # D. Restore ASUS thermal policy
        if self.saved_asus_thermal and os.path.exists("/sys/devices/platform/asus-nb-wmi/throttle_thermal_policy"):
            try:
                with open("/sys/devices/platform/asus-nb-wmi/throttle_thermal_policy", "w") as f:
                    f.write(self.saved_asus_thermal)
                logger.info(f"Restored ASUS thermal policy to {self.saved_asus_thermal}.")
            except Exception:
                pass
        self.saved_asus_thermal = None

        # E. Restore powerprofilesctl (if installed)
        if shutil.which("powerprofilesctl"):
            target_profile = self.saved_power_profile if self.saved_power_profile and self.saved_power_profile != "power-saver" else "balanced"
            try:
                subprocess.run(["powerprofilesctl", "set", target_profile], check=False)
                logger.info(f"Restored platform power profile to {target_profile}.")
            except Exception:
                pass
        self.saved_power_profile = None

        # F. Restore CPU EPP
        for ep, orig_epp in list(self.saved_cpu_epp.items()):
            try:
                if os.path.exists(ep):
                    target_epp = orig_epp if orig_epp and orig_epp != "power" else "balance_performance"
                    with open(ep, "w") as f:
                        f.write(target_epp)
            except Exception:
                pass
        self.saved_cpu_epp.clear()

        # 3. Restore GPU DPM across all cards
        for dpm_path, orig_dpm in list(self.saved_gpu_dpm.items()):
            try:
                if os.path.exists(dpm_path):
                    target_dpm = orig_dpm if orig_dpm and orig_dpm != "low" else "auto"
                    try:
                        with open(dpm_path, "w") as f:
                            f.write(target_dpm)
                    except PermissionError:
                        subprocess.run(["sudo", "sh", "-c", f"echo '{target_dpm}' > '{dpm_path}'"], check=False)
                    logger.info(f"Restored GPU performance level on {dpm_path} to {target_dpm}.")
            except Exception as e:
                logger.error(f"Failed to restore GPU on {dpm_path}: {e}")
        self.saved_gpu_dpm.clear()

        # 4. Unmute Audio (Hardware ALSA Master & PipeWire)
        if self.settings.get("mute_audio", True):
            self._set_audio_mute(False)

        # 5. Restore LEDs
        for lp, orig_val in list(self.saved_leds.items()):
            try:
                if os.path.exists(lp):
                    try:
                        with open(lp, "w") as f:
                            f.write(orig_val)
                    except PermissionError:
                        subprocess.run(["sudo", "sh", "-c", f"echo '{orig_val}' > '{lp}'"], check=False)
            except Exception:
                pass
        self.saved_leds.clear()

    # ==========================================
    # Background Mode Transitions
    # ==========================================
    async def enter_background_mode(self, reason: str = "manual") -> bool:
        if self.is_background_mode:
            return True

        # Do not enter background mode if wake cooldown is active!
        if time.time() < self.wake_cooldown_until:
            logger.info(f"Blocked enter_background_mode (reason: {reason}) because system just woke up.")
            return False

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
        self.wake_cooldown_until = time.time() + 12.0
        self.is_background_mode = False
        self._restore_system_power_and_display()
        self._update_inhibitor_state()

        await decky.emit("background_mode_changed", {"is_background_mode": False, "reason": reason})
        return True

    async def trigger_suspend(self):
        logger.info("Executing systemctl suspend...")
        if self.is_background_mode:
            self._restore_system_power_and_display()
            self.is_background_mode = False

        self._release_sleep_inhibitor()
        self._unmask_sleep_targets()
        await asyncio.sleep(0.5)

        try:
            subprocess.run(["sudo", "systemctl", "suspend"], check=False)
        except Exception as e:
            logger.error(f"Failed to execute systemctl suspend: {e}")

    # ==========================================
    # Periodic Background Loop (Download & Battery)
    # ==========================================
    async def _background_monitor_loop(self):
        logger.info("Starting background monitor loop...")
        self.last_loop_timestamp = time.time()
        while not self.stop_threads:
            try:
                await asyncio.sleep(1.5)

                now = time.time()
                dt = now - self.last_loop_timestamp
                self.last_loop_timestamp = now

                # 0. Kernel Sleep Resume Detection
                # Loop sleeps 1.5s. If dt > 3.5s, the system slept in kernel suspend and just woke up!
                if dt > 3.5:
                    logger.info(
                        f"System wake from kernel suspend detected (dt={dt:.1f}s)! "
                        "Enforcing wake cooldown and exiting background mode."
                    )
                    self.wake_cooldown_until = now + 12.0
                    if self.is_background_mode:
                        self.is_background_mode = False
                        self._restore_system_power_and_display()
                        self._update_inhibitor_state()
                        await decky.emit("background_mode_changed", {
                            "is_background_mode": False,
                            "reason": "system_resume_clock_jump",
                        })

                if not self.settings.get("enabled", True):
                    continue

                # 1. Native Download & Network Detection
                info = self.detector.detect()
                detector_is_dl = bool(info.get("is_downloading", False))
                detector_paused = bool(info.get("is_paused", False))
                net_rx = self.detector.get_network_rx_rate()

                # Check if frontend reported download recently (within 30 seconds)
                frontend_active = (
                    (now - self.last_frontend_dl_time < 30.0)
                    and bool(self.download_info.get("is_downloading", False))
                    and not bool(self.download_info.get("is_paused", False))
                )

                # Has active network traffic (> 30 KB/s)
                has_net_traffic = (net_rx > 30000)

                # Active download if detector says so, or frontend reported so recently, or network traffic exists
                is_dl = (
                    (detector_is_dl and not detector_paused)
                    or frontend_active
                    or (has_net_traffic and not detector_paused)
                )

                # If frontend provided richer info (game title, eta), keep it
                if not frontend_active and info:
                    self.download_info.update(info)

                self.download_info["is_downloading"] = is_dl
                if detector_paused and not is_dl:
                    self.download_info["is_paused"] = True

                if is_dl:
                    self.last_download_active_time = now
                    if net_rx > 0:
                        self.download_info["bytes_per_second"] = max(net_rx, self.download_info.get("bytes_per_second", 0))

                # Sync inhibitor state
                self._update_inhibitor_state()

                # 2. In Background Mode Checks
                if self.is_background_mode:
                    # Enforce screen backlight off and maintain gamepad lockout
                    if self.settings.get("turn_off_backlight", True):
                        for bdir in glob.glob("/sys/class/backlight/*"):
                            bp = os.path.join(bdir, "brightness")
                            bpow = os.path.join(bdir, "bl_power")
                            try:
                                with open(bp, "r") as f:
                                    if int(f.read().strip()) > 0:
                                        with open(bp, "w") as wf:
                                            wf.write("0")
                            except Exception:
                                pass
                            try:
                                with open(bpow, "r") as pf:
                                    if pf.read().strip() != "4":
                                        with open(bpow, "w") as pwf:
                                            pwf.write("4")
                            except Exception:
                                pass
                    self._grab_all_gamepad_inputs()

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
                        elapsed_since_dl = now - self.last_download_active_time
                        auto_sleep_delay = max(60.0, float(self.settings.get("auto_suspend_delay_seconds", 120)))

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
