import os
import sys
import json
import glob
import time
import struct
import select
import asyncio
import logging
import threading
import subprocess
from typing import Dict, Any, Optional

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

# Input event struct format for Linux 64-bit:
# struct input_event { struct timeval time (8+8 bytes); __u16 type (2 bytes); __u16 code (2 bytes); __s32 value (4 bytes); }
INPUT_EVENT_FORMAT = "qqHHi"
INPUT_EVENT_SIZE = struct.calcsize(INPUT_EVENT_FORMAT)
EV_KEY = 1
KEY_POWER = 116


class Plugin:
    def __init__(self):
        self.settings: Dict[str, Any] = DEFAULT_SETTINGS.copy()
        self.settings_file: str = ""
        self.is_background_mode: bool = False
        self.saved_brightness: Dict[str, int] = {}
        self.saved_power_profile: Optional[str] = None
        self.saved_cpu_governors: Dict[str, str] = {}
        self.saved_gpu_dpm: Optional[str] = None
        self.saved_audio_muted: Optional[bool] = None

        self.inhibitor_proc: Optional[subprocess.Popen] = None
        self.power_button_thread: Optional[threading.Thread] = None
        self.stop_threads: bool = False

        self.download_info: Dict[str, Any] = {
            "is_downloading": False,
            "bytes_per_second": 0,
            "progress_percent": 0,
            "game_title": "",
            "total_bytes": 0,
            "completed_bytes": 0,
            "estimated_seconds_remaining": 0,
        }
        self.last_download_active_time: float = time.time()
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.monitor_task: Optional[asyncio.Task] = None

    # ==========================================
    # Lifecycle Hooks
    # ==========================================
    async def _migration(self):
        """Prepare directory structures and migrate legacy paths if needed."""
        try:
            os.makedirs(decky.DECKY_PLUGIN_SETTINGS_DIR, exist_ok=True)
            self.settings_file = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "settings.json")
            self._load_settings()
        except Exception as e:
            logger.error(f"Error during migration: {e}")

    async def _main(self):
        """Plugin initialized and started."""
        self.loop = asyncio.get_running_loop()
        self.settings_file = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "settings.json")
        self._load_settings()
        self.stop_threads = False

        logger.info("Download in Background plugin started.")

        # Start power button listener thread
        self.power_button_thread = threading.Thread(
            target=self._power_button_listener_worker,
            daemon=True,
            name="DownloadInBackground-PowerButton"
        )
        self.power_button_thread.start()

        # Start periodic background monitor
        self.monitor_task = self.loop.create_task(self._background_monitor_loop())

    async def _unload(self):
        """Called when plugin is unloaded or disabled."""
        logger.info("Unloading Download in Background plugin...")
        self.stop_threads = True

        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()

        # Restore system state if we were in background download mode
        if self.is_background_mode:
            self._restore_system_power_and_display()

        # Release inhibitor lock
        self._release_sleep_inhibitor()

    async def _uninstall(self):
        """Called during complete uninstall."""
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

        # Update inhibitor state based on settings
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
        """Reads capacity and status from /sys/class/power_supply/BAT*."""
        capacity = 100
        is_charging = False
        is_plugged = False

        # Check AC/USB power supply
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

        # Check Battery (BAT0, BAT1, etc.)
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

    # ==========================================
    # Download Status Sync & Backend Detection
    # ==========================================
    async def update_download_status(self, info: Dict[str, Any]):
        """Called by Frontend whenever SteamClient reports download metrics."""
        self.download_info.update(info)
        is_dl = bool(info.get("is_downloading", False) or info.get("bytes_per_second", 0) > 10000)
        self.download_info["is_downloading"] = is_dl

        if is_dl:
            self.last_download_active_time = time.time()

        self._update_inhibitor_state()

    def _is_downloading_active(self) -> bool:
        """Determines if downloads are currently active, checking frontend report & filesystem."""
        if self.download_info.get("is_downloading", False):
            return True

        if self.download_info.get("bytes_per_second", 0) > 50000:
            return True

        # Secondary check: Check Steam's downloading directory for active files
        steam_paths = [
            os.path.expanduser("~/.local/share/Steam/steamapps/downloading"),
            os.path.expanduser("~/.steam/steam/steamapps/downloading"),
        ]
        for sp in steam_paths:
            if os.path.isdir(sp):
                try:
                    entries = os.listdir(sp)
                    if entries:
                        # Files exist in downloading directory
                        return True
                except Exception:
                    pass

        return False

    # ==========================================
    # Systemd Inhibitor Control
    # ==========================================
    def _acquire_sleep_inhibitor(self):
        """Acquires sleep:handle-power-key inhibitor using systemd-inhibit."""
        if self.inhibitor_proc is not None:
            return

        cmd = [
            "systemd-inhibit",
            "--what=sleep:handle-power-key",
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
            logger.info("Acquired sleep inhibitor lock.")
        except Exception as e:
            logger.error(f"Failed to acquire sleep inhibitor: {e}")
            self.inhibitor_proc = None

    def _release_sleep_inhibitor(self):
        """Releases the sleep inhibitor lock."""
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
        """Keeps inhibitor active if plugin is enabled and downloading or in background mode."""
        if not self.settings.get("enabled", True):
            self._release_sleep_inhibitor()
            return

        should_inhibit = self.is_background_mode or self._is_downloading_active()
        if should_inhibit and self.inhibitor_proc is None:
            self._acquire_sleep_inhibitor()
        elif not should_inhibit and self.inhibitor_proc is not None:
            self._release_sleep_inhibitor()

    # ==========================================
    # Hardware Power Button Monitoring
    # ==========================================
    def _find_power_button_devices(self):
        """Finds all input event device nodes corresponding to the Power Button."""
        devs = []
        try:
            with open("/proc/bus/input/devices", "r") as f:
                content = f.read()

            sections = content.split("\n\n")
            for section in sections:
                if 'Name="Power Button"' in section or "button/power" in section or "gpio-keys" in section:
                    for line in section.split("\n"):
                        if line.startswith("H: Handlers="):
                            parts = line.split()
                            for p in parts:
                                if p.startswith("event"):
                                    dev_path = f"/dev/input/{p}"
                                    if os.path.exists(dev_path) and dev_path not in devs:
                                        devs.append(dev_path)
        except Exception as e:
            logger.error(f"Error parsing /proc/bus/input/devices: {e}")

        # Fallback to searching /dev/input/by-path/*
        if not devs:
            for p in glob.glob("/dev/input/by-path/*-event"):
                if "pnp" in p.lower() or "button" in p.lower() or "power" in p.lower():
                    devs.append(p)

        return devs

    def _power_button_listener_worker(self):
        """Background thread monitoring power button key events."""
        logger.info("Starting power button listener worker...")
        while not self.stop_threads:
            device_paths = self._find_power_button_devices()
            if not device_paths:
                time.sleep(3.0)
                continue

            fds = []
            fd_map = {}
            for path in device_paths:
                try:
                    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                    fds.append(fd)
                    fd_map[fd] = path
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

                                # EV_KEY, KEY_POWER (116), ev_value 1 = key down
                                if ev_type == EV_KEY and ev_code == KEY_POWER and ev_value == 1:
                                    logger.info("Power button pressed detected!")
                                    self._on_power_button_pressed()
                        except BlockingIOError:
                            pass
                        except Exception as e:
                            logger.error(f"Error reading power button event: {e}")
                            break
            finally:
                for fd in fds:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
                time.sleep(1.0)

    def _on_power_button_pressed(self):
        """Handles power button press logic."""
        if not self.settings.get("enabled", True):
            # Plugin disabled; let system handle suspend
            return

        if self.is_background_mode:
            # Console is currently in Background Download Mode (screen off).
            # Power button wakes the screen up!
            logger.info("Power button pressed during background mode -> Waking up!")
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.exit_background_mode("power_button_wake"),
                    self.loop
                )
            return

        # Console is ON. Check if downloads are active.
        if self._is_downloading_active():
            logger.info("Power button pressed while downloading -> Intercepting suspend!")
            # Intercept! Hold inhibitor, notify frontend to show download HUD
            self._acquire_sleep_inhibitor()
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    decky.emit("on_suspend_intercepted", {
                        "download_info": self.download_info,
                        "hud_timeout": self.settings.get("hud_timeout_seconds", 5),
                    }),
                    self.loop
                )
        else:
            # No downloads active. User legitimately wants to suspend.
            logger.info("Power button pressed with no downloads active -> Executing normal suspend.")
            self._release_sleep_inhibitor()
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self.trigger_suspend(), self.loop)

    # ==========================================
    # Power Saving & Screen Control
    # ==========================================
    def _apply_power_saving_and_screen_off(self):
        """Applies ultra low power state and turns display backlight off."""
        # 1. Turn off backlight
        if self.settings.get("turn_off_backlight", True):
            backlight_dirs = glob.glob("/sys/class/backlight/*")
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

        # 2. CPU governor / Power profile
        if self.settings.get("throttle_cpu", True):
            # Try powerprofilesctl
            try:
                res = subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True, check=False)
                if res.returncode == 0:
                    self.saved_power_profile = res.stdout.strip()
                    subprocess.run(["powerprofilesctl", "set", "power-saver"], check=False)
                    logger.info(f"Switched power profile from {self.saved_power_profile} to power-saver.")
            except Exception as e:
                logger.error(f"Failed to set powerprofilesctl: {e}")

            # Also set cpufreq scaling governor to powersave
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
                    logger.info(f"Set GPU performance level to low (was {curr_dpm}).")
                except Exception as e:
                    logger.error(f"Failed to throttle GPU clock: {e}")

        # 4. Mute Audio
        if self.settings.get("mute_audio", True):
            try:
                # PipeWire / WirePlumber
                subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1"], check=False)
                # Fallbacks
                subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"], check=False)
                logger.info("Muted audio for background download.")
            except Exception as e:
                logger.error(f"Failed to mute audio: {e}")

    def _restore_system_power_and_display(self):
        """Restores screen brightness, audio, CPU governors, and GPU clocks."""
        logger.info("Restoring system power and display settings...")

        # 1. Restore Backlight
        for brightness_path, val in self.saved_brightness.items():
            try:
                if os.path.exists(brightness_path):
                    with open(brightness_path, "w") as f:
                        f.write(str(max(val, 10)))  # Ensure at least minimal visible brightness
                    logger.info(f"Restored backlight on {brightness_path} to {val}.")
            except Exception as e:
                logger.error(f"Failed to restore backlight on {brightness_path}: {e}")
        self.saved_brightness.clear()

        # 2. Restore Power Profile / CPU Governor
        if self.saved_power_profile:
            try:
                subprocess.run(["powerprofilesctl", "set", self.saved_power_profile], check=False)
                logger.info(f"Restored power profile to {self.saved_power_profile}.")
            except Exception as e:
                logger.error(f"Failed to restore power profile: {e}")
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
                    logger.info(f"Restored GPU performance level to {self.saved_gpu_dpm}.")
            except Exception as e:
                logger.error(f"Failed to restore GPU performance level: {e}")
            self.saved_gpu_dpm = None

        # 4. Unmute Audio
        try:
            subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"], check=False)
            subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], check=False)
            logger.info("Unmuted audio.")
        except Exception as e:
            logger.error(f"Failed to unmute audio: {e}")

    # ==========================================
    # Background Mode Transitions
    # ==========================================
    async def enter_background_mode(self, reason: str = "manual") -> bool:
        """Transitions into background download mode: turns screen off and applies power saving."""
        if self.is_background_mode:
            return True

        logger.info(f"Entering Background Download Mode (reason: {reason}).")
        self.is_background_mode = True
        self._acquire_sleep_inhibitor()
        self._apply_power_saving_and_screen_off()

        await decky.emit("background_mode_changed", {"is_background_mode": True, "reason": reason})
        return True

    async def exit_background_mode(self, reason: str = "manual") -> bool:
        """Exits background download mode and restores normal operation."""
        if not self.is_background_mode:
            return False

        logger.info(f"Exiting Background Download Mode (reason: {reason}).")
        self.is_background_mode = False
        self._restore_system_power_and_display()
        self._update_inhibitor_state()

        await decky.emit("background_mode_changed", {"is_background_mode": False, "reason": reason})
        return True

    async def trigger_suspend(self):
        """Releases inhibitor and invokes systemctl suspend."""
        logger.info("Executing systemctl suspend...")
        if self.is_background_mode:
            self._restore_system_power_and_display()
            self.is_background_mode = False

        self._release_sleep_inhibitor()

        # Give systemd a moment to register released inhibitor
        await asyncio.sleep(0.5)

        try:
            subprocess.run(["systemctl", "suspend"], check=False)
        except Exception as e:
            logger.error(f"Failed to execute systemctl suspend: {e}")

    # ==========================================
    # Periodic Background Loop (Battery & Completion)
    # ==========================================
    async def _background_monitor_loop(self):
        """Continuously monitors battery and download completion while in background mode."""
        logger.info("Starting background monitor loop...")
        while not self.stop_threads:
            try:
                await asyncio.sleep(4.0)

                if not self.settings.get("enabled", True):
                    continue

                bat = self._get_battery_info()
                is_dl = self._is_downloading_active()

                # Sync inhibitor state
                self._update_inhibitor_state()

                if self.is_background_mode:
                    # 1. Low battery check: If battery drops below configured threshold (default 15%)
                    min_thresh = int(self.settings.get("min_battery_threshold", 15))
                    if not bat["is_charging"] and bat["capacity"] <= min_thresh:
                        logger.warning(
                            f"Battery level is {bat['capacity']}% (<= {min_thresh}% threshold). "
                            "Entering sleep to protect battery!"
                        )
                        await decky.emit("battery_critical_suspend", {
                            "capacity": bat["capacity"],
                            "threshold": min_thresh,
                        })
                        await self.exit_background_mode("low_battery")
                        await self.trigger_suspend()
                        continue

                    # 2. Download completion check
                    if is_dl:
                        self.last_download_active_time = time.time()
                    else:
                        elapsed_since_dl = time.time() - self.last_download_active_time
                        auto_sleep_delay = float(self.settings.get("auto_suspend_delay_seconds", 15))

                        if elapsed_since_dl >= auto_sleep_delay:
                            logger.info(
                                f"All downloads completed ({elapsed_since_dl:.1f}s inactive). "
                                "Entering automatic system suspend!"
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
                await asyncio.sleep(5.0)
