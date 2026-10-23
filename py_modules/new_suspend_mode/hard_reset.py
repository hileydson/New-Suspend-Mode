"""Spotting a throttle the plugin left behind, and the hard reset that undoes it."""
import os
import glob
import time
import asyncio
import subprocess
import shutil
from typing import Dict, Any, List, Set

from .constants import (
    decky,
    logger,
    WAKE_COOLDOWN_SECONDS,
    RYZENADJ_SANE_FLOOR_MW,
    CPU_QUOTA_PERIOD,
)


class HardResetMixin:
    """Spotting a throttle the plugin left behind, and the hard reset that undoes it."""

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
                signs.append("gpu_dpm=low")
                break

        # 6. CPU scaling governor stuck at "powersave" when the baseline said otherwise.
        # Only acts when the baseline exists, so a system that genuinely defaults to
        # "powersave" (amd-pstate) is not fought.
        for path in glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"):
            if self._read_text(path) != "powersave":
                continue
            baseline = self.watchdog_targets.get(path)
            if baseline and baseline != "powersave":
                signs.append("governor=powersave")
                break

        # 7. EPP stuck at "power" with the same guard: a baseline change is required.
        for path in glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference"):
            if self._read_text(path) != "power":
                continue
            baseline = self.watchdog_targets.get(path)
            if baseline and baseline != "power":
                signs.append("epp=power")
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

        logger.warning("[NSM AUTO-RESET] 8 s post-wake: running the hard reset.")
        try:
            done = await self.loop.run_in_executor(None, self._run_transition_locked_safe,
                                                   self._hard_reset_power_limits)
            self.last_auto_hard_reset_time = time.time()
            if done:
                logger.warning(f"[NSM AUTO-RESET] Repaired: {done}")
            else:
                logger.info("[NSM AUTO-RESET] Nothing needed repair.")
        except Exception as e:
            logger.error(f"[NSM AUTO-RESET] Failed: {e}")

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
            logger.warning(f"[NSM HARD RESET] {done}")
        return done

    async def force_restore(self) -> Dict[str, Any]:
        """
        Puts the hardware back right now, whether or not the plugin thinks it is in the
        mode, and replays anything a previous session left on disk.

        The escape hatch for a console that came back slow: without it the only way out
        is a reboot, and a reboot also destroys the evidence.
        """
        logger.warning("Force restore requested from the plugin menu.")
        self.games_waiting_for_resume = False
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
