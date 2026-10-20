"""Crash-safe record of every reversible change, so a restart can still undo it."""
import os
import json
from typing import Dict, Any

from .constants import logger


class RuntimeStateMixin:
    """Crash-safe record of every reversible change, so a restart can still undo it."""

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
            # Connectors forced to "no signal". Persisted so a crash cannot leave a
            # desktop with no display until the next replug.
            "forced_off_connectors": list(self.forced_off_connectors),
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
        self.forced_off_connectors = [
            str(c) for c in (state.get("forced_off_connectors") or []) if c
        ]
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
