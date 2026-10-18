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
import signal
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
    "deep_input_lockout": True,
    "block_controller_hidraw": False,
    "limit_download_speed": True,
    "download_speed_limit_mbps": 6,
    "download_cpu_percent": 30,
    "debug_logging": True,
}

INPUT_EVENT_FORMAT = "qqHHi"
INPUT_EVENT_SIZE = struct.calcsize(INPUT_EVENT_FORMAT)
EV_KEY = 1
KEY_POWER = 116
KEY_SLEEP = 142
EVIOCGRAB = 0x40044590

# Monitor loop cadence. While nothing is downloading the plugin must stay as close
# to a no-op as possible, so it polls slowly and never touches the system.
ACTIVE_LOOP_INTERVAL = 2.0
IDLE_LOOP_INTERVAL = 6.0
DISABLED_LOOP_INTERVAL = 10.0

# Seconds during which suspend/power events are ignored right after a wake, so the
# key press (or logind event) that woke the console cannot put it straight back to sleep.
WAKE_COOLDOWN_SECONDS = 5.0

# Grace periods after entering background mode, before power/logind events count as a wake.
POWER_KEY_GRACE_SECONDS = 2.5
LOGIND_GRACE_SECONDS = 5.0

# Linux scheduling policies that leave a process starved of CPU time.
SCHED_BATCH = 3
SCHED_IDLE = 5

# Processes whose sluggishness is immediately visible in Gaming Mode. Used to undo
# idle-priority scheduling that older versions of this plugin applied to Steam.
# Gamescope is deliberately absent: it was always excluded from that throttling, so it
# has nothing to repair, and its scheduling class is not something to touch on a wake.
STEAM_UI_COMMS = {
    "steam",
    "steamwebhelper",
    "reaper",
    "steam_monitor",
}

# How often the telemetry line (temperature, fan, power, speed) is written while the
# screen is off, so a session can be reviewed afterwards from the plugin log.
TELEMETRY_INTERVAL = 30.0

# cgroup CPU quota period, in microseconds.
CPU_QUOTA_PERIOD = 100000


