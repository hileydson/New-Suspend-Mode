"""
New Suspend Mode - Decky Loader backend.

Plugin is the class Decky instantiates. Its lifecycle hooks, settings and status
endpoints live here; everything else is grouped by concern in py_modules/new_suspend_mode,
one mixin per area, which Decky puts on the import path before loading this file.
"""
import os
import json
import glob
import time
import asyncio
import threading
import subprocess
from typing import Dict, Any, Optional, List, Set, Tuple

from new_suspend_mode.constants import decky, logger, DEFAULT_SETTINGS
from new_suspend_mode.download_detector import SteamDownloadDetector
from new_suspend_mode.sleep_inhibitor import SleepInhibitorMixin
from new_suspend_mode.suspend_policy import SuspendPolicyMixin
from new_suspend_mode.hard_reset import HardResetMixin
from new_suspend_mode.logind_watcher import LogindWatcherMixin
from new_suspend_mode.power_key import PowerKeyMixin
from new_suspend_mode.power_snapshot import PowerSnapshotMixin
from new_suspend_mode.system_control import SystemControlMixin
from new_suspend_mode.gamepads import GamepadDevicesMixin
from new_suspend_mode.standby_wake import StandbyWakeMixin
from new_suspend_mode.diagnostics import DiagnosticsMixin
from new_suspend_mode.input_grab import InputGrabMixin
from new_suspend_mode.display_audio import DisplayAudioMixin
from new_suspend_mode.download_pacing import DownloadPacingMixin
from new_suspend_mode.runtime_state import RuntimeStateMixin
from new_suspend_mode.power_saving import PowerSavingMixin
from new_suspend_mode.restore import RestoreMixin
from new_suspend_mode.watchdog import ThrottleWatchdogMixin
from new_suspend_mode.transitions import TransitionsMixin
from new_suspend_mode.monitor_loop import MonitorLoopMixin


class Plugin(
    SleepInhibitorMixin,
    SuspendPolicyMixin,
    HardResetMixin,
    LogindWatcherMixin,
    PowerKeyMixin,
    PowerSnapshotMixin,
    SystemControlMixin,
    GamepadDevicesMixin,
    StandbyWakeMixin,
    DiagnosticsMixin,
    InputGrabMixin,
    DisplayAudioMixin,
    DownloadPacingMixin,
    RuntimeStateMixin,
    PowerSavingMixin,
    RestoreMixin,
    ThrottleWatchdogMixin,
    TransitionsMixin,
    MonitorLoopMixin,
):
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
        # After an RTC wake, the clock may still read a hair inside the quiet-hours
        # window (end minute boundary). Without a grace period, the monitor loop sees
        # that and triggers real sleep again — a loop. 10 minutes is enough for the
        # minute to tick past, which is why the slider is 10-min granular to begin with.
        self.rtc_wake_grace_until: float = 0.0
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
        # DRM connectors whose sysfs `status` this plugin forced to "off". Tracked so the
        # restore puts back exactly what was touched, and persisted in the runtime state
        # so a crash or plugin reload cannot leave a desktop with no display.
        self.forced_off_connectors: List[str] = []

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
            self._migrate_from_old_settings_dir()
            self.settings_file = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "settings.json")
            self._load_settings()
        except Exception as e:
            logger.error(f"Error during migration: {e}")

    def _migrate_from_old_settings_dir(self):
        """
        One-shot: copy settings.json and runtime_state.json from the plugin's old
        name (DownloadInBackground) to the new location on first run under the new
        name. Users keep their configured sliders, toggles and standby state across
        the rename instead of starting fresh.
        """
        try:
            new_dir = decky.DECKY_PLUGIN_SETTINGS_DIR
            old_dir = os.path.join(os.path.dirname(new_dir), "DownloadInBackground")
            if old_dir == new_dir or not os.path.isdir(old_dir):
                return
            for name in ("settings.json", "runtime_state.json"):
                src_path = os.path.join(old_dir, name)
                dst_path = os.path.join(new_dir, name)
                if os.path.isfile(src_path) and not os.path.exists(dst_path):
                    import shutil
                    shutil.copy2(src_path, dst_path)
                    logger.info(f"Migrated {name} from the old plugin folder: {old_dir}")
        except Exception as e:
            logger.warning(f"Old-settings migration skipped: {e}")

    async def _main(self):
        self.loop = asyncio.get_running_loop()
        self.settings_file = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "settings.json")
        self._load_settings()
        self.stop_threads = False

        logger.info("New Suspend Mode plugin started.")

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
            name="NewSuspendMode-PowerButton"
        )
        self.power_button_thread.start()

        # 2. Systemd Logind Journal Watcher Thread (catches UI suspend requests)
        self.logind_watcher_thread = threading.Thread(
            target=self._logind_watcher_worker,
            daemon=True,
            name="NewSuspendMode-LogindWatcher"
        )
        self.logind_watcher_thread.start()

        # 3. Standby wake watcher (controllers asking for the console back)
        self.wake_watcher_thread = threading.Thread(
            target=self._standby_wake_watcher_worker,
            daemon=True,
            name="NewSuspendMode-WakeWatcher"
        )
        self.wake_watcher_thread.start()

        # 4. Main periodic monitor loop
        self.monitor_task = self.loop.create_task(self._background_monitor_loop())

    async def _unload(self):
        logger.info("Unloading New Suspend Mode plugin...")
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
            logger.info(f"[NSM FRONTEND] {json.dumps(payload, default=str)[:12000]}")
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
