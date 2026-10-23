"""Applying the power-saving profile and turning the screen off."""
import os
import glob
import subprocess
import shutil
from typing import Dict

from .constants import logger


class PowerSavingMixin:
    """Applying the power-saving profile and turning the screen off."""

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

        # Pause games before changing displays/clocks. Steam and its downloads stay
        # alive. A failed pause aborts entry instead of throttling a running game.
        self._pause_running_games()

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
                    except Exception:
                        try:
                            self._write_sysfs(brightness_path, "0")
                        except Exception:
                            pass

                if os.path.exists(bl_power_path):
                    try:
                        # FB_BLANK_POWERDOWN = 4 (completely shuts down backlight power on LCD/IPS panels)
                        with open(bl_power_path, "w") as f:
                            f.write("4")
                        logger.info(f"Set bl_power {bl_power_path} to 4 (FB_BLANK_POWERDOWN).")
                    except Exception:
                        try:
                            self._write_sysfs(bl_power_path, "4")
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
                        self._write_sysfs(dpm_path, "low")
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
                        self._write_sysfs(lp, "0")
            except Exception:
                pass

        # 6. Write down everything that now needs undoing, before touching input. If the
        # plugin dies from here on, the next start replays this exact restore.
        self._save_runtime_state()
        if self.settings.get("debug_logging", True):
            # The counterpart of [NSM RESTORE CHECK]: what was taken away, and what has
            # to come back. A report of "still slow" is then a diff of two log lines.
            logger.info(
                "[NSM APPLY CHECK] "
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