class SteamDownloadDetector:
    """
    Natively inspects Steam library folders, appmanifest files, and network traffic
    to detect downloads with 100% reliability without relying on CEF JavaScript.
    """
    def __init__(self):
        self.cached_libraries: List[str] = []
        self.last_lib_scan: float = 0
        self.last_net_bytes: int = 0
        self.last_net_time: float = 0.0
        self.last_net_rate: float = 0.0
        self.last_completed_bytes: int = 0
        self.last_dl_calc_time: float = time.time()
        # appmanifest path -> (mtime_ns, parsed fields). Steam rewrites a manifest
        # while it downloads, so the mtime alone tells us when a re-read is needed.
        self.manifest_cache: Dict[str, Tuple[int, Optional[Dict[str, Any]]]] = {}

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

    def get_network_rx_rate(self, min_sample_age: float = 0.5) -> float:
        """
        Reads real received bytes per second across all non-lo network interfaces.

        Calls made less than min_sample_age apart return the previous result instead of
        re-sampling: two samples taken milliseconds apart always read as ~0 B/s, which
        used to make the plugin believe an active download had stopped.
        """
        now = time.time()
        if (now - self.last_net_time) < min_sample_age:
            return self.last_net_rate

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

        dt = max(0.1, now - self.last_net_time)
        bps = 0.0
        if self.last_net_bytes > 0 and curr_bytes >= self.last_net_bytes:
            bps = (curr_bytes - self.last_net_bytes) / dt

        self.last_net_bytes = curr_bytes
        self.last_net_time = now
        self.last_net_rate = bps
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

    def _read_manifest(self, path: str) -> Optional[Dict[str, Any]]:
        """Parses an appmanifest, reusing the cached result while its mtime is unchanged."""
        try:
            mtime_ns = os.stat(path).st_mtime_ns
        except OSError:
            self.manifest_cache.pop(path, None)
            return None

        cached = self.manifest_cache.get(path)
        if cached is not None and cached[0] == mtime_ns:
            return cached[1]

        parsed: Optional[Dict[str, Any]] = None
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                txt = f.read()

            state_m = re.search(r"\"StateFlags\"\s*\"(\d+)\"", txt)
            if state_m:
                name_m = re.search(r"\"name\"\s*\"([^\"]+)\"", txt)
                dl_m = re.search(r"\"BytesDownloaded\"\s*\"(\d+)\"", txt)
                tot_m = re.search(r"\"BytesToDownload\"\s*\"(\d+)\"", txt)

                b_dl = int(dl_m.group(1)) if dl_m else 0
                b_tot = int(tot_m.group(1)) if tot_m else 0
                parsed = {
                    "state": int(state_m.group(1)),
                    "game_title": name_m.group(1) if name_m else "Steam Download",
                    "completed_bytes": b_dl,
                    "total_bytes": b_tot,
                    "progress_percent": (b_dl / b_tot * 100) if b_tot > 0 else 0,
                }
        except Exception:
            parsed = None

        self.manifest_cache[path] = (mtime_ns, parsed)
        return parsed

    def detect(self) -> Dict[str, Any]:
        libs = self.get_library_paths()
        active_candidates: List[Dict[str, Any]] = []
        paused_candidates: List[Dict[str, Any]] = []
        seen_manifests: Set[str] = set()

        # Check appmanifest files in all libraries
        for sa in libs:
            for mf in glob.glob(os.path.join(sa, "appmanifest_*.acf")):
                seen_manifests.add(mf)
                parsed = self._read_manifest(mf)
                if not parsed:
                    continue

                state = parsed["state"]
                cand = {
                    "game_title": parsed["game_title"],
                    "completed_bytes": parsed["completed_bytes"],
                    "total_bytes": parsed["total_bytes"],
                    "progress_percent": parsed["progress_percent"],
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

        # Forget manifests for games that were uninstalled or moved to another library
        for stale in set(self.manifest_cache) - seen_manifests:
            self.manifest_cache.pop(stale, None)

        net_bps = self.get_network_rx_rate()

        # Walking steamapps/downloading/ is the only expensive check here, so it only runs
        # when a manifest or the network already hints that something may be downloading.
        has_recent_writes = False
        if active_candidates or paused_candidates or net_bps > 50000:
            has_recent_writes = self._has_recent_download_writes(libs, max_age_seconds=8.0)

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
        self.saved_asus_ppt: Dict[str, str] = {}
        self.saved_fan_boost: Dict[str, str] = {}
        self.saved_ryzenadj: Optional[Dict[str, int]] = None
        self.grabbed_gamepad_fds: Dict[str, int] = {}
        self.power_device_paths: Set[str] = set()
        self.power_grabbed_paths: Set[str] = set()
        self.unbound_hid_devices: List[Tuple[str, str]] = []
        self.frozen_daemons: List[str] = []
        self.inhibited_inputs: List[str] = []
        self.lockout_event_counts: Dict[str, int] = {}

        # Download pacing state, both reversible and recorded on disk so a crash mid
        # session can still be undone on the next start.
        self.saved_cpu_quota: Optional[Tuple[str, str]] = None
        self.last_cpu_quota_path: str = ""
        self.throttled_interfaces: List[str] = []
        self.runtime_state_file: str = ""
        self.last_telemetry_time: float = 0.0

        # Only undo what we actually changed, so toggling a setting mid-session can
        # never leave the console muted, dimmed or stuck on a power profile.
        self.audio_muted_by_us: bool = False
        self.power_profile_set_by_us: bool = False
        self.display_slept_by_us: bool = False
        self.power_saving_applied: bool = False

        self.inhibitor_proc: Optional[subprocess.Popen] = None
        self.power_button_thread: Optional[threading.Thread] = None
        self.logind_watcher_thread: Optional[threading.Thread] = None
        self.stop_threads: bool = False
        self.transition_lock = threading.Lock()
        self.input_lock = threading.Lock()
        self.transition_in_progress: bool = False
        self.suspend_in_progress: bool = False

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
        self.background_mode_entered_time: float = 0.0
        self.last_battery_info: Dict[str, Any] = {}
        self.last_battery_time: float = 0.0
        self.saved_cpu_boost: Optional[str] = None
        self.saved_policy_boost: Dict[str, str] = {}
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

        # 0. Undo anything a previous run (or a crash) may have left behind: masked
        # sleep targets, frozen controller daemons and Steam processes stuck at idle
        # scheduling priority all survive a plugin reload and make SteamOS feel broken.
        self.runtime_state_file = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "runtime_state.json")
        self._clear_stale_sleep_masks()
        self._heal_stray_input_inhibits()
        self._heal_runtime_state()
        if self._controller_daemons_look_frozen():
            logger.info("Startup repair: controller daemons were left frozen; resuming them.")
            self._resume_controller_daemons()
        healed = self._heal_steam_scheduling()
        if healed:
            logger.info(f"Startup repair: restored normal scheduling for {healed} Steam process(es).")
        self._log_input_diagnostics("plugin startup")

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
            self.is_background_mode = False
            self._restore_system_power_and_display()
        else:
            # Never leave a device grabbed or a daemon frozen behind.
            self._release_all_gamepad_inputs()

        self._release_sleep_inhibitor()
        self._clear_stale_sleep_masks()

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

        if not self.settings.get("enabled", True) and self.is_background_mode:
            await self.exit_background_mode("disabled_in_settings")

        self._update_inhibitor_state()
        return self.settings

    async def log_debug(self, payload: Dict[str, Any]) -> bool:
        """
        Writes a diagnostic payload from the frontend into the plugin log, so what the
        Steam client exposes on this console ends up in the same file as everything else.
        """
        try:
            logger.info(f"[DIB FRONTEND] {json.dumps(payload, default=str)[:12000]}")
        except Exception as e:
            logger.error(f"Could not log frontend diagnostics: {e}")
        return True

    # ==========================================
    # Battery & Hardware Status Queries
    # ==========================================
    def _get_battery_info(self, max_age: float = 2.0) -> Dict[str, Any]:
        now = time.time()
        if self.last_battery_info and (now - self.last_battery_time) < max_age:
            return self.last_battery_info

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

        self.last_battery_info = {
            "capacity": capacity,
            "is_charging": is_charging,
            "is_plugged": is_plugged or is_charging,
        }
        self.last_battery_time = now
        return self.last_battery_info

    async def get_status(self) -> Dict[str, Any]:
        bat = self._get_battery_info()
        return {
            "is_background_mode": self.is_background_mode,
            "battery_capacity": bat["capacity"],
            "is_charging": bat["is_charging"],
            "power_plugged": bat["is_plugged"],
            "inhibitor_active": self.inhibitor_proc is not None,
            "plugin_active": self._plugin_should_act(),
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
    # Systemd Sleep Inhibitor
    # ==========================================
    SLEEP_TARGETS = ("sleep.target", "suspend.target", "hibernate.target", "hybrid-sleep.target")

    def _clear_stale_sleep_masks(self):
        """
        Removes runtime masks on the systemd sleep targets.

        Earlier versions masked these targets to block suspend, which breaks suspend
        system-wide for as long as the mask stays in place (and survives a plugin crash).
        A logind 'block' inhibitor does the same job without that risk, so the masks are
        only ever cleaned up here. Permanent masks made by the user live in /etc and are
        not touched by --runtime.
        """
        stale = [t for t in self.SLEEP_TARGETS if os.path.islink(f"/run/systemd/system/{t}")]
        if not stale:
            return
        try:
            subprocess.run(
                ["systemctl", "unmask", "--runtime"] + list(self.SLEEP_TARGETS),
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10.0,
            )
            logger.info(f"Cleared leftover runtime mask on systemd sleep targets: {', '.join(stale)}.")
        except Exception as e:
            logger.error(f"Failed to clear sleep target masks: {e}")

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

    def _is_active_download(self) -> bool:
        return bool(
            self.download_info.get("is_downloading", False)
            and not self.download_info.get("is_paused", False)
        )

    def _plugin_should_act(self) -> bool:
        """
        The single answer to 'may the plugin touch the system right now?'.

        With the plugin enabled but nothing downloading, this is False and SteamOS is
        left completely alone: no inhibitor, no grabbed power button, no masked targets,
        so the stock suspend animation and behaviour are exactly as without the plugin.
        """
        if self.suspend_in_progress or not self.settings.get("enabled", True):
            return False
        return self.is_background_mode or self._is_active_download()

    def _update_inhibitor_state(self):
        # The inhibitor is a child process; if it ever dies, forget it so it can be retaken.
        if self.inhibitor_proc is not None and self.inhibitor_proc.poll() is not None:
            self.inhibitor_proc = None

        should_inhibit = self._plugin_should_act()
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
        time_in_bg = (now - self.background_mode_entered_time) if self.is_background_mode else 999.0
        # If currently in background mode, any suspend attempt after grace period is a WAKE action!
        if self.is_background_mode:
            if time_in_bg < LOGIND_GRACE_SECONDS:
                logger.info(f"Ignoring suspend intercept during background entry grace period ({time_in_bg:.1f}s).")
                return
            logger.info("Suspend attempt detected while in background mode -> Waking system!")
            self.wake_cooldown_until = now + WAKE_COOLDOWN_SECONDS
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
        if not self._is_active_download():
            logger.info("Suspend attempt not intercepted: Download is paused or idle. Allowing normal suspend.")
            self._update_inhibitor_state()
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

                    time_in_bg = (now - self.background_mode_entered_time) if self.is_background_mode else 999.0

                    # System resume from sleep detected via logind
                    if (
                        "operation 'sleep' finished" in lower
                        or "system is resuming" in lower
                    ):
                        logger.info("Logind reported system resume from sleep -> Enforcing wake cooldown.")
                        self.wake_cooldown_until = now + WAKE_COOLDOWN_SECONDS
                        if self.is_background_mode and time_in_bg > LOGIND_GRACE_SECONDS:
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
                        # If in background mode, wake up after grace period
                        if self.is_background_mode:
                            if time_in_bg < LOGIND_GRACE_SECONDS:
                                logger.info(f"Ignoring logind suspend event during background entry grace period ({time_in_bg:.1f}s).")
                                continue
                            logger.info("Logind suspend event received while in background mode -> Waking system!")
                            self.wake_cooldown_until = now + WAKE_COOLDOWN_SECONDS
                            if self.loop and self.loop.is_running():
                                asyncio.run_coroutine_threadsafe(
                                    self.exit_background_mode("logind_wake"),
                                    self.loop
                                )
                            continue

                        # Ignore logind events during wake cooldown
                        if now < self.wake_cooldown_until:
                            continue

                        if self._is_active_download():
                            self._trigger_suspend_intercepted()
                        else:
                            # Nothing to protect: let SteamOS suspend exactly as it normally would.
                            self._update_inhibitor_state()

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
        if not self.settings.get("enabled", True):
            return

        now = time.time()
        # Cooldown check: ignore power button press if system just woke up within 12 seconds
        if now < self.wake_cooldown_until:
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
                    self.exit_background_mode("power_button_wake"),
                    self.loop
                )
            return

        net_rx = self.detector.get_network_rx_rate()
        is_active_dl = self._is_active_download() or (net_rx > 20000)
        if is_active_dl:
            self._trigger_suspend_intercepted()
        else:
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

    def _write_sysfs(self, path: str, value: str) -> bool:
        """Writes a string value to sysfs/proc, with automatic passwordless sudo tee fallback."""
        try:
            with open(path, "w") as f:
                f.write(str(value))
            return True
        except Exception:
            try:
                p = subprocess.run(
                    ["sudo", "tee", path],
                    input=f"{value}\n",
                    text=True,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1.0,
                )
                return p.returncode == 0
            except Exception:
                return False

    def _find_daemon_pids(self, daemon: str) -> List[int]:
        """
        Finds PIDs whose executable (argv[0] or python script argv[1]) is exactly the daemon name.
        Never uses pkill -f, which also matches its own sudo parent and freezes it (hanging the plugin).
        """
        pids = []
        my_pid = os.getpid()
        for proc_dir in glob.glob("/proc/[0-9]*"):
            try:
                pid = int(os.path.basename(proc_dir))
                if pid == my_pid:
                    continue
                with open(os.path.join(proc_dir, "cmdline"), "rb") as f:
                    args = [a.decode("utf-8", errors="ignore") for a in f.read().split(b"\x00") if a]
                if not args:
                    continue
                exe = os.path.basename(args[0])
                # First non-flag argument after the interpreter (handles 'python3 -sP /usr/bin/hhd')
                script = next((os.path.basename(a) for a in args[1:] if not a.startswith("-")), "")
                if exe == daemon or (exe.startswith("python") and script == daemon):
                    pids.append(pid)
            except Exception:
                pass
        return pids

    def _signal_daemon(self, daemon: str, sig: int) -> List[int]:
        pids = self._find_daemon_pids(daemon)
        for pid in pids:
            try:
                os.kill(pid, sig)
            except Exception as e:
                logger.warning(f"Could not send signal {sig} to {daemon} ({pid}): {e}")
        return pids

    def _pause_controller_daemons(self):
        """
        Freezes controller mapping daemons (InputPlumber and Handheld Daemon) with SIGSTOP
        and systemctl freeze, so they stop translating button presses into the virtual
        controller Steam reads. Plugin runs as root (plugin.json flags), so signals are
        sent directly by PID.
        """
        self.frozen_daemons = []
        for daemon in ["inputplumber", "hhd"]:
            try:
                pids = self._signal_daemon(daemon, signal.SIGSTOP)
                subprocess.run(
                    ["systemctl", "freeze", f"{daemon}.service"],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5.0,
                )
                if pids:
                    self.frozen_daemons.append(daemon)
                    logger.info(f"Froze controller daemon {daemon} (pids={pids}).")
            except Exception as e:
                logger.warning(f"Freezing daemon {daemon} failed: {e}")

    def _controller_daemons_look_frozen(self) -> bool:
        """True if InputPlumber/HHD are sitting stopped, e.g. after a crash mid-lockout."""
        for daemon in ["inputplumber", "hhd"]:
            for pid in self._find_daemon_pids(daemon):
                try:
                    with open(f"/proc/{pid}/stat", "r") as f:
                        stat = f.read()
                    state = stat[stat.rfind(")") + 2:].split()[0]
                except Exception:
                    continue
                if state in ("T", "t"):
                    return True
        return False

    def _resume_controller_daemons(self, quiet: bool = False):
        """
        Unfreezes the controller mapping daemons.

        Called before the virtual controllers are rebound on purpose: a frozen daemon has
        the button presses from the lockout still queued on its input fds, and it replays
        them the moment it runs again. Letting it replay while its output device is still
        unbound is what keeps a press made with the screen off from opening the Quick
        Access Menu on wake.
        """
        for daemon in ["inputplumber", "hhd"]:
            try:
                subprocess.run(
                    ["systemctl", "thaw", f"{daemon}.service"],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5.0,
                )
                pids = self._signal_daemon(daemon, signal.SIGCONT)
                if pids and not quiet:
                    logger.info(f"Resumed controller daemon {daemon} (pids={pids}).")
            except Exception as e:
                logger.warning(f"Resuming daemon {daemon} failed: {e}")
        self.frozen_daemons = []

    def _iter_process_scheduling(self) -> List[Tuple[int, str, int, int]]:
        """Returns (pid, comm, nice, sched_policy) for every process, for the repair below."""
        found: List[Tuple[int, str, int, int]] = []
        my_pid = os.getpid()
        for proc_dir in glob.glob("/proc/[0-9]*"):
            try:
                pid = int(os.path.basename(proc_dir))
                if pid == my_pid:
                    continue
                with open(os.path.join(proc_dir, "stat"), "r") as f:
                    stat = f.read()
                # The comm field is wrapped in parentheses and may itself contain spaces.
                close = stat.rfind(")")
                comm = stat[stat.find("(") + 1:close]
                fields = stat[close + 2:].split()
                # /proc/pid/stat: field 19 is nice, field 41 is the scheduling policy;
                # both are offset by 3 here because state is the first field after comm.
                nice = int(fields[16])
                policy = int(fields[38])
                found.append((pid, comm, nice, policy))
            except Exception:
                continue
        return found

    def _heal_steam_scheduling(self) -> int:
        """
        Puts Steam's own processes back on normal CPU and I/O scheduling.

        Older versions of this plugin dropped everything matching 'steam' to SCHED_IDLE
        and nice 19 while the screen was off. Processes Steam started during that window
        inherited it and were never found again on wake, which left Gaming Mode
        permanently sluggish. Nothing throttles Steam any more, and this runs on every
        wake (and at startup) to repair consoles that are still in that state.
        """
        victims: List[int] = []
        for pid, comm, nice, policy in self._iter_process_scheduling():
            starved = nice > 0 or policy in (SCHED_BATCH, SCHED_IDLE)
            if not starved:
                continue
            if comm.lower() in STEAM_UI_COMMS:
                victims.append(pid)
                continue
            # Also rescue a running game that inherited idle scheduling from Steam.
            if policy == SCHED_IDLE:
                try:
                    with open(f"/proc/{pid}/cmdline", "rb") as f:
                        cmdline = f.read().decode("utf-8", errors="ignore")
                    if "/steamapps/common/" in cmdline:
                        victims.append(pid)
                except Exception:
                    pass

        if not victims:
            return 0

        pid_strs = [str(p) for p in victims]
        subprocess.run(
            ["renice", "-n", "0", "-p"] + pid_strs,
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for pid in pid_strs:
            for cmd in (
                ["chrt", "-o", "-p", "0", pid],
                ["ionice", "-c", "2", "-n", "4", "-p", pid],
            ):
                try:
                    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0)
                except Exception:
                    pass
        logger.info(f"Reset CPU/IO scheduling to normal for {len(victims)} Steam process(es).")
        return len(victims)

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
                f"[DIB TELEMETRY] net={net_mb:.2f}MB/s apu={power_w or 'n/a'} "
                f"cpu=[{' '.join(freqs) or 'n/a'}] fans=[{' '.join(fans) or 'none reported'}] "
                f"pwm=[{' '.join(pwms) or 'n/a'}] temps=[{' '.join(temps[:8]) or 'n/a'}] "
                f"quota={'on' if self.saved_cpu_quota else 'off'} "
                f"netcap={self.throttled_interfaces or 'off'}"
            )
        except Exception as e:
            logger.error(f"Failed to write telemetry: {e}")

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
        if deep:
            self._unbind_external_gamepads()
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
            self._log_input_diagnostics("before release")

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
        """
        Asks Gamescope to put the internal panel to sleep (or wake it).

        Only runs if gamescopectl actually exists, so machines without it (a desktop PC
        running SteamOS, where there is no internal panel anyway) do not pay for a dozen
        failed process spawns on every transition.
        """
        gamescopectl = shutil.which("gamescopectl") or next(
            (p for p in ("/usr/bin/gamescopectl", "/usr/local/bin/gamescopectl") if os.path.exists(p)),
            None,
        )
        if not gamescopectl:
            return

        arg = "1" if sleep else "0"
        user = self._get_session_user()
        for uid_dir in glob.glob("/run/user/*"):
            if not os.path.basename(uid_dir).isdigit():
                continue
            env = os.environ.copy()
            env["XDG_RUNTIME_DIR"] = uid_dir
            for cmd in (
                [gamescopectl, "drm_sleep_internal_screen", arg],
                # Gamescope only answers on its own user session's socket.
                ["sudo", "-u", user, "env", f"XDG_RUNTIME_DIR={uid_dir}", gamescopectl, "drm_sleep_internal_screen", arg],
            ):
                try:
                    subprocess.run(
                        cmd,
                        env=env,
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=2.0,
                    )
                except Exception:
                    pass

    # ==========================================
    # Download Pacing (the "handheld console" profile)
    # ==========================================
    def _steam_cgroup_dir(self) -> Optional[str]:
        """
        The cgroup v2 directory that already holds the main Steam process.

        Its cpu.max is written in place rather than moving processes into a cgroup of our
        own: moving them out of their systemd unit confuses systemd's tracking, while a
        cpu.max write is local, reversible, and the worst case if it is ever left behind
        is that systemd resets it on the next reload.
        """
        for pid, comm, _, _ in self._iter_process_scheduling():
            if comm.lower() != "steam":
                continue
            try:
                with open(f"/proc/{pid}/cgroup", "r") as f:
                    lines = f.readlines()
            except Exception:
                continue

            for line in lines:
                if not line.startswith("0::"):
                    continue  # Only the unified (v2) hierarchy carries cpu.max
                rel = line.strip().split("::", 1)[1]
                path = os.path.join("/sys/fs/cgroup", rel.lstrip("/"))
                # Steam's own cgroup, and only if the cpu controller is already enabled
                # there. Walking up to an ancestor would quietly throttle every other app
                # in that slice, and enabling the controller ourselves changes a cgroup
                # that belongs to systemd. Neither is worth the risk for a download.
                if os.path.exists(os.path.join(path, "cpu.max")):
                    return path
                logger.info(
                    f"CPU pacing unavailable: no cpu.max in Steam's own cgroup ({path}). "
                    "The download speed cap and the clock limits still apply."
                )
                return None
        return None

    def _cgroup_subtree_comms(self, cgroup_dir: str) -> Set[str]:
        comms: Set[str] = set()
        procs_files = [os.path.join(cgroup_dir, "cgroup.procs")]
        procs_files += glob.glob(os.path.join(cgroup_dir, "**", "cgroup.procs"), recursive=True)
        for procs_file in procs_files:
            try:
                with open(procs_file, "r") as f:
                    for line in f:
                        pid = line.strip()
                        if not pid:
                            continue
                        with open(f"/proc/{pid}/comm", "r") as cf:
                            comms.add(cf.read().strip().lower())
            except Exception:
                continue
        return comms

    def _apply_cpu_quota(self):
        """
        Caps how much CPU Steam may use while the screen is off.

        This is the lever that keeps the console cool, and it is what the old SCHED_IDLE
        throttling failed to do: with nothing else running, an idle-priority process
        still gets 100% of the CPU, so Steam decompressed at full speed and the fans
        spun up. A hard quota bounds the work per second, so the download settles at a
        calm pace and the SoC stays near idle - a download that takes longer but never
        heats the console up, the way a handheld console does it.
        """
        percent = int(self.settings.get("download_cpu_percent", 30))
        if percent <= 0 or percent >= 100:
            logger.info(f"CPU pacing disabled (download_cpu_percent={percent}).")
            return

        cgroup_dir = self._steam_cgroup_dir()
        if not cgroup_dir:
            logger.info("CPU pacing skipped: could not locate Steam's cgroup (cpu controller may be off).")
            return

        # Never throttle a cgroup the compositor shares: starving gamescope can take the
        # whole session down with it.
        comms = self._cgroup_subtree_comms(cgroup_dir)
        blockers = {c for c in comms if "gamescope" in c or "xwayland" in c}
        if blockers:
            logger.warning(f"CPU pacing skipped: Steam shares its cgroup with {sorted(blockers)}.")
            return

        cpu_max = os.path.join(cgroup_dir, "cpu.max")
        original = self._read_attr(cgroup_dir, "cpu.max") or "max 100000"
        quota = int(CPU_QUOTA_PERIOD * percent / 100)
        if self._write_sysfs(cpu_max, f"{quota} {CPU_QUOTA_PERIOD}"):
            self.saved_cpu_quota = (cpu_max, original)
            # Remembered separately so the final check can still verify this file even
            # after the restore has cleared saved_cpu_quota.
            self.last_cpu_quota_path = cpu_max
            logger.info(f"Paced Steam to {percent}% of one CPU core via {cpu_max} (was '{original}').")
        else:
            logger.warning(f"Could not write CPU quota to {cpu_max}.")

    def _restore_cpu_quota(self, saved: Optional[Tuple[str, str]] = None):
        entry = saved or self.saved_cpu_quota
        if not entry:
            return
        cpu_max, original = entry
        self.last_cpu_quota_path = cpu_max
        if os.path.exists(cpu_max):
            # An unreadable original would have been stored as the safe default, so this
            # always ends in an uncapped cgroup rather than a guess.
            target = original if original and not original.startswith("0 ") else f"max {CPU_QUOTA_PERIOD}"
            self._write_sysfs(cpu_max, target)
            logger.info(f"Restored CPU quota on {cpu_max} to '{target}'.")
        self.saved_cpu_quota = None

    def _network_interfaces(self, default_only: bool = True) -> List[str]:
        """Interfaces carrying the default route, or every live non-loopback interface."""
        ifaces: List[str] = []
        if default_only:
            try:
                with open("/proc/net/route", "r") as f:
                    for line in f.readlines()[1:]:
                        parts = line.split()
                        # Destination 00000000 == default route
                        if len(parts) > 2 and parts[1] == "00000000":
                            ifaces.append(parts[0])
            except Exception:
                pass
        if not ifaces:
            for path in sorted(glob.glob("/sys/class/net/*")):
                name = os.path.basename(path)
                if name == "lo":
                    continue
                if self._read_attr(path, "operstate") in ("up", "unknown"):
                    ifaces.append(name)
        return list(dict.fromkeys(ifaces))

    def _tc_binary(self) -> Optional[str]:
        return shutil.which("tc") or next((p for p in ("/usr/sbin/tc", "/sbin/tc") if os.path.exists(p)), None)

    def _tc_has_ingress(self, tc: str, iface: str) -> bool:
        try:
            res = subprocess.run(
                [tc, "qdisc", "show", "dev", iface, "ingress"],
                capture_output=True, text=True, check=False, timeout=5.0,
            )
            return "ingress" in (res.stdout or "")
        except Exception:
            return False

    def _limit_download_bandwidth(self):
        """
        Caps incoming bandwidth with an ingress policer, so Steam simply receives less
        data per second and therefore has far less to decompress and write. Pacing the
        bytes is the most direct way to keep the whole chain - radio, CPU, SSD - quiet.
        """
        if not self.settings.get("limit_download_speed", True):
            return
        tc = self._tc_binary()
        if not tc:
            logger.info("Download speed cap skipped: tc (iproute2) is not installed.")
            return

        megabytes = max(1, int(self.settings.get("download_speed_limit_mbps", 6)))
        rate = f"{megabytes * 8}mbit"
        for iface in self._network_interfaces():
            try:
                # Start from a clean slate in case a previous run left a qdisc behind
                subprocess.run([tc, "qdisc", "del", "dev", iface, "ingress"],
                               check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5.0)
                add = subprocess.run([tc, "qdisc", "add", "dev", iface, "handle", "ffff:", "ingress"],
                                     capture_output=True, text=True, check=False, timeout=5.0)
                if add.returncode != 0:
                    logger.warning(f"Could not add ingress qdisc on {iface}: {(add.stderr or '').strip()}")
                    continue

                applied = False
                for proto, prio, match in (
                    ("ip", "50", ["match", "ip", "src", "0.0.0.0/0"]),
                    ("ipv6", "51", ["match", "ip6", "src", "::/0"]),
                ):
                    res = subprocess.run(
                        [tc, "filter", "add", "dev", iface, "parent", "ffff:", "protocol", proto,
                         "prio", prio, "u32"] + match +
                        ["police", "rate", rate, "burst", "512k", "mtu", "65535", "drop", "flowid", ":1"],
                        capture_output=True, text=True, check=False, timeout=5.0,
                    )
                    if res.returncode == 0:
                        applied = True
                    else:
                        logger.info(f"Ingress filter for {proto} on {iface} not applied: {(res.stderr or '').strip()}")

                if applied:
                    self.throttled_interfaces.append(iface)
                    logger.info(f"Download paced to ~{megabytes} MB/s on {iface} ({rate} ingress policing).")
                else:
                    subprocess.run([tc, "qdisc", "del", "dev", iface, "ingress"],
                                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5.0)
            except Exception as e:
                logger.error(f"Failed to pace download on {iface}: {e}")

    def _clear_download_bandwidth_limit(self, interfaces: Optional[List[str]] = None):
        tc = self._tc_binary()
        if not tc:
            self.throttled_interfaces.clear()
            return
        # Deleted unconditionally, never gated on detecting the qdisc first: if the
        # detection ever misreads, the cap would stay on and the console would look
        # permanently slow. Deleting a qdisc that is not there just returns an error.
        for iface in (interfaces if interfaces is not None else list(self.throttled_interfaces)):
            try:
                res = subprocess.run(
                    [tc, "qdisc", "del", "dev", iface, "ingress"],
                    capture_output=True, text=True, check=False, timeout=5.0,
                )
                if res.returncode == 0:
                    logger.info(f"Removed download speed cap on {iface}.")
            except Exception as e:
                logger.error(f"Failed to clear download cap on {iface}: {e}")
        self.throttled_interfaces.clear()

    # ==========================================
    # Crash-safe record of the reversible changes
    # ==========================================
    def _runtime_state_snapshot(self) -> Dict[str, Any]:
        """Everything needed to undo a session, in a form that survives a restart."""
        return {
            "cpu_quota": list(self.saved_cpu_quota) if self.saved_cpu_quota else None,
            "throttled_interfaces": list(self.throttled_interfaces),
            "brightness": dict(self.saved_brightness),
            "cpu_freqs": dict(self.saved_cpu_freqs),
            "cpu_governors": dict(self.saved_cpu_governors),
            "cpu_epp": dict(self.saved_cpu_epp),
            "policy_boost": dict(self.saved_policy_boost),
            "gpu_dpm": dict(self.saved_gpu_dpm),
            "leds": dict(self.saved_leds),
            "asus_ppt": dict(self.saved_asus_ppt),
            "fan_boost": dict(self.saved_fan_boost),
            "cpu_boost": self.saved_cpu_boost,
            "platform_profile": self.saved_platform_profile,
            "asus_thermal": self.saved_asus_thermal,
            "power_profile": self.saved_power_profile,
            "power_profile_set_by_us": self.power_profile_set_by_us,
            "audio_muted": self.audio_muted_by_us,
            "display_slept": self.display_slept_by_us,
            "ryzenadj": dict(self.saved_ryzenadj) if self.saved_ryzenadj else None,
        }

    def _load_runtime_state(self, state: Dict[str, Any]):
        """Rebuilds the saved_* values from disk so the normal restore path can run."""
        quota = state.get("cpu_quota")
        self.saved_cpu_quota = (quota[0], quota[1]) if isinstance(quota, list) and len(quota) == 2 else None
        self.throttled_interfaces = list(state.get("throttled_interfaces") or [])
        self.saved_brightness = {
            k: int(v) for k, v in (state.get("brightness") or {}).items() if str(v).lstrip("-").isdigit()
        }
        self.saved_cpu_freqs = dict(state.get("cpu_freqs") or {})
        self.saved_cpu_governors = dict(state.get("cpu_governors") or {})
        self.saved_cpu_epp = dict(state.get("cpu_epp") or {})
        self.saved_policy_boost = dict(state.get("policy_boost") or {})
        self.saved_gpu_dpm = dict(state.get("gpu_dpm") or {})
        self.saved_leds = dict(state.get("leds") or {})
        self.saved_asus_ppt = dict(state.get("asus_ppt") or {})
        self.saved_fan_boost = dict(state.get("fan_boost") or {})
        self.saved_cpu_boost = state.get("cpu_boost")
        self.saved_platform_profile = state.get("platform_profile")
        self.saved_asus_thermal = state.get("asus_thermal")
        self.saved_power_profile = state.get("power_profile")
        self.power_profile_set_by_us = bool(state.get("power_profile_set_by_us"))
        self.audio_muted_by_us = bool(state.get("audio_muted"))
        self.display_slept_by_us = bool(state.get("display_slept"))
        ryzenadj = state.get("ryzenadj")
        self.saved_ryzenadj = {k: int(v) for k, v in ryzenadj.items()} if isinstance(ryzenadj, dict) else None

    def _save_runtime_state(self):
        """
        Records the changes that outlive a plugin crash, so the next start can undo them.
        A CPU quota, a network cap or a clock ceiling left behind looks exactly like a
        permanently slow console, which is the one failure this plugin must never cause.
        """
        if not self.runtime_state_file:
            return
        try:
            os.makedirs(os.path.dirname(self.runtime_state_file), exist_ok=True)
            with open(self.runtime_state_file, "w", encoding="utf-8") as f:
                json.dump(self._runtime_state_snapshot(), f, indent=2)
        except Exception as e:
            logger.error(f"Could not write runtime state: {e}")

    def _clear_runtime_state(self):
        try:
            if self.runtime_state_file and os.path.exists(self.runtime_state_file):
                os.remove(self.runtime_state_file)
        except Exception as e:
            logger.error(f"Could not clear runtime state: {e}")

    def _heal_runtime_state(self):
        """
        Undoes a session that never got its restore, by replaying the normal restore with
        the values read back from disk. This is what makes a plugin crash (or a forced
        reload) while the screen was off recoverable without rebooting the console.
        """
        if not self.runtime_state_file or not os.path.exists(self.runtime_state_file):
            return
        try:
            with open(self.runtime_state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception as e:
            logger.error(f"Leftover runtime state could not be read ({e}); clearing caps generically.")
            state = {}

        logger.warning(
            "Startup repair: a previous session was never restored. Undoing it now: "
            f"{ {k: (len(v) if isinstance(v, (dict, list)) else v) for k, v in state.items()} }"
        )
        self._load_runtime_state(state)
        # Always clear the network cap on every interface, tracked or not.
        self._clear_download_bandwidth_limit(self._network_interfaces(default_only=False))
        self._restore_system_power_and_display()
        self._clear_runtime_state()

    # ryzenadj option name -> multiplier to turn the reported value back into the unit
    # ryzenadj expects on the command line (watts are reported, milliwatts are written).
    RYZENADJ_RESTORE_KEYS = {
        "stapm-limit": 1000,
        "fast-limit": 1000,
        "slow-limit": 1000,
    }

    def _read_ryzenadj_limits(self) -> Dict[str, int]:
        """
        Reads the APU power limits currently in force, so they can be put back exactly.
        'ryzenadj -i' prints one table row per value: | STAPM LIMIT | 15.000 | stapm-limit |
        """
        limits: Dict[str, int] = {}
        try:
            res = subprocess.run(["ryzenadj", "-i"], capture_output=True, text=True, check=False, timeout=8.0)
        except Exception as e:
            logger.debug(f"Could not read ryzenadj limits: {e}")
            return limits

        for line in (res.stdout or "").splitlines():
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) < 3:
                continue
            scale = self.RYZENADJ_RESTORE_KEYS.get(parts[-1])
            if scale is None:
                continue
            try:
                value = float(parts[1])
            except ValueError:
                continue
            if value > 0:
                limits[parts[-1]] = int(round(value * scale))
        return limits

    def _apply_power_saving_and_screen_off(self):
        # Hard guard: applying twice would save the already-throttled values as the
        # originals, and the console would stay at 6W / 800MHz even after waking up.
        if self.power_saving_applied:
            logger.warning("Power saving already applied; skipping to avoid saving throttled values as the originals.")
            return
        self.power_saving_applied = True

        logger.info("Applying smart suspend power saving and screen off...")

        # 1. Turn off backlight: prioritize amdgpu_bl* on ROG Ally / Steam Deck
        if self.settings.get("turn_off_backlight", True):
            self.display_slept_by_us = True
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
                    target_choice = "quiet" if "quiet" in choices else ("low-power" if "low-power" in choices else "balanced")
                    self._write_sysfs(profile_file, target_choice)
                    logger.info(f"Set ACPI platform_profile to {target_choice} (was {self.saved_platform_profile}).")
                except Exception as e:
                    logger.debug(f"Direct ACPI platform_profile write failed: {e}")

            # B. ASUS WMI Thermal Policy (0=Normal, 1=Boost, 2=Silent)
            for asus_thermal_file in [
                "/sys/devices/platform/asus-nb-wmi/throttle_thermal_policy",
                "/sys/devices/platform/asus_wmi/throttle_thermal_policy",
            ]:
                if os.path.exists(asus_thermal_file):
                    try:
                        with open(asus_thermal_file, "r") as f:
                            self.saved_asus_thermal = f.read().strip()
                        self._write_sysfs(asus_thermal_file, "2")
                        logger.info(f"Set ASUS thermal policy on {asus_thermal_file} to Silent (2).")
                    except Exception:
                        pass

            # Fan boost mode (Silent = 2). Saved, because leaving the fans in silent mode
            # after waking makes the console throttle and feel permanently slow.
            self.saved_fan_boost.clear()
            for fan_boost in glob.glob("/sys/devices/platform/asus*/fan_boost_mode"):
                try:
                    with open(fan_boost, "r") as f:
                        self.saved_fan_boost[fan_boost] = f.read().strip()
                except Exception:
                    continue
                self._write_sysfs(fan_boost, "2")

            # C. ASUS Hardware PPT / SPL Power Limits (Hard limit to 6 Watts!)
            self.saved_asus_ppt.clear()
            ppt_files = [
                "/sys/devices/platform/asus-nb-wmi/ppt_pl1_spl",
                "/sys/devices/platform/asus-nb-wmi/ppt_pl2_sppt",
                "/sys/devices/platform/asus-nb-wmi/ppt_fppt",
                "/sys/class/firmware-attributes/asus-armoury/attributes/ppt_pl1_spl/current_value",
                "/sys/class/firmware-attributes/asus-armoury/attributes/ppt_pl2_sppt/current_value",
                "/sys/class/firmware-attributes/asus-armoury/attributes/ppt_fppt/current_value",
            ]
            for pf in ppt_files:
                if os.path.exists(pf):
                    try:
                        with open(pf, "r") as f:
                            curr_ppt = f.read().strip()
                        self.saved_asus_ppt[pf] = curr_ppt
                        self._write_sysfs(pf, "6")
                        logger.info(f"Capped ASUS PPT limit on {pf} to 6W (was {curr_ppt}).")
                    except Exception:
                        pass

            # D. ryzenadj fallback (hardware-cap APU power to 6W)
            # Only ever applied when the current limits can be read back first: a fixed
            # "restore" value would cap the APU at the wrong wattage forever, which is
            # exactly what used to leave the machine slow after waking up (and would cap
            # a desktop APU far below its stock limits).
            if shutil.which("ryzenadj"):
                if self.saved_ryzenadj is None:
                    self.saved_ryzenadj = self._read_ryzenadj_limits()
                if self.saved_ryzenadj:
                    try:
                        subprocess.run(
                            ["ryzenadj", "--stapm-limit=6000", "--fast-limit=6000", "--slow-limit=6000"],
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=5.0,
                        )
                        logger.info(f"Capped APU power to 6W via ryzenadj (will restore {self.saved_ryzenadj}).")
                    except Exception:
                        pass
                else:
                    logger.info("Skipping ryzenadj: its current limits could not be read, so they could not be restored on wake.")

            # E. powerprofilesctl fallback (if available)
            if shutil.which("powerprofilesctl"):
                try:
                    res = subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True, check=False, timeout=5.0)
                    if res.returncode == 0:
                        current = res.stdout.strip()
                        if current and current != "power-saver":
                            self.saved_power_profile = current
                        subprocess.run(["powerprofilesctl", "set", "power-saver"], check=False, timeout=5.0)
                        self.power_profile_set_by_us = True
                except Exception:
                    pass

            # F. Disable CPU Turbo Boost completely (AMD cpufreq boost -> 0)
            boost_file = "/sys/devices/system/cpu/cpufreq/boost"
            if os.path.exists(boost_file):
                try:
                    with open(boost_file, "r") as f:
                        self.saved_cpu_boost = f.read().strip()
                    self._write_sysfs(boost_file, "0")
                    logger.info("Disabled global CPU turbo boost (boost -> 0).")
                except Exception:
                    pass

            self.saved_policy_boost.clear()
            for pboost in glob.glob("/sys/devices/system/cpu/cpufreq/policy*/boost"):
                try:
                    with open(pboost, "r") as f:
                        curr_b = f.read().strip()
                    self.saved_policy_boost[pboost] = curr_b
                    self._write_sysfs(pboost, "0")
                except Exception:
                    pass

            # G. Throttle CPU Frequency to Minimum across ALL cores & policies
            min_freq = "800000"
            for min_file in ["/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq"]:
                if os.path.exists(min_file):
                    try:
                        with open(min_file, "r") as mf:
                            val = mf.read().strip()
                            if val.isdigit() and int(val) > 0:
                                min_freq = str(max(600000, int(val)))
                                break
                    except Exception:
                        pass

            self.saved_cpu_freqs.clear()
            freq_files = glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq") + glob.glob("/sys/devices/system/cpu/cpufreq/policy*/scaling_max_freq")
            for freq_file in set(freq_files):
                try:
                    with open(freq_file, "r") as f:
                        curr_freq = f.read().strip()
                    self.saved_cpu_freqs[freq_file] = curr_freq
                    self._write_sysfs(freq_file, min_freq)
                except Exception:
                    pass
            if self.saved_cpu_freqs:
                logger.info(f"Capped CPU max frequency to {min_freq} kHz across {len(self.saved_cpu_freqs)} nodes for calm, silent cooling.")

            # H. Set CPU scaling governor to powersave across all cores
            self.saved_cpu_governors.clear()
            gov_files = glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor") + glob.glob("/sys/devices/system/cpu/cpufreq/policy*/scaling_governor")
            for gov_file in set(gov_files):
                try:
                    with open(gov_file, "r") as f:
                        curr_gov = f.read().strip()
                    self.saved_cpu_governors[gov_file] = curr_gov
                    self._write_sysfs(gov_file, "powersave")
                except Exception:
                    pass

            # I. Set AMD Energy Performance Preference (EPP) to power
            self.saved_cpu_epp.clear()
            epp_files = glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference") + glob.glob("/sys/devices/system/cpu/cpufreq/policy*/energy_performance_preference")
            for ep in set(epp_files):
                try:
                    with open(ep, "r") as f:
                        curr_epp = f.read().strip()
                    self.saved_cpu_epp[ep] = curr_epp
                    self._write_sysfs(ep, "power")
                except Exception:
                    pass

            # Note: Steam's own processes are deliberately left at normal CPU/IO priority.
            # Dropping them to SCHED_IDLE slowed the download itself down, and anything
            # Steam spawned inherited it and stayed starved long after waking up.

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

        # 3.5 Pace the download itself. Capping the clocks alone does not stop the fans,
        # because Steam will happily use every cycle it is given; limiting the bytes per
        # second and the CPU it may spend on them is what keeps the console cold.
        self._limit_download_bandwidth()
        self._apply_cpu_quota()

        # 4. Mute Audio (Hardware ALSA Master & PipeWire)
        if self.settings.get("mute_audio", True):
            self._set_audio_mute(True)
            self.audio_muted_by_us = True

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

        # 6. Write down everything that now needs undoing, before touching input. If the
        # plugin dies from here on, the next start replays this exact restore.
        self._save_runtime_state()

        # 7. Exclusive Gamepad & Button Lockout (EVIOCGRAB on all controllers)
        # Prevents any button, trigger, joystick, or touch from waking the display or triggering menus!
        self._grab_all_gamepad_inputs()

    def _restore_system_power_and_display(self):
        """
        Puts everything back, with every stage isolated from the others.

        A failure in one stage must never skip the stages after it. That is exactly how a
        console ends up stuck at 800 MHz, capped at 6 W, or paced to a few MB/s until the
        next reboot: one unlucky exception early on, and nothing below it ever ran. So
        each stage runs no matter what the previous one did, and a final check forces back
        anything measurable that is still throttled.
        """
        logger.info("Restoring system power and display settings...")
        self.power_saving_applied = False

        stages = (
            ("backlight", self._restore_backlight),
            ("download pacing", self._restore_download_pacing),
            ("steam scheduling", self._heal_steam_scheduling),
            ("apu power limits", self._restore_apu_power_limits),
            ("cpu", self._restore_cpu_settings),
            ("platform profile", self._restore_platform_profile),
            ("gpu", self._restore_gpu_settings),
            ("audio", self._restore_audio),
            ("leds", self._restore_leds),
            ("input", self._release_all_gamepad_inputs),
        )

        failed: List[str] = []
        for label, stage in stages:
            try:
                stage()
            except Exception as e:
                failed.append(label)
                logger.error(f"Restore stage '{label}' FAILED: {e}")

        forced = self._verify_and_force_restore()
        if failed or forced:
            logger.warning(
                f"Restore finished with problems. failed_stages={failed or 'none'} forced_fixes={forced or 'none'}"
            )
        else:
            logger.info("Restore complete; everything verified back to normal.")

    def _restore_backlight(self):
        # Restore the backlight FIRST, so pressing power lights the screen up at once
        # instead of after every power limit and input device has been handed back.
        # Only panels this plugin actually dimmed are touched, so a console whose
        # backlight was never changed keeps exactly the brightness the user set.
        dimmed_paths = list(self.saved_brightness.items())
        for brightness_path, val in dimmed_paths:
            try:
                if os.path.exists(brightness_path):
                    bdir = os.path.dirname(brightness_path)
                    bl_power_path = os.path.join(bdir, "bl_power")
                    if os.path.exists(bl_power_path):
                        self._write_sysfs(bl_power_path, "0")

                    max_b_path = os.path.join(bdir, "max_brightness")
                    max_b = 255
                    if os.path.exists(max_b_path):
                        with open(max_b_path, "r") as mf:
                            max_b = int(mf.read().strip())
                    target = val if val > int(max_b * 0.05) else int(max_b * 0.6)
                    self._write_sysfs(brightness_path, str(target))
                    logger.info(f"Restored backlight on {brightness_path} to {target}.")
            except Exception as e:
                logger.error(f"Failed to restore backlight on {brightness_path}: {e}")
        self.saved_brightness.clear()

        # Second pass: a single failed sysfs write here is the difference between waking
        # up and staring at a black screen, so any panel still dark gets another attempt.
        for brightness_path, val in dimmed_paths:
            try:
                with open(brightness_path, "r") as f:
                    if int(f.read().strip()) > 0:
                        continue
            except Exception:
                continue
            bdir = os.path.dirname(brightness_path)
            self._write_sysfs(os.path.join(bdir, "bl_power"), "0")
            max_b = 255
            try:
                with open(os.path.join(bdir, "max_brightness"), "r") as mf:
                    max_b = int(mf.read().strip())
            except Exception:
                pass
            self._write_sysfs(brightness_path, str(val if val > 0 else int(max_b * 0.6)))
            try:
                subprocess.run(["brightnessctl", "set", "60%"], capture_output=True, check=False, timeout=3.0)
            except Exception:
                pass

        # Wake the internal display back up through Gamescope (only if we slept it)
        if self.display_slept_by_us:
            self._set_gamescope_display(sleep=False)
            self.display_slept_by_us = False

    def _restore_download_pacing(self):
        """Full speed again: the CPU quota and the network cap both go away here."""
        self._restore_cpu_quota()
        self._clear_download_bandwidth_limit()
        self._clear_runtime_state()

    def _restore_apu_power_limits(self):
        # Restore ASUS PPT power limits
        for pf, orig_ppt in list(self.saved_asus_ppt.items()):
            if os.path.exists(pf):
                self._write_sysfs(pf, orig_ppt)
                logger.info(f"Restored ASUS PPT limit on {pf} to {orig_ppt}.")
        self.saved_asus_ppt.clear()

        # Restore the exact APU power limits that were in force before the screen went off
        if self.saved_ryzenadj and shutil.which("ryzenadj"):
            args = [f"--{opt}={val}" for opt, val in sorted(self.saved_ryzenadj.items())]
            try:
                subprocess.run(
                    ["ryzenadj"] + args,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8.0,
                )
                logger.info(f"Restored APU power limits via ryzenadj: {' '.join(args)}.")
            except Exception as e:
                logger.error(f"Failed to restore ryzenadj limits: {e}")
        self.saved_ryzenadj = None

    def _restore_cpu_settings(self):
        # Restore CPU turbo boost, frequency ceilings, governors and EPP
        # A. Restore CPU Turbo Boost
        if self.saved_cpu_boost is not None:
            self._write_sysfs("/sys/devices/system/cpu/cpufreq/boost", self.saved_cpu_boost)
            logger.info(f"Restored global CPU turbo boost to {self.saved_cpu_boost}.")
            self.saved_cpu_boost = None

        for pboost, orig_b in list(self.saved_policy_boost.items()):
            self._write_sysfs(pboost, orig_b)
        self.saved_policy_boost.clear()

        # B. Restore CPU max frequencies
        for freq_file, orig_freq in list(self.saved_cpu_freqs.items()):
            if os.path.exists(freq_file):
                self._write_sysfs(freq_file, orig_freq)
        self.saved_cpu_freqs.clear()

        # C. Restore CPU governors
        for gov_file, orig_gov in list(self.saved_cpu_governors.items()):
            if os.path.exists(gov_file):
                self._write_sysfs(gov_file, orig_gov)
        self.saved_cpu_governors.clear()

        # G. Restore CPU EPP
        for ep, orig_epp in list(self.saved_cpu_epp.items()):
            if os.path.exists(ep):
                target_epp = orig_epp if orig_epp and orig_epp != "power" else "balance_performance"
                self._write_sysfs(ep, target_epp)
        self.saved_cpu_epp.clear()

    def _restore_platform_profile(self):
        # D. Restore ACPI platform profile
        if self.saved_platform_profile and os.path.exists("/sys/firmware/acpi/platform_profile"):
            self._write_sysfs("/sys/firmware/acpi/platform_profile", self.saved_platform_profile)
            logger.info(f"Restored ACPI platform_profile to {self.saved_platform_profile}.")
        self.saved_platform_profile = None

        # E. Restore ASUS thermal policy
        for asus_thermal_file in [
            "/sys/devices/platform/asus-nb-wmi/throttle_thermal_policy",
            "/sys/devices/platform/asus_wmi/throttle_thermal_policy",
        ]:
            if self.saved_asus_thermal and os.path.exists(asus_thermal_file):
                self._write_sysfs(asus_thermal_file, self.saved_asus_thermal)
                logger.info(f"Restored ASUS thermal policy on {asus_thermal_file} to {self.saved_asus_thermal}.")
        self.saved_asus_thermal = None

        # E2. Restore the fan curve. Left in silent mode, the console throttles itself
        # and feels permanently slow long after the download is over.
        for fan_boost, orig_fan in list(self.saved_fan_boost.items()):
            if os.path.exists(fan_boost):
                self._write_sysfs(fan_boost, orig_fan)
                logger.info(f"Restored fan mode on {fan_boost} to {orig_fan}.")
        self.saved_fan_boost.clear()

        # F. Restore powerprofilesctl (only if this plugin changed it)
        if self.power_profile_set_by_us and shutil.which("powerprofilesctl"):
            target_profile = self.saved_power_profile or "balanced"
            try:
                subprocess.run(["powerprofilesctl", "set", target_profile], check=False, timeout=5.0)
                logger.info(f"Restored platform power profile to {target_profile}.")
            except Exception:
                pass
        self.saved_power_profile = None
        self.power_profile_set_by_us = False

    def _restore_gpu_settings(self):
        # Restore GPU DPM across all cards
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

    def _restore_audio(self):
        # Unmute audio, but only if this plugin muted it
        if self.audio_muted_by_us:
            self._set_audio_mute(False)
            self.audio_muted_by_us = False

    def _restore_leds(self):
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

    def _verify_and_force_restore(self) -> List[str]:
        """
        Last line of defence against a console left slow after waking up.

        Only checks things that can be measured on their own, with no saved state needed,
        and forces them back. The CPU frequency ceiling is deliberately NOT forced here:
        another tool (HHD's TDP control, PowerTools) may be capping it on purpose, and
        fighting it every wake would be its own bug. Anything this plugin set is restored
        from the saved values, or from the on-disk state file after a crash.
        """
        forced: List[str] = []

        # 1. The cgroup CPU quota: a leftover here throttles Steam until reboot.
        if self.last_cpu_quota_path and os.path.exists(self.last_cpu_quota_path):
            current = ""
            try:
                with open(self.last_cpu_quota_path, "r") as f:
                    current = f.read().strip()
            except Exception:
                pass
            if current and not current.startswith("max"):
                if self._write_sysfs(self.last_cpu_quota_path, f"max {CPU_QUOTA_PERIOD}"):
                    forced.append(f"cpu quota cleared on {self.last_cpu_quota_path} (was '{current}')")
        self.last_cpu_quota_path = ""

        # 2. Any ingress speed cap left on any interface, tracked or not.
        tc = self._tc_binary()
        if tc:
            for iface in self._network_interfaces(default_only=False):
                try:
                    if not self._tc_has_ingress(tc, iface):
                        continue
                    res = subprocess.run(
                        [tc, "qdisc", "del", "dev", iface, "ingress"],
                        capture_output=True, text=True, check=False, timeout=5.0,
                    )
                    if res.returncode == 0:
                        forced.append(f"download cap cleared on {iface}")
                except Exception:
                    pass

        # 3. Anything the restore stages should have emptied but did not.
        leftovers = {
            "cpu_freqs": len(self.saved_cpu_freqs),
            "cpu_governors": len(self.saved_cpu_governors),
            "cpu_epp": len(self.saved_cpu_epp),
            "gpu_dpm": len(self.saved_gpu_dpm),
            "asus_ppt": len(self.saved_asus_ppt),
            "fan_boost": len(self.saved_fan_boost),
            "brightness": len(self.saved_brightness),
            "leds": len(self.saved_leds),
        }
        pending = {k: v for k, v in leftovers.items() if v}
        if pending:
            forced.append(f"stages left values unrestored: {pending}")

        # 4. Record what the machine actually looks like now, so a report of "still slow"
        # can be diagnosed from the log instead of guessed at.
        if self.settings.get("debug_logging", True):
            cpu0 = "/sys/devices/system/cpu/cpu0/cpufreq"
            logger.info(
                "[DIB RESTORE CHECK] "
                f"scaling_max_freq={self._read_attr(cpu0, 'scaling_max_freq') or 'n/a'} "
                f"cpuinfo_max_freq={self._read_attr(cpu0, 'cpuinfo_max_freq') or 'n/a'} "
                f"governor={self._read_attr(cpu0, 'scaling_governor') or 'n/a'} "
                f"epp={self._read_attr(cpu0, 'energy_performance_preference') or 'n/a'} "
                f"boost={self._read_attr('/sys/devices/system/cpu/cpufreq', 'boost') or 'n/a'} "
                f"platform_profile={self._read_attr('/sys/firmware/acpi', 'platform_profile') or 'n/a'} "
                f"ppt={[f'{os.path.basename(p)}={self._read_attr(os.path.dirname(p), os.path.basename(p))}' for p in glob.glob('/sys/devices/platform/asus-nb-wmi/ppt_*')] or 'n/a'} "
                f"gpu_dpm={[self._read_attr(os.path.dirname(p), 'power_dpm_force_performance_level') for p in glob.glob('/sys/class/drm/card*/device/power_dpm_force_performance_level')] or 'n/a'} "
                f"forced={forced or 'nothing'}"
            )
        return forced

    # ==========================================
    # Background Mode Transitions
    # ==========================================
    async def enter_background_mode(self, reason: str = "manual") -> bool:
        if self.is_background_mode:
            return True

        now = time.time()
        # Do not enter background mode if wake cooldown is active!
        if now < self.wake_cooldown_until:
            logger.info(f"Blocked enter_background_mode (reason: {reason}) because system just woke up.")
            return False

        logger.info(f"Entering Background Download Mode (reason: {reason}).")
        self.is_background_mode = True
        self.background_mode_entered_time = now
        self.last_loop_timestamp = now

        self._acquire_sleep_inhibitor()
        t0 = time.time()
        self.transition_in_progress = True
        try:
            await self.loop.run_in_executor(None, self._run_transition_locked, self._apply_power_saving_and_screen_off)
        finally:
            self.transition_in_progress = False
        logger.info(f"[DBG] Power saving applied in {time.time() - t0:.2f}s")

        # Reset loop timestamp immediately after setup to avoid false clock-jump
        self.last_loop_timestamp = time.time()

        await decky.emit("background_mode_changed", {"is_background_mode": True, "reason": reason})
        return True

    async def exit_background_mode(self, reason: str = "manual") -> bool:
        if not self.is_background_mode:
            logger.info(f"[DBG] exit_background_mode({reason}) ignored: not in background mode.")
            return False

        logger.info(f"Exiting Background Download Mode (reason: {reason}).")
        self.wake_cooldown_until = time.time() + WAKE_COOLDOWN_SECONDS
        self.is_background_mode = False
        t0 = time.time()
        self.transition_in_progress = True
        try:
            await self.loop.run_in_executor(None, self._run_transition_locked, self._restore_system_power_and_display)
        finally:
            self.transition_in_progress = False
        logger.info(f"[DBG] System restored in {time.time() - t0:.2f}s")
        self._update_inhibitor_state()

        await decky.emit("background_mode_changed", {"is_background_mode": False, "reason": reason})
        return True

    def _run_transition_locked(self, func):
        """Serializes enter/exit hardware transitions so restore never races a half-finished apply."""
        with self.transition_lock:
            try:
                func()
            except Exception as e:
                logger.error(f"[DBG] Transition {func.__name__} failed: {e}")
                if func == self._restore_system_power_and_display:
                    # A restore that died halfway must never leave input grabbed or the
                    # controller daemons frozen: recovering from that needs a reboot.
                    try:
                        self._release_all_gamepad_inputs()
                    except Exception as inner:
                        logger.error(f"Emergency input release also failed: {inner}")

    async def trigger_suspend(self):
        logger.info("Executing systemctl suspend...")
        # Makes _plugin_should_act() False, so the power key listener hands the button
        # back to logind and the inhibitor is dropped before suspend is requested.
        self.suspend_in_progress = True
        try:
            if self.is_background_mode:
                self.is_background_mode = False
                await self.loop.run_in_executor(None, self._run_transition_locked, self._restore_system_power_and_display)

            self._release_sleep_inhibitor()
            self._clear_stale_sleep_masks()
            # Give the listener thread (0.3s poll) time to release the power device.
            await asyncio.sleep(1.0)

            try:
                subprocess.run(["systemctl", "suspend"], check=False, timeout=15.0)
            except Exception as e:
                logger.error(f"Failed to execute systemctl suspend: {e}")
            # Stay out of the way while the kernel actually goes down and comes back.
            await asyncio.sleep(2.0)
        finally:
            self.suspend_in_progress = False
            self.wake_cooldown_until = max(self.wake_cooldown_until, time.time() + WAKE_COOLDOWN_SECONDS)

    # ==========================================
    # Periodic Background Loop (Download & Battery)
    # ==========================================
    async def _background_monitor_loop(self):
        logger.info("Starting background monitor loop...")
        self.last_loop_timestamp = time.time()
        interval = ACTIVE_LOOP_INTERVAL
        while not self.stop_threads:
            try:
                await asyncio.sleep(interval)

                now = time.time()
                dt = now - self.last_loop_timestamp
                self.last_loop_timestamp = now
                enabled = bool(self.settings.get("enabled", True))
                slept_for = interval

                # Poll fast only when there is something to watch over. Idle means the
                # plugin stays out of the way and barely touches the disk.
                if not enabled:
                    interval = DISABLED_LOOP_INTERVAL
                elif self.is_background_mode or self._is_active_download():
                    interval = ACTIVE_LOOP_INTERVAL
                else:
                    interval = IDLE_LOOP_INTERVAL

                # 0. Kernel Sleep Resume Detection: a gap far larger than the sleep we
                # just did means the machine was actually suspended in between.
                time_in_bg = (now - self.background_mode_entered_time) if self.is_background_mode else 999.0
                if dt > (slept_for + 10.0) and time_in_bg > 10.0:
                    logger.info(
                        f"System wake from kernel suspend detected (dt={dt:.1f}s, time_in_bg={time_in_bg:.1f}s)! "
                        "Enforcing wake cooldown and exiting background mode."
                    )
                    self.wake_cooldown_until = now + WAKE_COOLDOWN_SECONDS
                    if self.is_background_mode:
                        self.is_background_mode = False
                        self.transition_in_progress = True
                        try:
                            await self.loop.run_in_executor(
                                None, self._run_transition_locked, self._restore_system_power_and_display
                            )
                        finally:
                            self.transition_in_progress = False
                        self._update_inhibitor_state()
                        await decky.emit("background_mode_changed", {
                            "is_background_mode": False,
                            "reason": "system_resume_clock_jump",
                        })

                if not enabled:
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
                if not frontend_active:
                    # Always recompute: a stuck is_paused=True used to keep the plugin
                    # from ever protecting a download again.
                    self.download_info["is_paused"] = bool(detector_paused and not is_dl)

                if is_dl:
                    self.last_download_active_time = now
                    if net_rx > 0:
                        self.download_info["bytes_per_second"] = max(net_rx, self.download_info.get("bytes_per_second", 0))

                # Sync inhibitor state
                self._update_inhibitor_state()

                # Safety net: input must never stay blocked outside background mode.
                # A dead console is the worst failure this plugin could cause, so it is
                # checked every pass rather than trusted to the exit path alone.
                if not self.is_background_mode and not self.transition_in_progress and (
                    self.inhibited_inputs or self.grabbed_gamepad_fds
                ):
                    logger.warning("Input was still blocked outside background mode; releasing it now.")
                    self._uninhibit_all_inputs()
                    self._release_all_gamepad_inputs()

                # 2. In Background Mode Checks
                if self.is_background_mode and not self.transition_in_progress:
                    # Keep the panels we dimmed dark (Steam re-lights them on its own)
                    for bp in list(self.saved_brightness.keys()):
                        bpow = os.path.join(os.path.dirname(bp), "bl_power")
                        try:
                            with open(bp, "r") as f:
                                if int(f.read().strip()) > 0:
                                    self._write_sysfs(bp, "0")
                        except Exception:
                            pass
                        try:
                            with open(bpow, "r") as pf:
                                if pf.read().strip() != "4":
                                    self._write_sysfs(bpow, "4")
                        except Exception:
                            pass

                    # Keep the lockout airtight: drop anything buffered, and grab plus
                    # inhibit devices that showed up after entering (a pad waking up, a
                    # recreated virtual controller) so they cannot reach Steam either.
                    self._flush_grabbed_inputs()
                    self._grab_new_inputs()
                    self._inhibit_all_inputs()

                    if now - self.last_telemetry_time >= TELEMETRY_INTERVAL:
                        self.last_telemetry_time = now
                        self._log_power_telemetry()

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
                        auto_sleep_delay = max(30.0, float(self.settings.get("auto_suspend_delay_seconds", 120)))

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
