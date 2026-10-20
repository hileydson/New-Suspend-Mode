"""The watchdog that makes sure no throttle outlives the plugin's mode."""
import os
import glob
import time
import subprocess
from typing import List

from .constants import logger, RYZENADJ_SANE_FLOOR_MW, CPU_QUOTA_PERIOD


class ThrottleWatchdogMixin:
    """The watchdog that makes sure no throttle outlives the plugin's mode."""

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
                f"[NSM WATCHDOG] Periodic check: still capped ({signs}); running the hard reset."
            )
            try:
                with self.transition_lock:
                    done = self._hard_reset_power_limits()
                self.last_auto_hard_reset_time = now
                if done:
                    repairs.extend([f"hard-reset: {d}" for d in done])
            except Exception as e:
                logger.error(f"[NSM WATCHDOG] Hard reset failed: {e}")
        elif signs and did_hard_reset_for_current_wake:
            if self.settings.get("debug_logging", True):
                logger.info(
                    f"[NSM WATCHDOG] Signs ({signs}) but hard reset ran recently; waiting."
                )

        if repairs:
            logger.warning(f"[NSM WATCHDOG] Repaired drifted throttles: {repairs}")
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
                "[NSM RESTORE CHECK] "
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
