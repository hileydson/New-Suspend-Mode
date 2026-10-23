"""The systemd sleep inhibitor, and the single answer to 'may the plugin act right now?'."""
import os
import time
import subprocess

from .constants import logger


class SleepInhibitorMixin:
    """The systemd sleep inhibitor, and the single answer to 'may the plugin act right now?'."""

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
            "--who=NewSuspendMode",
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

    def _effective_enabled(self, max_age: float = 2.0) -> bool:
        """
        True iff the plugin should behave as enabled right now.

        AC-only and always-on are exclusive modes. AC-only takes precedence even
        for stale/legacy settings containing both switches. Sleep requests bypass
        the battery cache so plugging in immediately before Sleep works too.
        """
        if self.settings.get("enable_plugin_when_plugged_in", False):
            try:
                bat = self._get_battery_info(max_age=max_age)
                return bool(bat and bat.get("is_plugged"))
            except Exception:
                return False
        return bool(self.settings.get("enabled", False))

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
        return self.is_background_mode or self.wake_presentation_active or self._is_active_download()

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
