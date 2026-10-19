import os
import sys
import json
import glob
import time
import struct
import select
import fcntl
import re
import datetime
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
    # When True, the plugin force-enables itself whenever the device is plugged into AC.
    # Useful on a PC that is always on mains, or on a handheld the user only wants the
    # plugin active for while charging. Overrides a False "enabled" only on AC.
    "enable_plugin_when_plugged_in": False,
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
    "ui_recovery_on_wake": True,
    "auto_hard_reset_after_wake": True,
    # Quiet-hours option: during the period [start, end), replace the plugin's standby
    # with the real SteamOS sleep, as long as no download is active. The watchdog takes
    # care of restoring the hardware on the next wake. Values are minutes-of-day in
    # 10-minute steps (0..1430); the period wraps across midnight when end <= start
    # (so 23:00 - 07:00 means 23:00 through 06:59).
    "enter_real_sleep_after_time": True,
    "real_sleep_start_minutes": 0,     # 00:00
    "real_sleep_end_minutes": 420,     # 07:00
    # Programs the RTC to wake the console at end, then re-enters the plugin's own
    # standby so a controller can wake it as usual. Pure Linux kernel feature, works on
    # any handheld or PC that exposes /sys/class/rtc/rtc0/wakealarm.
    "wake_at_period_end": True,
    # Standby: turn the power button into "console off, wakes on a controller"
    "standby_on_power_off": True,
    # Advanced mode: when False, the UI hides anything that is not among the essentials.
    # The backend uses every option regardless of this flag; it only affects the panel.
    "advanced_mode": False,
    "wake_on_bluetooth_connect": True,
    "wake_on_controller_button": True,
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
# How long after a restore the plugin keeps checking that it stayed restored.
POST_RESTORE_WATCH_SECONDS = 25.0
# The permanent watchdog, in addition to the above: a periodic check for drift that
# happens later. Interval is on the Plugin class itself (WATCHDOG_PERIODIC_INTERVAL).
# ryzenadj limits at or below this many milliwatts can only be a leftover of the plugin's
# own 6 W cap: used by the snapshot (do not save as the originals) and the watchdog (re-apply
# the real originals when they drift back down). 10 W is well below any sane APU default,
# so a healthy machine never triggers.
RYZENADJ_SANE_FLOOR_MW = 10000

# Grace periods after entering background mode, before power/logind events count as a wake.
POWER_KEY_GRACE_SECONDS = 2.5
LOGIND_GRACE_SECONDS = 5.0

# A controller dropped on the way into standby may retry the connection on its own for a
# few seconds. Only a connection after this window counts as the user asking for the
# console back, so the console cannot wake itself up the moment it goes dark.
BT_CONNECT_GRACE_SECONDS = 12.0

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

# Input bus types as /sys/class/input/inputN/id/bustype reports them.
BUS_USB = "0003"
BUS_BLUETOOTH = "0005"

# The buttons that bring the console back from standby: Select/Back, Start/Menu and the
# big middle one (Guide / Home / PS / Xbox), whichever name the pad uses for it.
BTN_SELECT = 314
BTN_START = 315
BTN_MODE = 316
KEY_HOMEPAGE = 172
WAKE_BUTTON_CODES = {BTN_SELECT, BTN_START, BTN_MODE, KEY_HOMEPAGE}

