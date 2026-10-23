"""Settings defaults, tuning constants and the Decky handle shared by every module."""
import os
import struct
import logging
from typing import Dict, Any

# Setup Decky compatibility
try:
    import decky
except ImportError:
    # Dummy mock for standalone linting / local testing outside Decky
    class DummyDecky:
        DECKY_PLUGIN_SETTINGS_DIR = os.path.expanduser("~/.config/NewSuspendMode")
        DECKY_PLUGIN_LOG_DIR = os.path.expanduser("~/.config/NewSuspendMode/logs")
        DECKY_USER_HOME = os.path.expanduser("~")
        DECKY_HOME = os.path.expanduser("~/homebrew")
        logger = logging.getLogger("NewSuspendMode")
        @staticmethod
        async def emit(event_name: str, *args):
            pass
    decky = DummyDecky()

logging.basicConfig(level=logging.INFO)
logger = decky.logger

DEFAULT_SETTINGS: Dict[str, Any] = {
    # Mutually exclusive activation modes; both off disables the plugin.
    "enabled": False,
    "enable_plugin_when_plugged_in": True,
    "min_battery_threshold": 15,
    "hud_timeout_seconds": 5,
    "auto_suspend_delay_seconds": 120,
    "pause_running_games": True,
    "throttle_cpu": True,
    "throttle_gpu": True,
    "mute_audio": True,
    "turn_off_backlight": True,
    "oled_black_screen": True,
    # Desktop/TV only. A black frame is still a valid HDMI signal, so a TV keeps its
    # backlight on and never reaches its own standby. The only way to produce a real
    # "no signal" is to stop the TMDS clock, i.e. disable the connector. Forcing the
    # connector's sysfs `status` to "off" does that: the kernel reports it as
    # disconnected and the compositor drops the output, the same event as unplugging
    # the cable. Off by default because it leaves a single-display desktop headless.
    "tv_force_connector_off": False,
    "deep_input_lockout": True,
    "block_controller_hidraw": False,
    "limit_download_speed": True,
    "download_speed_limit_mbps": 6,
    "download_cpu_percent": 30,
    "debug_logging": True,
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
