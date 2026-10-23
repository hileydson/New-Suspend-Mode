"""Restoring hardware, display and audio when the plugin's mode ends."""
import os
import time
import subprocess
import shutil
from typing import Dict, List, Tuple

from .constants import logger, POST_RESTORE_WATCH_SECONDS


class RestoreMixin:
    """Restoring hardware, display and audio when the plugin's mode ends."""

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
        started = time.monotonic()
        timings: Dict[str, float] = {}
        failed: List[str] = []

        def run_stage(label, stage):
            before = time.monotonic()
            try:
                return stage()
            except Exception as e:
                failed.append(label)
                logger.error(f"Restore stage '{label}' FAILED: {e}")
            finally:
                timings[label] = time.monotonic() - before
                if self.settings.get("debug_logging", True):
                    logger.info(f"[NSM WAKE TIMING] {label}={timings[label]:.3f}s")

        # The platform profile and the power limits go back BEFORE the clocks. Changing
        # the ACPI profile or the ASUS thermal policy makes the firmware re-apply its own
        # clock and power ceilings, which silently overwrote the frequencies restored a
        # moment earlier - the console then sat at its low-power clocks until a reboot.
        stages = (
            # Let Steam draw the wake immediately, rather than making display and
            # IPC commands compete with a quota of a fraction of one CPU core.
            ("steam cpu budget", self._restore_cpu_quota),
            ("backlight", self._restore_backlight),
            ("download pacing", self._restore_download_pacing),
            ("steam scheduling", self._heal_steam_scheduling),
            ("platform profile", self._restore_platform_profile),
            ("apu power limits", self._restore_apu_power_limits),
            ("cpu", self._restore_cpu_settings),
            ("gpu", self._restore_gpu_settings),
        )

        for label, stage in stages:
            run_stage(label, stage)

        # A normal wake keeps native input blocked beneath the presentation. Real
        # sleep, unload and emergency recovery still give it back immediately.
        if not self.wake_presentation_active:
            run_stage("input", self._release_all_gamepad_inputs)
        else:
            run_stage("splash input lock", self._lock_inputs_for_splash)

        try:
            stubborn = run_stage("verify saved values", lambda: self._converge_restore(targets)) or []
            forced = run_stage("verify fallback values", self._verify_and_force_restore) or []
        finally:
            # Keep games paused across a handoff into real sleep. On a normal wake,
            # clocks, display and input have already been restored before this point.
            if not self.games_waiting_for_resume and not self.wake_presentation_active:
                run_stage("resume games", self._resume_running_games)

        logger.info(f"[NSM WAKE TIMING] interactive restore={time.monotonic() - started:.3f}s")
        # These are still restored on every path, including real sleep and recovery,
        # but an unavailable audio server or a diagnostic scan cannot delay input or
        # leave an otherwise ready game paused. During the wake presentation, audio stays
        # muted until the splash finishes so button presses cannot make UI sounds.
        if not self.wake_presentation_active:
            run_stage("audio", self._restore_audio)
        run_stage("leds", self._restore_leds)
        if self.input_diagnostics_pending and not self.wake_presentation_active:
            self.input_diagnostics_pending = False
            run_stage("input diagnostics", lambda: self._log_input_diagnostics("after restore"))

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

        # Wake the display back up through Gamescope. Also runs when only
        # forced_off_connectors is set, which is the case after loading the runtime
        # state of a session that crashed mid-standby: a display left at "no signal"
        # has to come back even if the flag that put it there did not survive.
        if self.display_slept_by_us or self.forced_off_connectors:
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
                        self._write_sysfs(dpm_path, target_dpm)
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
                        self._write_sysfs(lp, orig_val)
            except Exception:
                pass
        self.saved_leds.clear()