# How long a controller's raw HID reports are watched to learn which bytes move on their
# own (analog sticks, gyros, sequence counters) before a change counts as a button press.
HIDRAW_LEARN_SECONDS = 1.5


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

        # Standby mode: the console is "off" but awake, waiting for a controller.
        self.standby_mode: bool = False
        self.wake_event_fds: Dict[str, int] = {}
        self.wake_hidraw_fds: Dict[str, int] = {}
        self.wake_source_paths: Set[str] = set()
        self.hidraw_state: Dict[str, Dict[str, Any]] = {}
        self.standby_known_gamepads: Set[str] = set()
        self.wake_watcher_thread: Optional[threading.Thread] = None

        # Download pacing state, both reversible and recorded on disk so a crash mid
        # session can still be undone on the next start.
        self.saved_cpu_quota: Optional[Tuple[str, str]] = None
        self.last_cpu_quota_path: str = ""
        # Kept for a short while after a restore, so a firmware that re-applies its own
        # limits a second or two later does not get the last word.
        self.post_restore_targets: Dict[str, str] = {}
        self.post_restore_marks: Dict[str, str] = {}
        self.post_restore_until: float = 0.0
        # Permanent throttle watchdog. Known-good targets and the throttled values the
        # plugin is known to have written, so a stuck setting can be told apart from
        # another tool's choice. Updated at the END of each successful restore, kept for
        # the whole plugin session (and across reloads, through the on-disk state).
        self.watchdog_targets: Dict[str, str] = {}
        self.watchdog_marks: Dict[str, str] = {}
        self.watchdog_ryzenadj: Dict[str, int] = {}
        self.last_watchdog_check: float = 0.0
        # The "once per wake, then periodic check" state the user asked for. The post-wake
        # auto-reset runs 8 s after each exit from the mode. Any later re-run from the
        # periodic check is suppressed for 2 minutes afterwards, so the hard reset is not
        # repeated for the same cycle. See _throttle_watchdog.
        self.last_wake_time: float = 0.0
        self.last_auto_hard_reset_time: float = 0.0
        # RTC-based wake-at-end-of-quiet-hours. Persisted across plugin reloads so the
        # resume handler still fires if the plugin was reloaded during the sleep.
        self.rtc_wake_pending: bool = False
        self.rtc_wake_target: int = 0
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
        self.sleep_targets_masked: bool = False
        self.standby_request_pending: bool = False

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
        # path -> the value this plugin wrote there. What makes it possible to tell
        # "the machine is still throttled by me" from "the user set it that way".
        self.applied_marks: Dict[str, str] = {}
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

        # 3. Standby wake watcher (controllers asking for the console back)
        self.wake_watcher_thread = threading.Thread(
            target=self._standby_wake_watcher_worker,
            daemon=True,
            name="DownloadInBackground-WakeWatcher"
        )
        self.wake_watcher_thread.start()

        # 4. Main periodic monitor loop
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
                self._migrate_legacy_settings()
            else:
                self._save_settings_sync()
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")

    def _migrate_legacy_settings(self):
        """One-shot upgrades for keys whose names or units changed between versions."""
        changed = False
        # real_sleep_{start,end}_hour (0..23) -> real_sleep_{start,end}_minutes (0..1430)
        if "real_sleep_start_hour" in self.settings:
            try:
                self.settings["real_sleep_start_minutes"] = (
                    int(self.settings["real_sleep_start_hour"]) * 60
                )
            except (TypeError, ValueError):
                pass
            self.settings.pop("real_sleep_start_hour", None)
            changed = True
        if "real_sleep_end_hour" in self.settings:
            try:
                self.settings["real_sleep_end_minutes"] = (
                    int(self.settings["real_sleep_end_hour"]) * 60
                )
            except (TypeError, ValueError):
                pass
            self.settings.pop("real_sleep_end_hour", None)
            changed = True
        if changed:
            try:
                self._save_settings_sync()
            except Exception:
                pass

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

        if not self._effective_enabled() and self.is_background_mode:
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
            "standby_mode": self.standby_mode,
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

        Earlier versions masked these targets to stop the power menu's Sleep from going
        through. It did stop it, but in the worst possible way: Steam had already begun
        its own suspend sequence and blanked the screen, the suspend then failed, and the
        session was left on a black lit screen it could never come back from.

        The menu is intercepted in the Steam client itself now, before any of that, so
        nothing is ever masked. This only cleans up masks left behind by those versions
        (and a plugin crash), which is also why it runs at startup. Permanent masks the
        user made live in /etc and are not touched by --runtime.
        """
        stale = [t for t in self.SLEEP_TARGETS if os.path.islink(f"/run/systemd/system/{t}")]
        self.sleep_targets_masked = False
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

    def _refresh_download_state(self) -> bool:
        """
        Reads the real download state now and returns whether one is actually running.

        Called from the monitor loop and, importantly, the instant the user asks to sleep:
        pausing a download rewrites its appmanifest immediately, so reading it right then
        catches a pause made a second ago instead of waiting for the next poll. That is
        the difference between the plugin showing the download card and letting the
        console go into standby as the user intended.
        """
        now = time.time()
        info = self.detector.detect()
        detector_is_dl = bool(info.get("is_downloading", False))
        detector_paused = bool(info.get("is_paused", False))
        net_rx = self.detector.get_network_rx_rate()

        # Did the frontend report an active download recently? Its own report is dropped
        # the moment Steam says paused, so a stale "downloading" cannot survive a pause.
        frontend_active = (
            (now - self.last_frontend_dl_time < 30.0)
            and bool(self.download_info.get("is_downloading", False))
            and not bool(self.download_info.get("is_paused", False))
            and not detector_paused
        )

        is_dl = (
            (detector_is_dl and not detector_paused)
            or frontend_active
            or (net_rx > 30000 and not detector_paused)
        )

        # If the detector provided richer info (game title, progress), keep it
        if not frontend_active and info:
            self.download_info.update(info)

        self.download_info["is_downloading"] = is_dl
        if not frontend_active:
            # Always recompute: a stuck is_paused=True used to keep the plugin from ever
            # protecting a download again.
            self.download_info["is_paused"] = bool(detector_paused and not is_dl)

        if is_dl:
            self.last_download_active_time = now
            if net_rx > 0:
                self.download_info["bytes_per_second"] = max(
                    net_rx, self.download_info.get("bytes_per_second", 0)
                )
        return is_dl

    def _effective_enabled(self) -> bool:
        """
        True iff the plugin should behave as enabled right now.

        The user-facing 'Enable Plugin' toggle is the baseline. 'Enable Plugin When
        Plugged In' is an overriding opt-in that force-enables the plugin while on AC,
        even if the baseline toggle is off — meant for a desktop PC permanently plugged
        in, or a handheld the user only wants the plugin active for while charging.
        """
        if self.settings.get("enabled", True):
            return True
        if self.settings.get("enable_plugin_when_plugged_in", False):
            try:
                bat = self._get_battery_info()
                if bat and bat.get("is_plugged"):
                    return True
            except Exception:
                pass
        return False

    def _plugin_should_act(self) -> bool:
        """
        The single answer to 'may the plugin touch the system right now?'.

        With the plugin enabled but nothing downloading, this is False and SteamOS is
        left completely alone: no inhibitor, no grabbed power button, no masked targets,
        so the stock suspend animation and behaviour are exactly as without the plugin.

        Standby mode is the one exception: there the power button has to be ours at all
        times, because turning it into "console off, wakes on a controller" is the point.
        """
        if self.suspend_in_progress or not self._effective_enabled():
            return False
        if self.settings.get("standby_on_power_off", False):
            return True
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

        # Nothing is masked at the systemd level any more: the power menu's Sleep is taken
        # over inside the Steam client instead, before it ever reaches logind.

    # ==========================================
    # Suspend Interception & Logind Watcher
    # ==========================================
    def _trigger_suspend_intercepted(self, source: str = "unknown") -> str:
        """
        Called whenever a suspend attempt is detected while downloads are active.

        Returns the verdict, so the caller knows what happened: 'wake', 'ignored',
        'standby', 'hud', or 'allow' when the suspend should simply go ahead as usual.
        The Steam power menu needs that last answer: it is the one path where the plugin
        has to hand the suspend back after deciding not to take it.
        """
        now = time.time()
        time_in_bg = (now - self.background_mode_entered_time) if self.is_background_mode else 999.0
        # If currently in background mode, any suspend attempt after grace period is a WAKE action!
        if self.is_background_mode:
            if time_in_bg < LOGIND_GRACE_SECONDS:
                logger.info(f"Ignoring suspend intercept during background entry grace period ({time_in_bg:.1f}s).")
                return "ignored"
            logger.info("Suspend attempt detected while in background mode -> Waking system!")
            self.wake_cooldown_until = now + WAKE_COOLDOWN_SECONDS
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.exit_background_mode("suspend_attempt_wake"),
                    self.loop
                )
            return "wake"

        # Cooldown: Ignore any suspend request if system just woke up within 12 seconds
        if now < self.wake_cooldown_until:
            logger.info("Ignoring suspend attempt because system just woke up from background mode.")
            return "ignored"

        # Double check against the real state, not the last poll: a download paused a
        # moment ago must already count as idle here.
        if not self._refresh_download_state():
            if self.settings.get("standby_on_power_off", False):
                if now - self.last_suspend_intercept_time < 3.0:
                    return "ignored"
                self.last_suspend_intercept_time = now
                logger.info(
                    f"[DIB SLEEP SOURCE] Sleep requested from '{source}' with standby enabled "
                    "-> standby splash, then entering."
                )
                if self.loop and self.loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self.request_standby(f"standby_{source}"), self.loop
                    )
                return "standby"
            logger.info("Suspend attempt not intercepted: Download is paused or idle. Allowing normal suspend.")
            # The inhibitor goes first, or the suspend we just allowed would be blocked.
            self._update_inhibitor_state()
            return "allow"

        # Debounce to prevent double trigger within 3 seconds
        if now - self.last_suspend_intercept_time < 3.0:
            return "ignored"
        self.last_suspend_intercept_time = now

        logger.info(f"[DIB SLEEP SOURCE] Suspend attempt from '{source}' intercepted while downloading -> Showing HUD!")
        self._acquire_sleep_inhibitor()

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                decky.emit("on_suspend_intercepted", {
                    "download_info": self.download_info,
                    "hud_timeout": self.settings.get("hud_timeout_seconds", 5),
                }),
                self.loop
            )
        return "hud"

    RTC_WAKEALARM = "/sys/class/rtc/rtc0/wakealarm"

    def _quiet_hours_bounds(self) -> Optional[Tuple[int, int]]:
        """
        (start_minutes_of_day, end_minutes_of_day) when the option is on and valid.

        Values are 0..1430, snapped to 10-minute steps so the slider's values and the
        bounds always line up. An empty period (start == end) returns None.
        """
        if not self.settings.get("enter_real_sleep_after_time", False):
            return None
        try:
            start = int(self.settings.get("real_sleep_start_minutes", 0))
            end = int(self.settings.get("real_sleep_end_minutes", 420))
        except (TypeError, ValueError):
            return None
        start = max(0, min(1430, (start // 10) * 10))
        end = max(0, min(1430, (end // 10) * 10))
        if start == end:
            return None
        return (start, end)

    def _inside_quiet_hours(self) -> bool:
        """
        True when the clock is inside the user's quiet-hours period.

        Period is [start, end): the start minute counts, the end minute does not.
        Natural wrap-around for a period that crosses midnight: 23:00 - 07:00 means
        23:00 through 06:59, so 02:00 is inside and 07:00 is outside.
        """
        bounds = self._quiet_hours_bounds()
        if not bounds:
            return False
        start, end = bounds
        now = datetime.datetime.now()
        current = now.hour * 60 + now.minute
        if start < end:
            return start <= current < end
        return current >= start or current < end

    def _next_quiet_hours_end(self) -> Optional[int]:
        """Unix epoch of the next time the quiet-hours period ends."""
        bounds = self._quiet_hours_bounds()
        if not bounds:
            return None
        _start, end = bounds
        end_hour, end_min = divmod(end, 60)
        now = datetime.datetime.now()
        target = now.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        return int(target.timestamp())

    def _schedule_rtc_wake(self, epoch_time: int) -> bool:
        """
        Programs the real-time clock to wake the console at the given Unix time.

        Standard kernel interface, works on any handheld or desktop that exposes it.
        Writing "0" first is required: the kernel refuses a new alarm while one is still
        armed, so clearing before setting is the only reliable way.
        """
        if not os.path.exists(self.RTC_WAKEALARM):
            logger.info("RTC wakealarm not available; cannot schedule a wake.")
            return False
        if epoch_time <= time.time() + 30:
            logger.info(f"RTC wake refused: {epoch_time} is too close to now.")
            return False
        if not self._write_sysfs(self.RTC_WAKEALARM, "0"):
            return False
        time.sleep(0.1)
        if not self._write_sysfs(self.RTC_WAKEALARM, str(int(epoch_time))):
            return False
        logger.info(
            f"RTC wake armed for {datetime.datetime.fromtimestamp(epoch_time).isoformat()} "
            f"(in {int(epoch_time - time.time())} s)."
        )
        return True

    def _clear_rtc_wake(self):
        """Disarms the RTC alarm. Safe to call even if nothing was armed."""
        if os.path.exists(self.RTC_WAKEALARM):
            try:
                self._write_sysfs(self.RTC_WAKEALARM, "0")
            except Exception:
                pass
        self.rtc_wake_pending = False
        self.rtc_wake_target = 0

    async def _maybe_real_sleep_instead(self, reason: str) -> bool:
        """
        Inside the quiet-hours period with nothing downloading, runs the real SteamOS
        sleep instead of entering the plugin's own mode. If the wake-at-end option is on,
        also programs the RTC to wake the console at the end of the period, where the
        resume handler will put it back into the plugin's standby. Returns True when it
        took the sleep over.
        """
        if not self._inside_quiet_hours():
            return False
        if self._is_active_download():
            logger.info(
                "[DIB QUIET HOURS] Inside the period, but a download is active; "
                "entering the plugin's own mode as usual."
            )
            return False
        bounds = self._quiet_hours_bounds()
        logger.info(
            f"[DIB QUIET HOURS] Inside the period ({bounds[0]:02d}:00 - {bounds[1]:02d}:00) "
            f"and nothing is downloading (reason: {reason}) -> real SteamOS sleep."
        )
        if self.settings.get("wake_at_period_end", False):
            end_epoch = self._next_quiet_hours_end()
            if end_epoch and self._schedule_rtc_wake(end_epoch):
                self.rtc_wake_pending = True
                self.rtc_wake_target = end_epoch
                self._save_runtime_state()
        await self.trigger_suspend()
        return True

    async def _enter_standby_after_rtc_wake(self):
        """
        Called after a resume that was triggered by the RTC alarm the plugin set up at the
        start of a quiet-hours sleep. Short delay so the kernel finishes bringing the
        hardware back, then enters the plugin's standby for a controller to wake later.
        """
        await asyncio.sleep(3.0)
        if self.is_background_mode:
            return
        if not self.settings.get("standby_on_power_off", False):
            logger.info("[DIB RTC WAKE] Standby option is off; staying awake.")
            return
        if self._inside_quiet_hours():
            # Still inside the window somehow (user widened it after sleeping): a plain
            # real sleep is correct again.
            logger.info("[DIB RTC WAKE] Woke inside the quiet-hours window; running real sleep again.")
            await self.trigger_suspend()
            return
        logger.info("[DIB RTC WAKE] Quiet-hours ended; entering the plugin's standby.")
        await self.request_standby("quiet_hours_rtc_end")

    async def request_standby(self, reason: str = "standby") -> bool:
        """
        Shows the standby splash first, then enters the mode.

        The splash has to be drawn while the panel is still lit. Entering the mode first
        and drawing after put the logo on a screen whose backlight was already at zero,
        which is why nothing appeared to show up at all.
        """
        if self.is_background_mode or self.standby_request_pending:
            return False
        if time.time() < self.wake_cooldown_until:
            logger.info("Standby request ignored: the console just woke up.")
            return False

        # Quiet-hours short-circuit: before entering our mode, run the real SteamOS
        # sleep if the configured hour has passed and no download is active.
        if await self._maybe_real_sleep_instead(reason):
            return False

        self.standby_request_pending = True
        try:
            splash_seconds = max(0, int(self.settings.get("hud_timeout_seconds", 5)))
            await decky.emit("on_standby_requested", {
                "splash_seconds": splash_seconds,
                "reason": reason,
            })
            if splash_seconds <= 0:
                return await self.enter_background_mode(reason)

            # The frontend draws the splash and then enters. If it never does (not
            # running, or an error), the mode is entered here so the power button is
            # never a no-op.
            await asyncio.sleep(splash_seconds + 2.5)
            if not self.is_background_mode and time.time() >= self.wake_cooldown_until:
                logger.info("Frontend did not enter standby in time; entering from the backend.")
                return await self.enter_background_mode(reason)
            return True
        finally:
            self.standby_request_pending = False

    async def trigger_suspend_intercept(self) -> Dict[str, Any]:
        """
        API called by the frontend when the Steam client intercepts a suspend.

        The verdict comes back because the frontend is the only one that can hand a
        suspend over to SteamOS after the fact: when this says 'allow', the Steam power
        menu's Sleep has to go through as usual.
        """
        verdict = self._trigger_suspend_intercepted("frontend_hook")
        return {
            "verdict": verdict,
            "intercepted": verdict in ("hud", "standby", "wake"),
            "download_info": self.download_info,
        }

    def _system_still_capped_signs(self) -> List[str]:
        """
        Looks for signs that the plugin's own throttle is still in place.

        Only used as a trigger for the automatic hard reset, so it has to be conservative:
        a false positive would bounce the ACPI profile without reason, and that is a
        firmware event the user feels. Only values this plugin is known to have set are
        counted - anything an external tool wrote is left alone.

        Covers every scenario the plugin applies throttles to, from a handheld AMD APU
        (ROG Ally, Steam Deck) to a desktop PC with a dedicated GPU. The handheld-only
        checks (ryzenadj, platform_profile) sit quietly on hardware that does not have
        them, so a desktop pays nothing for their presence here.
        """
        signs: List[str] = []

        # 1. CPU scaling_max_freq pinned at the plugin's cap. The cap is the min_freq of
        # the CPU, so a healthy system is ALWAYS above it; a user-chosen lower ceiling
        # from PowerTools is above it too, because it never equals it exactly.
        min_target = self._cpu_min_freq_target()
        for path in self._cpu_freq_files():
            if self._read_text(path) == min_target:
                signs.append(f"{os.path.basename(path)}={min_target}")
                break

        # 2. CPU turbo boost still off AND we had a baseline that said it should be on.
        boost = self._read_text(self.CPU_BOOST_FILE) if os.path.exists(self.CPU_BOOST_FILE) else ""
        if boost == "0" and self.watchdog_targets.get(self.CPU_BOOST_FILE) == "1":
            signs.append("boost=0")

        # 3. ryzenadj limits at or near our cap. 10 W is well below any sane APU default.
        if shutil.which("ryzenadj"):
            limits = self._read_ryzenadj_limits()
            if limits and any(
                0 < limits.get(k, 999999) <= RYZENADJ_SANE_FLOOR_MW
                for k in ("stapm-limit", "fast-limit", "slow-limit")
            ):
                signs.append(f"ryzenadj={limits}")

        # 4. The ACPI platform profile still at a low-power choice when we had the
        # baseline saying it should be balanced/performance.
        if os.path.exists(self.PLATFORM_PROFILE_FILE):
            now_profile = self._read_text(self.PLATFORM_PROFILE_FILE)
            baseline = self.watchdog_targets.get(self.PLATFORM_PROFILE_FILE)
            if now_profile in ("quiet", "low-power") and baseline and baseline != now_profile:
                signs.append(f"platform_profile={now_profile}")

        # 5. GPU DPM level still at "low" when the baseline said otherwise. Covers desktop
        # PCs with a dedicated AMD GPU, where this is the biggest performance hit.
        for path in glob.glob("/sys/class/drm/card*/device/power_dpm_force_performance_level"):
            if self._read_text(path) != "low":
                continue
            baseline = self.watchdog_targets.get(path)
            if baseline and baseline != "low":
                signs.append(f"gpu_dpm=low")
                break

        # 6. CPU scaling governor stuck at "powersave" when the baseline said otherwise.
        # Only acts when the baseline exists, so a system that genuinely defaults to
        # "powersave" (amd-pstate) is not fought.
        for path in glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"):
            if self._read_text(path) != "powersave":
                continue
            baseline = self.watchdog_targets.get(path)
            if baseline and baseline != "powersave":
                signs.append(f"governor=powersave")
                break

        # 7. EPP stuck at "power" with the same guard: a baseline change is required.
        for path in glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference"):
            if self._read_text(path) != "power":
                continue
            baseline = self.watchdog_targets.get(path)
            if baseline and baseline != "power":
                signs.append(f"epp=power")
                break

        # 8. The cgroup v2 CPU quota: a leftover here throttles Steam to a fraction of a
        # core until the next reboot, which on a desktop is the single most noticeable cap.
        if self.last_cpu_quota_path and os.path.exists(self.last_cpu_quota_path):
            current = self._read_text(self.last_cpu_quota_path)
            if current and not current.startswith("max"):
                signs.append(f"cpu.max={current}")

        # 9. The tc ingress policer: a leftover caps every download on that interface at
        # a few megabytes per second, which looks like a terrible internet connection.
        tc = self._tc_binary()
        if tc:
            for iface in self._network_interfaces(default_only=False):
                if self._tc_has_ingress(tc, iface):
                    signs.append(f"tc_ingress={iface}")
                    break

        return signs

    async def _auto_hard_reset_after_wake(self, delay_seconds: float):
        """
        Scheduled 8 s after each wake. The user asked for exactly this: "ao voltar da
        suspensao, esperar uns 8 segundos e entao chamar o restore hardware".

        Runs unconditionally (does not check for signs first), because the manual button
        is what the user says works for them on the ROG Ally X - any detection logic that
        decides against running it when they want it run is wrong by their own report.

        Only one run per wake: the periodic watchdog honours a 2-minute cooldown after
        this fires, so the hard reset is not repeated for the same cycle. The periodic
        check is still there to catch a future problem, as asked for.
        """
        try:
            await asyncio.sleep(delay_seconds)
        except asyncio.CancelledError:
            return

        if self.is_background_mode or self.transition_in_progress:
            return
        if not self.settings.get("auto_hard_reset_after_wake", True):
            return

        logger.warning("[DIB AUTO-RESET] 8 s post-wake: running the hard reset.")
        try:
            done = await self.loop.run_in_executor(None, self._run_transition_locked_safe,
                                                   self._hard_reset_power_limits)
            self.last_auto_hard_reset_time = time.time()
            if done:
                logger.warning(f"[DIB AUTO-RESET] Repaired: {done}")
            else:
                logger.info("[DIB AUTO-RESET] Nothing needed repair.")
        except Exception as e:
            logger.error(f"[DIB AUTO-RESET] Failed: {e}")

    def _run_transition_locked_safe(self, func):
        """Non-throwing wrapper for a hardware repair run from a schedule."""
        try:
            with self.transition_lock:
                return func()
        except Exception as e:
            logger.error(f"Auto hardware repair {func.__name__} failed: {e}")
            return []

    def _hard_reset_power_limits(self) -> List[str]:
        """
        The heavy-handed repair, run only from the "Restore Hardware Now" button.

        Switching the ACPI profile makes the firmware rewrite its power limits, but
        switching it back does not reliably make it rewrite them again: the console ends
        up reporting the balanced profile while still running on the low-power PPT
        values. Bouncing the profile through another choice and back forces the firmware
        to apply the current one properly.

        The frequency ceiling is then raised to whatever the hardware says it can do,
        which also clears a ceiling the kernel left behind while turbo boost was off.
        This is the one place that overrules another tool's TDP settings, which is why it
        only ever happens when the user presses the button.
        """
        done: List[str] = []

        # 1. Turbo boost first: with it off, the kernel clamps the ceiling right back.
        boost_file = self.CPU_BOOST_FILE
        if os.path.exists(boost_file) and self._read_text(boost_file) == "0":
            if self._write_sysfs(boost_file, "1"):
                done.append("turbo boost re-enabled")
        for pb in glob.glob("/sys/devices/system/cpu/cpufreq/policy*/boost"):
            if self._read_text(pb) == "0":
                self._write_sysfs(pb, "1")

        # 2. Make the firmware re-apply the power limits of the current profile.
        current = self._read_text(self.PLATFORM_PROFILE_FILE)
        choices = self._read_text("/sys/firmware/acpi/platform_profile_choices").split()
        other = next((c for c in choices if c != current), "")
        if current and other:
            self._write_sysfs(self.PLATFORM_PROFILE_FILE, other)
            time.sleep(0.5)
            self._write_sysfs(self.PLATFORM_PROFILE_FILE, current)
            time.sleep(0.5)
            done.append(f"platform profile bounced through '{other}' back to '{current}'")

        # 3. Raise any ceiling still below what the hardware reports.
        raised = 0
        ceilings: Set[str] = set()
        for path in self._cpu_freq_files():
            ceiling = self._read_attr(os.path.dirname(path), "cpuinfo_max_freq")
            now_at = self._read_text(path)
            if ceiling.isdigit() and now_at.isdigit() and int(now_at) < int(ceiling):
                if self._write_sysfs(path, ceiling):
                    raised += 1
                    ceilings.add(f"{now_at}->{ceiling}")
        if raised:
            done.append(f"raised the frequency ceiling on {raised} node(s): {sorted(ceilings)}")

        # 4. GPU DPM: desktop PC with a dedicated AMD GPU usually feels this the most. If
        # any card is still at "low" and the baseline knew another value, put it back; the
        # safe generic fallback is "auto".
        for path in glob.glob("/sys/class/drm/card*/device/power_dpm_force_performance_level"):
            if self._read_text(path) != "low":
                continue
            baseline = self.watchdog_targets.get(path)
            target = baseline if baseline and baseline != "low" else "auto"
            if self._write_sysfs(path, target):
                done.append(f"gpu dpm {os.path.basename(os.path.dirname(path))}: low->{target}")

        # 5. CPU scaling governor stuck at "powersave" with a different baseline. On a
        # system where "powersave" is the real default (amd-pstate), the baseline matches
        # and this does nothing - which is correct.
        gov_fixed = 0
        for path in glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"):
            if self._read_text(path) != "powersave":
                continue
            baseline = self.watchdog_targets.get(path)
            if baseline and baseline != "powersave":
                if self._write_sysfs(path, baseline):
                    gov_fixed += 1
        if gov_fixed:
            done.append(f"restored CPU governor on {gov_fixed} node(s) to baseline")

        # 6. EPP: same rule. Default on most AMD systems is "balance_performance", on
        # Intel often "balance_performance" or "performance".
        epp_fixed = 0
        for path in glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference"):
            if self._read_text(path) != "power":
                continue
            baseline = self.watchdog_targets.get(path)
            target = baseline if baseline and baseline != "power" else "balance_performance"
            if self._write_sysfs(path, target):
                epp_fixed += 1
        if epp_fixed:
            done.append(f"restored EPP on {epp_fixed} node(s)")

        # 7. The cgroup CPU quota: a leftover here throttles Steam until the next reboot.
        # Writing "max 100000" uncaps it. This is the single most impactful thing to clear
        # on a desktop PC with the plugin's download pacing enabled.
        if self.last_cpu_quota_path and os.path.exists(self.last_cpu_quota_path):
            current = self._read_text(self.last_cpu_quota_path)
            if current and not current.startswith("max"):
                if self._write_sysfs(self.last_cpu_quota_path, f"max {CPU_QUOTA_PERIOD}"):
                    done.append(f"cleared cpu.max on {self.last_cpu_quota_path} (was '{current}')")

        # 8. The tc ingress policer: a leftover caps every download on that interface.
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
                        done.append(f"cleared tc ingress on {iface}")
                except Exception:
                    pass

        if done:
            logger.warning(f"[DIB HARD RESET] {done}")
        return done

    async def force_restore(self) -> Dict[str, Any]:
        """
        Puts the hardware back right now, whether or not the plugin thinks it is in the
        mode, and replays anything a previous session left on disk.

        The escape hatch for a console that came back slow: without it the only way out
        is a reboot, and a reboot also destroys the evidence.
        """
        logger.warning("Force restore requested from the plugin menu.")
        was_bg = self.is_background_mode
        self.is_background_mode = False
        self.standby_mode = False
        self.wake_cooldown_until = time.time() + WAKE_COOLDOWN_SECONDS
        self.transition_in_progress = True
        try:
            await self.loop.run_in_executor(None, self._run_transition_locked, self._heal_runtime_state)
            await self.loop.run_in_executor(
                None, self._run_transition_locked, self._restore_system_power_and_display
            )
        finally:
            self.transition_in_progress = False
        hard = await self.loop.run_in_executor(None, self._hard_reset_power_limits)
        self._clear_stale_sleep_masks()
        self._update_inhibitor_state()
        if was_bg:
            await decky.emit("background_mode_changed", {
                "is_background_mode": False,
                "reason": "force_restore",
            })
        return {"ok": True, "was_background_mode": was_bg, "hard_reset": hard}

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

                        # Quiet-hours RTC wake handling: a resume near the time we armed
                        # the RTC for is almost certainly our RTC alarm firing. Re-enter
                        # the plugin's standby so a controller can wake it as usual.
                        if self.rtc_wake_pending:
                            diff = abs(now - self.rtc_wake_target)
                            if diff <= 120:
                                logger.info(
                                    f"[DIB RTC WAKE] Resume at {int(now)}, target was "
                                    f"{self.rtc_wake_target} (diff {diff:.1f}s) -> entering standby."
                                )
                                self.rtc_wake_pending = False
                                self.rtc_wake_target = 0
                                if self.loop and self.loop.is_running():
                                    asyncio.run_coroutine_threadsafe(
                                        self._enter_standby_after_rtc_wake(), self.loop
                                    )
                                continue
                            else:
                                logger.info(
                                    f"[DIB RTC WAKE] Resume at {int(now)} is far from the "
                                    f"RTC target {self.rtc_wake_target} (diff {diff:.1f}s); "
                                    "treating as a manual wake and clearing the alarm."
                                )
                                self._clear_rtc_wake()

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
                            self._trigger_suspend_intercepted("logind_journal")
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
        if not self._effective_enabled():
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

    ASUS_PPT_FILES = (
        "/sys/devices/platform/asus-nb-wmi/ppt_pl1_spl",
        "/sys/devices/platform/asus-nb-wmi/ppt_pl2_sppt",
        "/sys/devices/platform/asus-nb-wmi/ppt_fppt",
        "/sys/class/firmware-attributes/asus-armoury/attributes/ppt_pl1_spl/current_value",
        "/sys/class/firmware-attributes/asus-armoury/attributes/ppt_pl2_sppt/current_value",
        "/sys/class/firmware-attributes/asus-armoury/attributes/ppt_fppt/current_value",
    )
    ASUS_THERMAL_FILES = (
        "/sys/devices/platform/asus-nb-wmi/throttle_thermal_policy",
        "/sys/devices/platform/asus_wmi/throttle_thermal_policy",
    )
    PLATFORM_PROFILE_FILE = "/sys/firmware/acpi/platform_profile"
    CPU_BOOST_FILE = "/sys/devices/system/cpu/cpufreq/boost"

    def _read_text(self, path: str) -> str:
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except Exception:
            return ""

    def _platform_profile_target(self) -> str:
        choices = self._read_text("/sys/firmware/acpi/platform_profile_choices")
        return "quiet" if "quiet" in choices else ("low-power" if "low-power" in choices else "balanced")

    def _cpu_min_freq_target(self) -> str:
        min_freq = "800000"
        for min_file in ("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq",
                         "/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq"):
            val = self._read_text(min_file)
            if val.isdigit() and int(val) > 0:
                return str(max(600000, int(val)))
        return min_freq

    def _cpu_freq_files(self) -> Set[str]:
        return set(
            glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq")
            + glob.glob("/sys/devices/system/cpu/cpufreq/policy*/scaling_max_freq")
        )

    def _snapshot_power_originals(self):
        """
        Reads every value the low-power pass is about to change, BEFORE changing any of
        them.

        This is the difference between waking up to a 5.1 GHz, 30 W console and waking up
        to a 3.3 GHz, 5 W one. Several of these settings move each other:

          - turning turbo boost off makes the kernel drop scaling_max_freq to the
            non-boost nominal (5134889 -> 3301000 on this APU);
          - switching the ACPI profile to low-power makes the firmware rewrite every PPT
            limit (30 W -> 5 W).

        Reading each value immediately before overwriting it therefore captured a number
        this plugin had itself just caused, and "restoring" wrote the throttled values
        back in for good - a console that came back slow with every check reporting
        success, because every value really was back to what had been recorded.

        Everything is read up front here. The saves further down keep the first value
        recorded for a path, so they become no-ops.
        """
        if self.settings.get("throttle_cpu", True):
            profile = self._read_text(self.PLATFORM_PROFILE_FILE)
            if profile:
                self._save_original_scalar(
                    "saved_platform_profile", profile,
                    self._platform_profile_target(), self.PLATFORM_PROFILE_FILE,
                )
            for path in self.ASUS_THERMAL_FILES:
                if os.path.exists(path):
                    current = self._read_text(path)
                    if current:
                        self._save_original_scalar("saved_asus_thermal", current, "2", path)
            for path in glob.glob("/sys/devices/platform/asus*/fan_boost_mode"):
                current = self._read_text(path)
                if current:
                    self._save_original(self.saved_fan_boost, path, current, "2")
            for path in self.ASUS_PPT_FILES:
                if os.path.exists(path):
                    current = self._read_text(path)
                    if current:
                        self._save_original(self.saved_asus_ppt, path, current, "6")

            boost_file = self.CPU_BOOST_FILE
            if os.path.exists(boost_file):
                current = self._read_text(boost_file)
                if current:
                    self._save_original_scalar("saved_cpu_boost", current, "0", boost_file)
            for path in glob.glob("/sys/devices/system/cpu/cpufreq/policy*/boost"):
                current = self._read_text(path)
                if current:
                    self._save_original(self.saved_policy_boost, path, current, "0")

            min_freq = self._cpu_min_freq_target()
            for path in self._cpu_freq_files():
                current = self._read_text(path)
                if current:
                    self._save_original(self.saved_cpu_freqs, path, current, min_freq)
            for path in set(
                glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor")
                + glob.glob("/sys/devices/system/cpu/cpufreq/policy*/scaling_governor")
            ):
                current = self._read_text(path)
                if current:
                    self._save_original(self.saved_cpu_governors, path, current, "powersave")
            for path in set(
                glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference")
                + glob.glob("/sys/devices/system/cpu/cpufreq/policy*/energy_performance_preference")
            ):
                current = self._read_text(path)
                if current:
                    self._save_original(self.saved_cpu_epp, path, current, "power")

        if self.settings.get("throttle_gpu", True):
            for path in glob.glob("/sys/class/drm/card*/device/power_dpm_force_performance_level"):
                current = self._read_text(path)
                if current:
                    self._save_original(self.saved_gpu_dpm, path, current, "low")

        # ryzenadj HAS to be snapshotted here, same as everything else - and for the same
        # reason. Reading `ryzenadj -i` in the apply section used to come AFTER the ACPI
        # profile had been dropped to low-power, which makes the firmware re-apply its
        # own clock and power limits. The read therefore returned the already-throttled
        # STAPM/PPT values, those got saved as the originals, and restore wrote them back
        # on wake. Each cycle recorded a slightly lower "original", so after a few runs
        # the console sat at the low-power profile's defaults until the next reboot.
        if (self.settings.get("throttle_cpu", True) and shutil.which("ryzenadj")
                and self.saved_ryzenadj is None):
            limits = self._read_ryzenadj_limits()
            if limits:
                # Guard against a failed restore from the previous cycle: if the limits are
                # already at or below the plugin's own cap, they can only be the leftover
                # of that cap, and saving them here would make the next restore write them
                # back for good. Reuse the watchdog's known-good baseline when it has one,
                # otherwise skip ryzenadj for this cycle entirely (no cap, no "restore"
                # that would permanently throttle the APU).
                suspect = any(
                    0 < limits.get(k, 0) <= RYZENADJ_SANE_FLOOR_MW
                    for k in ("stapm-limit", "fast-limit", "slow-limit")
                )
                if suspect and self.watchdog_ryzenadj:
                    logger.warning(
                        f"[DIB SNAPSHOT] ryzenadj reports {limits}, which looks like a leftover "
                        f"of this plugin; using the last known-good baseline {self.watchdog_ryzenadj}."
                    )
                    self.saved_ryzenadj = dict(self.watchdog_ryzenadj)
                elif suspect:
                    logger.warning(
                        f"[DIB SNAPSHOT] ryzenadj reports {limits}, which looks like a plugin cap; "
                        "skipping ryzenadj for this cycle so we never write these back as originals."
                    )
                else:
                    self.saved_ryzenadj = limits
                    if self.settings.get("debug_logging", True):
                        logger.info(f"[DIB SNAPSHOT] ryzenadj originals captured: {limits}")

        if self.settings.get("debug_logging", True):
            logger.info(
                "[DIB SNAPSHOT] Recorded originals before touching anything: "
                f"platform_profile={self.saved_platform_profile} asus_thermal={self.saved_asus_thermal} "
                f"boost={self.saved_cpu_boost} ppt={self.saved_asus_ppt or 'none'} "
                f"fan_boost={self.saved_fan_boost or 'none'} "
                f"cpu_freqs={sorted(set(self.saved_cpu_freqs.values())) or 'none'} "
                f"governors={sorted(set(self.saved_cpu_governors.values())) or 'none'} "
                f"epp={sorted(set(self.saved_cpu_epp.values())) or 'none'} "
                f"gpu_dpm={sorted(set(self.saved_gpu_dpm.values())) or 'none'}"
            )

    def _save_original(self, store: Dict[str, str], key: str, current: str, target: str) -> bool:
        """
        Records what to put back later, and never lets a second pass overwrite it.

        Applying the low-power settings twice without a restore in between used to
        overwrite the saved originals with the throttled values this plugin had just
        written. 'Restore' then meant writing 800 MHz and 6 W back in: a console left
        slow until the next reboot, with nothing in the log looking wrong. First save
        wins, and a value that already matches the target is not saved at all, so the
        restore cannot be turned into a no-op either.
        """
        if current == target:
            return False
        if key not in store:
            store[key] = current
        self.applied_marks[key] = target
        return True

    def _save_original_scalar(self, attr: str, current: str, target: str, path: str) -> bool:
        """_save_original for the settings there is only one of on a machine."""
        if current == target:
            return False
        if getattr(self, attr, None) is None:
            setattr(self, attr, current)
        self.applied_marks[path] = target
        return True

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
            asyncio.run_coroutine_threadsafe(self.exit_background_mode(reason), self.loop)

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
        for pad in self._find_external_gamepads():
            if pad["bustype"] != BUS_BLUETOOTH or pad["input_dir"] in self.standby_known_gamepads:
                continue
            self.standby_known_gamepads.add(pad["input_dir"])
            names.append(pad["name"] or pad["input_dir"])
        for address, name in self._bluez_connected_gamepads().items():
            key = f"bt:{address}"
            if key in self.standby_known_gamepads:
                continue
            self.standby_known_gamepads.add(key)
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
            self._log_input_diagnostics("before release")

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
        Puts the display into a real standby, so an external TV or monitor stops showing
        a black screen and enters its own no-signal state.

        On a handheld (ROG Ally, Steam Deck) the backlight sysfs path above was enough -
        the panel itself went dark. On a desktop PC connected to a TV, the TV manages its
        own backlight: it only enters standby when the GPU stops sending video. That is
        what this does, trying every path a given SteamOS build may expose:

          1. gamescopectl drm_sleep_internal_screen  -> handheld panel
          2. gamescopectl drm_sleep_external_screen  -> dock / desktop TV
          3. The DRM connector dpms attribute        -> works outside gamescope, too
          4. The DRM connector enabled attribute     -> harder shut-off, same end result

        Each one is wrapped in its own try, so a path a given gamescope build does not
        support just logs 'no' and the next one runs.
        """
        arg = "1" if sleep else "0"
        dpms_state = "4" if sleep else "0"   # 4 = DRM_MODE_DPMS_OFF, 0 = ON

        # Paths 1 and 2: gamescope.
        gamescopectl = shutil.which("gamescopectl") or next(
            (p for p in ("/usr/bin/gamescopectl", "/usr/local/bin/gamescopectl") if os.path.exists(p)),
            None,
        )
        if gamescopectl:
            user = self._get_session_user()
            for uid_dir in glob.glob("/run/user/*"):
                if not os.path.basename(uid_dir).isdigit():
                    continue
                env = os.environ.copy()
                env["XDG_RUNTIME_DIR"] = uid_dir
                for subcommand in ("drm_sleep_internal_screen", "drm_sleep_external_screen"):
                    for cmd in (
                        [gamescopectl, subcommand, arg],
                        ["sudo", "-u", user, "env", f"XDG_RUNTIME_DIR={uid_dir}", gamescopectl, subcommand, arg],
                    ):
                        try:
                            subprocess.run(
                                cmd, env=env, check=False,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0,
                            )
                        except Exception:
                            pass

        # Path 3: DRM DPMS on each connected connector. Standard kernel interface, works
        # on amdgpu, i915, nvidia-drm. Writing to this attribute does not need the DRM
        # master, only root (which this plugin has through plugin.json flags).
        for conn in glob.glob("/sys/class/drm/card*-*"):
            try:
                if self._read_text(os.path.join(conn, "status")) != "connected":
                    continue
            except Exception:
                continue
            dpms_file = os.path.join(conn, "dpms")
            if not os.path.exists(dpms_file):
                continue
            label = os.path.basename(conn)
            try:
                before = self._read_text(dpms_file)
                if self._write_sysfs(dpms_file, dpms_state):
                    logger.info(f"DRM DPMS on {label}: {before} -> {dpms_state} (sleep={sleep}).")
            except Exception as e:
                logger.debug(f"DRM DPMS on {label} failed: {e}")

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
            "applied_marks": dict(self.applied_marks),
            # Watchdog baselines, so the safety net survives a plugin reload.
            "watchdog_targets": dict(self.watchdog_targets),
            "watchdog_marks": dict(self.watchdog_marks),
            "watchdog_ryzenadj": dict(self.watchdog_ryzenadj) if self.watchdog_ryzenadj else None,
            # Pending RTC-wake handoff: if the plugin is reloaded while the console is
            # suspended for quiet hours, the resume handler still fires because the state
            # survives the reload.
            "rtc_wake_pending": bool(self.rtc_wake_pending),
            "rtc_wake_target": int(self.rtc_wake_target) if self.rtc_wake_target else 0,
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
        # Carried across a reload so the forced pass can still recognise its own work.
        self.applied_marks = {str(k): str(v) for k, v in (state.get("applied_marks") or {}).items()}
        # Watchdog baselines survive a reload: the plugin can still rescue a system that
        # went slow between the previous instance's unload and this one's load.
        self.watchdog_targets = {str(k): str(v) for k, v in (state.get("watchdog_targets") or {}).items()}
        self.watchdog_marks = {str(k): str(v) for k, v in (state.get("watchdog_marks") or {}).items()}
        wr = state.get("watchdog_ryzenadj")
        self.watchdog_ryzenadj = {str(k): int(v) for k, v in wr.items()} if isinstance(wr, dict) else {}
        # Quiet-hours RTC pending handoff
        self.rtc_wake_pending = bool(state.get("rtc_wake_pending"))
        try:
            self.rtc_wake_target = int(state.get("rtc_wake_target") or 0)
        except (TypeError, ValueError):
            self.rtc_wake_target = 0

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

        # 0. Record what everything looks like BEFORE anything is changed. Several of
        # these settings move each other, so reading each one just before overwriting it
        # captures a value this plugin itself caused. See _snapshot_power_originals.
        self._snapshot_power_originals()

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
            if os.path.exists(profile_file):
                try:
                    with open(profile_file, "r") as f:
                        curr_profile = f.read().strip()
                    target_choice = self._platform_profile_target()
                    self._save_original_scalar("saved_platform_profile", curr_profile, target_choice, profile_file)
                    self._write_sysfs(profile_file, target_choice)
                    logger.info(f"Set ACPI platform_profile to {target_choice} (was {curr_profile}).")
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
                            curr_thermal = f.read().strip()
                        self._save_original_scalar("saved_asus_thermal", curr_thermal, "2", asus_thermal_file)
                        self._write_sysfs(asus_thermal_file, "2")
                        logger.info(f"Set ASUS thermal policy on {asus_thermal_file} to Silent (2) (was {curr_thermal}).")
                    except Exception:
                        pass

            # Fan boost mode (Silent = 2). Saved, because leaving the fans in silent mode
            # after waking makes the console throttle and feel permanently slow.
            for fan_boost in glob.glob("/sys/devices/platform/asus*/fan_boost_mode"):
                try:
                    with open(fan_boost, "r") as f:
                        curr_fan = f.read().strip()
                except Exception:
                    continue
                self._save_original(self.saved_fan_boost, fan_boost, curr_fan, "2")
                self._write_sysfs(fan_boost, "2")

            # C. ASUS Hardware PPT / SPL Power Limits (Hard limit to 6 Watts!)
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
                        self._save_original(self.saved_asus_ppt, pf, curr_ppt, "6")
                        self._write_sysfs(pf, "6")
                        logger.info(f"Capped ASUS PPT limit on {pf} to 6W (was {curr_ppt}).")
                    except Exception:
                        pass

            # D. ryzenadj hardware-cap: APU to 6 W. The originals have already been
            # snapshotted at the top of this function, BEFORE any firmware re-apply could
            # change what ryzenadj would report. If that read came back empty, the write
            # is skipped on purpose: without a real original to put back, "restoring" was
            # how the console used to end up at the wrong wattage until the next reboot.
            if shutil.which("ryzenadj"):
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
            boost_file = self.CPU_BOOST_FILE
            if os.path.exists(boost_file):
                try:
                    with open(boost_file, "r") as f:
                        curr_boost = f.read().strip()
                    self._save_original_scalar("saved_cpu_boost", curr_boost, "0", boost_file)
                    self._write_sysfs(boost_file, "0")
                    logger.info(f"Disabled global CPU turbo boost (boost {curr_boost} -> 0).")
                except Exception:
                    pass

            for pboost in glob.glob("/sys/devices/system/cpu/cpufreq/policy*/boost"):
                try:
                    with open(pboost, "r") as f:
                        curr_b = f.read().strip()
                    self._save_original(self.saved_policy_boost, pboost, curr_b, "0")
                    self._write_sysfs(pboost, "0")
                except Exception:
                    pass

            # G. Throttle CPU Frequency to Minimum across ALL cores & policies
            min_freq = self._cpu_min_freq_target()

            freq_files = glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq") + glob.glob("/sys/devices/system/cpu/cpufreq/policy*/scaling_max_freq")
            for freq_file in set(freq_files):
                try:
                    with open(freq_file, "r") as f:
                        curr_freq = f.read().strip()
                    self._save_original(self.saved_cpu_freqs, freq_file, curr_freq, min_freq)
                    self._write_sysfs(freq_file, min_freq)
                except Exception:
                    pass
            if self.saved_cpu_freqs:
                logger.info(f"Capped CPU max frequency to {min_freq} kHz across {len(self.saved_cpu_freqs)} nodes for calm, silent cooling.")

            # H. Set CPU scaling governor to powersave across all cores
            gov_files = glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor") + glob.glob("/sys/devices/system/cpu/cpufreq/policy*/scaling_governor")
            for gov_file in set(gov_files):
                try:
                    with open(gov_file, "r") as f:
                        curr_gov = f.read().strip()
                    self._save_original(self.saved_cpu_governors, gov_file, curr_gov, "powersave")
                    self._write_sysfs(gov_file, "powersave")
                except Exception:
                    pass

            # I. Set AMD Energy Performance Preference (EPP) to power
            epp_files = glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference") + glob.glob("/sys/devices/system/cpu/cpufreq/policy*/energy_performance_preference")
            for ep in set(epp_files):
                try:
                    with open(ep, "r") as f:
                        curr_epp = f.read().strip()
                    self._save_original(self.saved_cpu_epp, ep, curr_epp, "power")
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
                    self._save_original(self.saved_gpu_dpm, dpm_path, curr_dpm, "low")
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
        if self.settings.get("debug_logging", True):
            # The counterpart of [DIB RESTORE CHECK]: what was taken away, and what has
            # to come back. A report of "still slow" is then a diff of two log lines.
            logger.info(
                "[DIB APPLY CHECK] "
                f"will_restore_cpu_freqs={len(self.saved_cpu_freqs)} "
                f"governors={len(self.saved_cpu_governors)} epp={len(self.saved_cpu_epp)} "
                f"policy_boost={len(self.saved_policy_boost)} gpu_dpm={self.saved_gpu_dpm or 'none'} "
                f"ppt={self.saved_asus_ppt or 'none'} fan_boost={self.saved_fan_boost or 'none'} "
                f"boost={self.saved_cpu_boost} platform_profile={self.saved_platform_profile} "
                f"asus_thermal={self.saved_asus_thermal} ryzenadj={self.saved_ryzenadj or 'none'} "
                f"quota={self.saved_cpu_quota or 'none'} marks={len(self.applied_marks)}"
            )

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
        self.standby_mode = False

        # What every path must read back as, captured before the stages start emptying
        # the saved values, so the result can be checked instead of assumed.
        targets = self._restore_targets_snapshot()

        # The platform profile and the power limits go back BEFORE the clocks. Changing
        # the ACPI profile or the ASUS thermal policy makes the firmware re-apply its own
        # clock and power ceilings, which silently overwrote the frequencies restored a
        # moment earlier - the console then sat at its low-power clocks until a reboot.
        stages = (
            ("backlight", self._restore_backlight),
            ("download pacing", self._restore_download_pacing),
            ("steam scheduling", self._heal_steam_scheduling),
            ("platform profile", self._restore_platform_profile),
            ("apu power limits", self._restore_apu_power_limits),
            ("cpu", self._restore_cpu_settings),
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

        stubborn = self._converge_restore(targets)
        forced = self._verify_and_force_restore()

        # Keep watching for a short while: see _recheck_after_restore.
        self.post_restore_targets = dict(targets)
        self.post_restore_until = time.time() + POST_RESTORE_WATCH_SECONDS

        # Keep watching forever (while NOT in the mode) as a safety net: see
        # _throttle_watchdog. This is the "contorno" the user asked for.
        self._arm_watchdog_from_targets()
        if failed or forced or stubborn:
            logger.warning(
                f"Restore finished with problems. failed_stages={failed or 'none'} "
                f"did_not_stick={stubborn or 'none'} forced_fixes={forced or 'none'}"
            )
        else:
            logger.info(f"Restore complete; {len(targets)} values verified back to normal.")

    def _restore_targets_snapshot(self) -> Dict[str, str]:
        """Every path the restore is about to write, with the value it must end up at."""
        targets: Dict[str, str] = {}
        for store in (
            self.saved_cpu_freqs, self.saved_cpu_governors, self.saved_cpu_epp,
            self.saved_policy_boost, self.saved_gpu_dpm, self.saved_asus_ppt,
            self.saved_fan_boost,
        ):
            targets.update(store)
        if self.saved_cpu_boost is not None:
            targets[self.CPU_BOOST_FILE] = self.saved_cpu_boost
        if self.saved_platform_profile:
            targets["/sys/firmware/acpi/platform_profile"] = self.saved_platform_profile
        if self.saved_asus_thermal:
            for path in (
                "/sys/devices/platform/asus-nb-wmi/throttle_thermal_policy",
                "/sys/devices/platform/asus_wmi/throttle_thermal_policy",
            ):
                if os.path.exists(path):
                    targets[path] = self.saved_asus_thermal
        return targets

    def _converge_restore(self, targets: Dict[str, str]) -> List[str]:
        """
        Writes again whatever did not stick, until it does, and reports what never did.

        One pass is not enough on these platforms. A value can be refused, clamped, or
        overwritten moments later by firmware reacting to another write (an ACPI profile
        change re-applying its own limits is the usual one). Rather than hard-code the
        right order for every device, the restore is re-read and re-applied until the
        machine stops disagreeing - which also catches whatever device comes next.
        """
        if not targets:
            return []

        def mismatches() -> List[Tuple[str, str, str]]:
            out: List[Tuple[str, str, str]] = []
            for path, want in targets.items():
                if not os.path.exists(path):
                    continue
                try:
                    with open(path, "r") as f:
                        have = f.read().strip()
                except Exception:
                    continue
                if have != want:
                    out.append((path, have, want))
            return out

        for attempt in range(3):
            pending = mismatches()
            if not pending:
                return []
            logger.info(
                f"Restore pass {attempt + 2}: {len(pending)} value(s) did not stick, writing again."
            )
            for path, _have, want in pending:
                self._write_sysfs(path, want)
            time.sleep(0.2)

        remaining = [f"{path} is '{have}', wanted '{want}'" for path, have, want in mismatches()]
        if remaining:
            logger.error(f"Restore could not put these back after 3 extra passes: {remaining}")
        return remaining

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
            self._write_sysfs(self.CPU_BOOST_FILE, self.saved_cpu_boost)
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

    # Safe values for settings this plugin is known to have written, used only when the
    # original is gone. The scaling governor is deliberately absent: 'powersave' is the
    # normal amd-pstate default, so forcing it would be fighting the system.
    MARK_FALLBACKS = {
        "power_dpm_force_performance_level": "auto",
        "boost": "1",
        "energy_performance_preference": "balance_performance",
        "platform_profile": "balanced",
    }

    def _force_back_from_mark(self, path: str, mark: str) -> str:
        """
        Puts one setting back when it still holds exactly the value this plugin wrote and
        there is no saved original left. Returns what it did, or "" for nothing.
        """
        if not os.path.exists(path):
            return ""
        try:
            with open(path, "r") as f:
                have = f.read().strip()
        except Exception:
            return ""
        if have != mark:
            return ""  # Already something else, so not ours any more

        base = os.path.basename(path)
        if base == "scaling_max_freq":
            ceiling = self._read_attr(os.path.dirname(path), "cpuinfo_max_freq")
            if ceiling and ceiling != mark and self._write_sysfs(path, ceiling):
                return f"{path} was still capped at {mark}, raised to {ceiling}"
            return ""
        fallback = self.MARK_FALLBACKS.get(base)
        if fallback and fallback != mark and self._write_sysfs(path, fallback):
            return f"{path} was still at {mark}, set to {fallback}"
        return ""

    def _arm_watchdog_from_targets(self):
        """
        After a successful restore, record the known-good values so the watchdog can
        tell them apart from another tool's choice.

        Called at the end of _restore_system_power_and_display. Values are added, never
        removed: an alternate restore might not touch everything a previous one did, and
        anything left out would stop being guarded.
        """
        self.watchdog_targets.update(self.post_restore_targets)
        self.watchdog_marks.update(self.post_restore_marks)
        if self.saved_ryzenadj:
            # Ignore a saved value that was itself our own cap: that would make the
            # watchdog write the cap back forever.
            if not any(
                0 < self.saved_ryzenadj.get(k, 0) <= RYZENADJ_SANE_FLOOR_MW
                for k in ("stapm-limit", "fast-limit", "slow-limit")
            ):
                self.watchdog_ryzenadj = dict(self.saved_ryzenadj)
        self._save_runtime_state()

    # The periodic watchdog runs at this cadence (seconds). Set long on purpose: the
    # primary path is the 8 s post-wake auto-reset, this is only the backstop for
    # drift that happens later. The user asked for both: "esperar uns 8 segundos e
    # entao chamar o restore hardware" + "de tempos em tempos tem que ter essa
    # checkagem, para corrigir possiveis problemas futuros".
    WATCHDOG_PERIODIC_INTERVAL = 90.0
    # After a hard reset the periodic watchdog waits this many seconds before it is
    # allowed to run another one, so one wake does not get the hard reset over and over.
    WATCHDOG_HARD_RESET_COOLDOWN = 120.0

    def _throttle_watchdog(self) -> List[str]:
        """
        Periodic safety net for drift that happens LATER - between wakes, or hours after
        a wake - not for the moment just after a wake, which the post-wake auto-reset
        already covers.

        One hard reset per wake, no more. If this watchdog finds signs of capping and
        the 8 s post-wake auto-reset already fired for the current wake, it skips the
        hard reset (the user asked for exactly this: do not keep calling it once it has
        been executed). It still runs the cheap, baseline-based repairs though - those
        are tiny and cannot step on anything.

        Only acts on values that match EXACTLY what the plugin wrote, so another tool
        (PowerTools, HHD, you) is never fought.
        """
        if self.is_background_mode or self.transition_in_progress:
            return []
        now = time.time()
        if now < self.wake_cooldown_until + 3.0:
            return []
        if now - self.last_watchdog_check < self.WATCHDOG_PERIODIC_INTERVAL:
            return []
        self.last_watchdog_check = now

        repairs: List[str] = []

        # 1. The cheap baseline-based repairs always run: each one is one sysfs write
        # and only if the value matches our cap exactly. Independent of the hard reset.
        for path, want in self.watchdog_targets.items():
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r") as f:
                    have = f.read().strip()
            except Exception:
                continue
            if have == want:
                continue
            mark = self.watchdog_marks.get(path)
            if mark is None or have != mark:
                continue  # Something else wrote it; leave it alone
            if self._write_sysfs(path, want):
                repairs.append(f"{os.path.basename(path)}: {have}->{want}")

        # 2. The hard reset only runs here when NONE of the cheaper options help, and
        # NOT if the post-wake auto-reset already fired for the current wake. One run
        # per wake was explicit in the user's own words.
        signs = self._system_still_capped_signs()
        did_hard_reset_for_current_wake = (
            self.last_auto_hard_reset_time > self.last_wake_time
            and now - self.last_auto_hard_reset_time < self.WATCHDOG_HARD_RESET_COOLDOWN
        )
        if signs and not did_hard_reset_for_current_wake:
            logger.warning(
                f"[DIB WATCHDOG] Periodic check: still capped ({signs}); running the hard reset."
            )
            try:
                with self.transition_lock:
                    done = self._hard_reset_power_limits()
                self.last_auto_hard_reset_time = now
                if done:
                    repairs.extend([f"hard-reset: {d}" for d in done])
            except Exception as e:
                logger.error(f"[DIB WATCHDOG] Hard reset failed: {e}")
        elif signs and did_hard_reset_for_current_wake:
            if self.settings.get("debug_logging", True):
                logger.info(
                    f"[DIB WATCHDOG] Signs ({signs}) but hard reset ran recently; waiting."
                )

        if repairs:
            logger.warning(f"[DIB WATCHDOG] Repaired drifted throttles: {repairs}")
        return repairs

    def _recheck_after_restore(self) -> List[str]:
        """
        Looks again, a few seconds after a restore, and puts back anything that has been
        undone since.

        The restore itself re-reads and re-writes until the machine agrees, but it stops
        looking after a fraction of a second. Changing the ACPI platform profile or the
        ASUS thermal policy makes the firmware re-apply its own clock and power limits,
        and it does not always do that immediately - so without this, the machine can
        agree with the restore and then quietly undo it once nobody is watching.
        """
        fixed: List[str] = []
        for path, want in self.post_restore_targets.items():
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r") as f:
                    if f.read().strip() == want:
                        continue
            except Exception:
                continue
            if self._write_sysfs(path, want):
                fixed.append(f"{path} -> {want}")
        for path, mark in self.post_restore_marks.items():
            note = self._force_back_from_mark(path, mark)
            if note:
                fixed.append(note)
        return fixed

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

        # 0. Anything still holding exactly the value this plugin wrote, with no original
        # left to put it back from: the saved values were lost (a crash, a plugin reload
        # mid-session) or something overwrote them. Only paths with a safe, known-good
        # fallback are forced. The scaling governor is not one of them: 'powersave' is
        # the normal amd-pstate default, so forcing it would fight the system.
        for path, mark in list(self.applied_marks.items()):
            note = self._force_back_from_mark(path, mark)
            if note:
                forced.append(note)

        # Handed to the delayed re-check below, which runs for a few seconds after the
        # restore has finished, then cleared.
        self.post_restore_marks = dict(self.applied_marks)
        self.applied_marks.clear()

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

        # Standby is decided by the setting, never by how the mode was entered. Deriving
        # it from the reason string meant an entry through the HUD countdown
        # ("countdown_completed") silently ran WITHOUT standby: no controller could wake
        # the console, and the external pads were detached as part of the normal lockout.
        self.standby_mode = bool(self.settings.get("standby_on_power_off", False))
        logger.info(
            f"Entering {'Standby' if self.standby_mode else 'Background Download'} Mode (reason: {reason})."
        )
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

        await decky.emit("background_mode_changed", {
            "is_background_mode": True,
            "reason": reason,
            "standby": self.standby_mode,
            # Without a download there is nothing to put in the HUD, so the frontend
            # shows just the plugin logo before the screen goes black.
            "has_download": self._is_active_download(),
        })
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

        # Record this wake, so the periodic watchdog can tell "already handled this
        # wake" from "a new wake happened, do it again".
        self.last_wake_time = time.time()
        # Scheduled 8 s after the wake: run the hard reset unconditionally, as the user
        # asked. The periodic watchdog honours a cooldown after this so one wake does
        # not get the hard reset over and over.
        if self.loop and self.loop.is_running():
            self.loop.create_task(self._auto_hard_reset_after_wake(8.0))
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
                enabled = self._effective_enabled()
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
                is_dl = self._refresh_download_state()

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

                # A restore can be undone a second or two AFTER it finishes, because
                # changing the ACPI profile makes the firmware re-apply its own limits on
                # its own schedule. The restore itself has stopped looking by then, so a
                # console that was verified back to normal can quietly go slow again.
                if self.post_restore_until and not self.is_background_mode and not self.transition_in_progress:
                    if now < self.post_restore_until:
                        undone = self._recheck_after_restore()
                        if undone:
                            logger.warning(
                                f"[DIB POST-RESTORE] Something undid the restore; put back: {undone}"
                            )
                    else:
                        self.post_restore_until = 0.0
                        self.post_restore_targets = {}
                        self.post_restore_marks = {}

                # Permanent watchdog: a safety net for the cases none of the paths above
                # catch. Runs quietly every ~20s while NOT in the mode, and corrects
                # ONLY values that match the plugin's own cap exactly. See the function.
                if self.watchdog_targets or self.watchdog_ryzenadj:
                    self._throttle_watchdog()

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

                    # A USB/dongle controller that connects AFTER standby began has no wake
                    # capability unless this adds it, and its buttons would act on the
                    # console in the window before the next grab/inhibit pass.
                    if self.standby_mode:
                        self._refresh_standby_wake_sources()

                    # A Bluetooth controller connecting is itself the wake signal: there is
                    # no button to press, the pairing is the request for the console back.
                    if self.standby_mode and self.settings.get("wake_on_bluetooth_connect", True):
                        connected = self._newly_connected_bluetooth_gamepads()
                        if connected and time_in_bg > BT_CONNECT_GRACE_SECONDS:
                            logger.info(f"Bluetooth controller connected in standby ({', '.join(connected)}) -> waking.")
                            await self.exit_background_mode("bluetooth_controller_connected")
                            continue

                    # Quiet hours while already in the mode: a session that began at
                    # 22:50 reaches 23:00 while sitting here, and the user chose the
                    # real sleep for that case too. The exit comes first so the mode's
                    # restore runs cleanly; the real suspend follows.
                    if self.standby_mode and self._inside_quiet_hours() and not self._is_active_download():
                        logger.info(
                            "[DIB QUIET HOURS] Entered the quiet-hours period while in our mode; "
                            "exiting it and running real SteamOS sleep."
                        )
                        if self.settings.get("wake_at_period_end", False):
                            end_epoch = self._next_quiet_hours_end()
                            if end_epoch and self._schedule_rtc_wake(end_epoch):
                                self.rtc_wake_pending = True
                                self.rtc_wake_target = end_epoch
                                self._save_runtime_state()
                        await self.exit_background_mode("quiet_hours_real_sleep")
                        await asyncio.sleep(0.5)
                        await self.trigger_suspend()
                        continue

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

                    # Condition B: Downloads finished or paused auto-suspend.
                    # Never in standby: there the console is meant to sit and wait for a
                    # controller, so suspending it for lack of a download would defeat it.
                    if not is_dl and not self.standby_mode:
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
