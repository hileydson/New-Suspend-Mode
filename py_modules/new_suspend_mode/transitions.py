"""Entering and leaving the plugin's mode, and the real suspend."""
import time
import asyncio
import subprocess

from .constants import decky, logger, WAKE_COOLDOWN_SECONDS


class TransitionsMixin:
    """Entering and leaving the plugin's mode, and the real suspend."""

    # ==========================================
    # Background Mode Transitions
    # ==========================================
    async def enter_background_mode(self, reason: str = "manual") -> bool:
        if self.is_background_mode:
            return True

        now = time.time()
        # Do not enter background mode if wake cooldown is active!
        if now < self.wake_cooldown_until:
            logger.info(f"Blocked enter_background_mode (reason: {reason}) because system just woke up.")
            return False

        # Standby is decided by the setting, never by how the mode was entered. Deriving
        # it from the reason string meant an entry through the HUD countdown
        # ("countdown_completed") silently ran WITHOUT standby: no controller could wake
        # the console, and the external pads were detached as part of the normal lockout.
        self.standby_mode = bool(self.settings.get("standby_on_power_off", False))
        logger.info(
            f"Entering {'Standby' if self.standby_mode else 'Background Download'} Mode (reason: {reason})."
        )
        self.is_background_mode = True
        self.background_mode_entered_time = now
        self.last_loop_timestamp = now

        self._acquire_sleep_inhibitor()
        t0 = time.time()
        self.transition_in_progress = True
        try:
            await self.loop.run_in_executor(None, self._run_transition_locked, self._apply_power_saving_and_screen_off)
        finally:
            self.transition_in_progress = False
        logger.info(f"[DBG] Power saving applied in {time.time() - t0:.2f}s")

        # Reset loop timestamp immediately after setup to avoid false clock-jump
        self.last_loop_timestamp = time.time()

        await decky.emit("background_mode_changed", {
            "is_background_mode": True,
            "reason": reason,
            "standby": self.standby_mode,
            # Without a download there is nothing to put in the HUD, so the frontend
            # shows just the plugin logo before the screen goes black.
            "has_download": self._is_active_download(),
        })
        return True

    async def exit_background_mode(self, reason: str = "manual") -> bool:
        if not self.is_background_mode:
            logger.info(f"[DBG] exit_background_mode({reason}) ignored: not in background mode.")
            return False

        logger.info(f"Exiting Background Download Mode (reason: {reason}).")
        self.wake_cooldown_until = time.time() + WAKE_COOLDOWN_SECONDS
        self.is_background_mode = False
        t0 = time.time()
        self.transition_in_progress = True
        try:
            await self.loop.run_in_executor(None, self._run_transition_locked, self._restore_system_power_and_display)
        finally:
            self.transition_in_progress = False
        logger.info(f"[DBG] System restored in {time.time() - t0:.2f}s")
        self._update_inhibitor_state()

        await decky.emit("background_mode_changed", {"is_background_mode": False, "reason": reason})

        # Record this wake, so the periodic watchdog can tell "already handled this
        # wake" from "a new wake happened, do it again".
        self.last_wake_time = time.time()
        # Scheduled 8 s after the wake: run the hard reset unconditionally, as the user
        # asked. The periodic watchdog honours a cooldown after this so one wake does
        # not get the hard reset over and over.
        if self.loop and self.loop.is_running():
            self.loop.create_task(self._auto_hard_reset_after_wake(8.0))
        return True

    def _run_transition_locked(self, func):
        """Serializes enter/exit hardware transitions so restore never races a half-finished apply."""
        with self.transition_lock:
            try:
                func()
            except Exception as e:
                logger.error(f"[DBG] Transition {func.__name__} failed: {e}")
                if func == self._restore_system_power_and_display:
                    # A restore that died halfway must never leave input grabbed or the
                    # controller daemons frozen: recovering from that needs a reboot.
                    try:
                        self._release_all_gamepad_inputs()
                    except Exception as inner:
                        logger.error(f"Emergency input release also failed: {inner}")

    async def trigger_suspend(self):
        logger.info("Executing systemctl suspend...")
        # Makes _plugin_should_act() False, so the power key listener hands the button
        # back to logind and the inhibitor is dropped before suspend is requested.
        self.suspend_in_progress = True
        try:
            if self.is_background_mode:
                self.is_background_mode = False
                await self.loop.run_in_executor(None, self._run_transition_locked, self._restore_system_power_and_display)

            self._release_sleep_inhibitor()
            self._clear_stale_sleep_masks()
            # Give the listener thread (0.3s poll) time to release the power device.
            await asyncio.sleep(1.0)

            try:
                subprocess.run(["systemctl", "suspend"], check=False, timeout=15.0)
            except Exception as e:
                logger.error(f"Failed to execute systemctl suspend: {e}")
            # Stay out of the way while the kernel actually goes down and comes back.
            await asyncio.sleep(2.0)
        finally:
            self.suspend_in_progress = False
            self.wake_cooldown_until = max(self.wake_cooldown_until, time.time() + WAKE_COOLDOWN_SECONDS)
