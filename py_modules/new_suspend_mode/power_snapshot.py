"""Recording the hardware's original power settings before anything is changed."""
import os
import glob
import shutil
from typing import Dict, Set

from .constants import logger, RYZENADJ_SANE_FLOOR_MW


class PowerSnapshotMixin:
    """Recording the hardware's original power settings before anything is changed."""

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
                        f"[NSM SNAPSHOT] ryzenadj reports {limits}, which looks like a leftover "
                        f"of this plugin; using the last known-good baseline {self.watchdog_ryzenadj}."
                    )
                    self.saved_ryzenadj = dict(self.watchdog_ryzenadj)
                elif suspect:
                    logger.warning(
                        f"[NSM SNAPSHOT] ryzenadj reports {limits}, which looks like a plugin cap; "
                        "skipping ryzenadj for this cycle so we never write these back as originals."
                    )
                else:
                    self.saved_ryzenadj = limits
                    if self.settings.get("debug_logging", True):
                        logger.info(f"[NSM SNAPSHOT] ryzenadj originals captured: {limits}")

        if self.settings.get("debug_logging", True):
            logger.info(
                "[NSM SNAPSHOT] Recorded originals before touching anything: "
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
