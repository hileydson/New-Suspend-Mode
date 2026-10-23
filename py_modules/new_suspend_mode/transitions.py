"""Entering and leaving the plugin's mode, and the real suspend."""
import time
import asyncio
import subprocess

from .constants import decky, logger, WAKE_COOLDOWN_SECONDS

WAKE_PRESENTATION_SECONDS = 3.0
# Match WAKE_FADE_MS in src/state.ts.
WAKE_FADE_SECONDS = 0.3


class TransitionsMixin:
    """Entering and leaving the plugin's mode, and the real suspend."""

    # ==========================================
    # Background Mode Transitions
    # ==========================================
    async def enter_background_mode(self, reason: str = "manual") -> bool:
        if self.transition_in_progress or self.suspend_in_progress or not self._effective_enabled(max_age=0.0):
            return False
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
        except Exception as e:
            logger.error(f"Background entry aborted: {e}")
            self.is_background_mode = False
            await self.loop.run_in_executor(None, self._run_transition_locked, self._restore_system_power_and_display)
            self._update_inhibitor_state()
            await decky.emit("background_mode_changed", {"is_background_mode": False, "reason": "entry_failed"})
            return False
        finally:
            self.transition_in_progress = False
        logger.info(f"[DBG] Power saving applied in {time.time() - t0:.2f}s")

        # Reset loop timestamp immediately after setup to avoid false clock-jump
        self.last_loop_timestamp = time.time()

        if not self.is_background_mode:
            return False
        await decky.emit("background_mode_changed", {
            "is_background_mode": True,
            "reason": reason,
            "standby": self.standby_mode,
            # Without a download there is nothing to put in the HUD, so the frontend
            # shows just the plugin logo before the screen goes black.
            "has_download": self._is_active_download(),
        })
        return True

    async def exit_background_mode(self, reason: str = "manual", requested_at: float = 0.0) -> bool:
        if not self.is_background_mode:
            logger.info(f"[DBG] exit_background_mode({reason}) ignored: not in background mode.")
            return False

        logger.info(f"Exiting Background Download Mode (reason: {reason}).")
        if requested_at:
            logger.info(f"[NSM WAKE TIMING] request queue={time.monotonic() - requested_at:.3f}s via={reason}")
        self.wake_cooldown_until = time.time() + WAKE_COOLDOWN_SECONDS
        self.is_background_mode = False
        self.transition_in_progress = True
        t0 = time.monotonic()
        present_wake = not self.suspend_in_progress and not self.stop_threads
        self.wake_presentation_active = present_wake
        self.last_wake_time = time.time()
        if present_wake:
            self.wake_id = max(self.wake_id + 1, int(time.time() * 1000))
            self.wake_phase = "restoring"
            # Queue the opaque presentation before lighting the panel. A missing
            # frontend must not strand hardware in its low-power state.
            await self._announce_wake(reason)
        restore = self.loop.run_in_executor(None, self._run_transition_locked, self._restore_system_power_and_display)
        try:
            if not present_wake:
                await self._announce_wake(reason)
            await restore
            logger.info(f"[DBG] System restored in {time.monotonic() - t0:.2f}s")
            if present_wake and not self.stop_threads:
                # Count from the wake request, not from the end of restoration. The
                # extra hardware reset also finishes beneath the presentation.
                await asyncio.sleep(max(0.0, WAKE_PRESENTATION_SECONDS - (time.monotonic() - t0)))
                await self._auto_hard_reset_after_wake(0.0, during_wake=True)
                self.wake_phase = "fading"
                await self._announce_wake(reason)
                await asyncio.sleep(WAKE_FADE_SECONDS)
        finally:
            try:
                if present_wake:
                    # Also runs after cancellation or a failed restore. Never leave
                    # native input grabbed or a game paused behind a React overlay.
                    await self.loop.run_in_executor(None, self._run_transition_locked, self._finish_wake_presentation)
            finally:
                self.wake_presentation_active = False
                self.wake_phase = ""
                self.transition_in_progress = False
                self.wake_cooldown_until = time.time() + WAKE_COOLDOWN_SECONDS
                await self._announce_wake(reason)
        self._update_inhibitor_state()
        logger.info(f"[NSM WAKE TIMING] wake ready={time.monotonic() - t0:.3f}s presentation={present_wake}")
        if self.input_diagnostics_pending:
            self.input_diagnostics_pending = False
            await self.loop.run_in_executor(None, self._run_transition_locked_safe,
                                           lambda: self._log_input_diagnostics("after restore"))
        return True

    async def _announce_wake(self, reason: str):
        try:
            await asyncio.wait_for(decky.emit("background_mode_changed", {
                "is_background_mode": False, "reason": reason,
                "wake_phase": self.wake_phase, "wake_id": self.wake_id,
            }), timeout=0.5)
        except Exception as e:
            logger.warning(f"Could not announce wake ({self.wake_phase or 'ready'}): {e}")

    def _finish_wake_presentation(self):
        try:
            self._release_all_gamepad_inputs()
        finally:
            if not self.games_waiting_for_resume:
                self._resume_running_games()

    def _run_transition_locked(self, func):
        """Serializes enter/exit hardware transitions so restore never races a half-finished apply."""
        with self.transition_lock:
            try:
                func()
            except Exception as e:
                logger.error(f"[DBG] Transition {getattr(func, '__name__', type(func).__name__)} failed: {e}")
                if func == self._restore_system_power_and_display:
                    # A restore that died halfway must never leave input grabbed or the
                    # controller daemons frozen: recovering from that needs a reboot.
                    try:
                        self._release_all_gamepad_inputs()
                    except Exception as inner:
                        logger.error(f"Emergency input release also failed: {inner}")
                    if not self.games_waiting_for_resume:
                        self._resume_running_games()
                else:
                    raise

    async def trigger_suspend(self, reason: str = "real_sleep"):
        if self.suspend_in_progress:
            return
        logger.info("Executing systemctl suspend...")
        # Makes _plugin_should_act() False, so the power key listener hands the button
        # back to logind and the inhibitor is dropped before suspend is requested.
        self.suspend_in_progress = True
        self.games_waiting_for_resume = bool(self.paused_game_processes)
        self.game_resume_fallback_at = time.time() + 20.0
        try:
            # Every real-sleep path must bypass the Steam frontend sleep patch,
            # including charger removal and quiet hours (not just low battery).
            await decky.emit("real_suspend_requested", {"reason": reason})
            if self.is_background_mode:
                await self.exit_background_mode(reason)

            self._release_sleep_inhibitor()
            self._clear_stale_sleep_masks()
            # Give the listener thread (0.3s poll) time to release the power device.
            await asyncio.sleep(1.0)

            result = await self.loop.run_in_executor(
                None, lambda: subprocess.run(["systemctl", "suspend"], check=False, timeout=15.0)
            )
            if result.returncode != 0:
                raise RuntimeError(f"systemctl suspend exited with {result.returncode}")
            # Stay out of the way while the kernel actually goes down and comes back.
            await asyncio.sleep(2.0)
        except Exception as e:
            logger.error(f"Failed to execute systemctl suspend: {e}")
            if self.is_background_mode:
                self.games_waiting_for_resume = False
            else:
                await self._resume_games_after_system_sleep()
        finally:
            self.suspend_in_progress = False
            self.wake_cooldown_until = max(self.wake_cooldown_until, time.time() + WAKE_COOLDOWN_SECONDS)
