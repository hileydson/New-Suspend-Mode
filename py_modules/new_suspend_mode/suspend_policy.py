"""What a sleep request turns into: the plugin's mode, the quiet-hours real sleep, the RTC wake."""
import os
import time
import datetime
import asyncio
from typing import Dict, Any, Optional, Tuple

from .constants import decky, logger, WAKE_COOLDOWN_SECONDS, LOGIND_GRACE_SECONDS


class SuspendPolicyMixin:
    """What a sleep request turns into: the plugin's mode, the quiet-hours real sleep, the RTC wake."""

    # ==========================================
    # Suspend Interception & Logind Watcher
    # ==========================================
    def _trigger_suspend_intercepted(self, source: str = "unknown") -> str:
        """
        Called whenever a suspend attempt is detected while downloads are active.

        Returns the verdict, so the caller knows what happened: 'wake', 'ignored',
        'standby', 'hud', or 'allow' when the suspend should simply go ahead as usual.
        The Steam power menu needs that last answer: it is the one path where the plugin
        has to hand the suspend back after deciding not to take it.
        """
        now = time.time()
        time_in_bg = (now - self.background_mode_entered_time) if self.is_background_mode else 999.0
        # If currently in background mode, any suspend attempt after grace period is a WAKE action!
        if self.is_background_mode:
            if time_in_bg < LOGIND_GRACE_SECONDS:
                logger.info(f"Ignoring suspend intercept during background entry grace period ({time_in_bg:.1f}s).")
                return "ignored"
            logger.info("Suspend attempt detected while in background mode -> Waking system!")
            self.wake_cooldown_until = now + WAKE_COOLDOWN_SECONDS
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.exit_background_mode("suspend_attempt_wake"),
                    self.loop
                )
            return "wake"

        if not self._effective_enabled(max_age=0.0):
            self._update_inhibitor_state()
            return "allow"

        # Cooldown: Ignore any suspend request if system just woke up within 12 seconds
        if now < self.wake_cooldown_until or self.transition_in_progress or self.wake_presentation_active:
            logger.info("Ignoring suspend attempt because system just woke up from background mode.")
            return "ignored"

        # Double check against the real state, not the last poll: a download paused a
        # moment ago must already count as idle here.
        if not self._refresh_download_state():
            if self.settings.get("standby_on_power_off", False):
                if now - self.last_suspend_intercept_time < 3.0:
                    return "ignored"
                self.last_suspend_intercept_time = now
                logger.info(
                    f"[NSM SLEEP SOURCE] Sleep requested from '{source}' with standby enabled "
                    "-> standby splash, then entering."
                )
                if self.loop and self.loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self.request_standby(f"standby_{source}"), self.loop
                    )
                return "standby"
            logger.info("Suspend attempt not intercepted: Download is paused or idle. Allowing normal suspend.")
            # The inhibitor goes first, or the suspend we just allowed would be blocked.
            self._update_inhibitor_state()
            return "allow"

        # Debounce to prevent double trigger within 3 seconds
        if now - self.last_suspend_intercept_time < 3.0:
            return "ignored"
        self.last_suspend_intercept_time = now

        logger.info(f"[NSM SLEEP SOURCE] Suspend attempt from '{source}' intercepted while downloading -> Showing HUD!")
        self._acquire_sleep_inhibitor()

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                decky.emit("on_suspend_intercepted", {
                    "download_info": self.download_info,
                    "hud_timeout": self.settings.get("hud_timeout_seconds", 5),
                }),
                self.loop
            )
        return "hud"

    RTC_WAKEALARM = "/sys/class/rtc/rtc0/wakealarm"

    def _quiet_hours_bounds(self) -> Optional[Tuple[int, int]]:
        """
        (start_minutes_of_day, end_minutes_of_day) when the option is on and valid.

        Values are 0..1430, snapped to 10-minute steps so the slider's values and the
        bounds always line up. An empty period (start == end) returns None.
        """
        if not self.settings.get("enter_real_sleep_after_time", False):
            return None
        try:
            start = int(self.settings.get("real_sleep_start_minutes", 0))
            end = int(self.settings.get("real_sleep_end_minutes", 420))
        except (TypeError, ValueError):
            return None
        start = max(0, min(1430, (start // 10) * 10))
        end = max(0, min(1430, (end // 10) * 10))
        if start == end:
            return None
        return (start, end)

    def _inside_quiet_hours(self) -> bool:
        """
        True when the clock is inside the user's quiet-hours period.

        Period is [start, end): the start minute counts, the end minute does not.
        Natural wrap-around for a period that crosses midnight: 23:00 - 07:00 means
        23:00 through 06:59, so 02:00 is inside and 07:00 is outside.
        """
        bounds = self._quiet_hours_bounds()
        if not bounds:
            return False
        start, end = bounds
        now = datetime.datetime.now()
        current = now.hour * 60 + now.minute
        if start < end:
            return start <= current < end
        return current >= start or current < end

    def _next_quiet_hours_end(self) -> Optional[int]:
        """Unix epoch of the next time the quiet-hours period ends."""
        bounds = self._quiet_hours_bounds()
        if not bounds:
            return None
        _start, end = bounds
        end_hour, end_min = divmod(end, 60)
        now = datetime.datetime.now()
        target = now.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        return int(target.timestamp())

    def _schedule_rtc_wake(self, epoch_time: int) -> bool:
        """
        Programs the real-time clock to wake the console at the given Unix time.

        Standard kernel interface, works on any handheld or desktop that exposes it.
        Writing "0" first is required: the kernel refuses a new alarm while one is still
        armed, so clearing before setting is the only reliable way.
        """
        if not os.path.exists(self.RTC_WAKEALARM):
            logger.info("RTC wakealarm not available; cannot schedule a wake.")
            return False
        if epoch_time <= time.time() + 30:
            logger.info(f"RTC wake refused: {epoch_time} is too close to now.")
            return False
        if not self._write_sysfs(self.RTC_WAKEALARM, "0"):
            return False
        time.sleep(0.1)
        if not self._write_sysfs(self.RTC_WAKEALARM, str(int(epoch_time))):
            return False
        logger.info(
            f"RTC wake armed for {datetime.datetime.fromtimestamp(epoch_time).isoformat()} "
            f"(in {int(epoch_time - time.time())} s)."
        )
        return True

    def _clear_rtc_wake(self):
        """Disarms the RTC alarm. Safe to call even if nothing was armed."""
        if os.path.exists(self.RTC_WAKEALARM):
            try:
                self._write_sysfs(self.RTC_WAKEALARM, "0")
            except Exception:
                pass
        self.rtc_wake_pending = False
        self.rtc_wake_target = 0

    async def _maybe_real_sleep_instead(self, reason: str) -> bool:
        """
        Inside the quiet-hours period with nothing downloading, runs the real SteamOS
        sleep instead of entering the plugin's own mode. If the wake-at-end option is on,
        also programs the RTC to wake the console at the end of the period, where the
        resume handler will put it back into the plugin's standby. Returns True when it
        took the sleep over.
        """
        if not self._inside_quiet_hours():
            return False
        if self._is_active_download():
            logger.info(
                "[NSM QUIET HOURS] Inside the period, but a download is active; "
                "entering the plugin's own mode as usual."
            )
            return False
        bounds = self._quiet_hours_bounds()
        logger.info(
            f"[NSM QUIET HOURS] Inside the period ({bounds[0] // 60:02d}:{bounds[0] % 60:02d} - "
            f"{bounds[1] // 60:02d}:{bounds[1] % 60:02d}) "
            f"and nothing is downloading (reason: {reason}) -> real SteamOS sleep."
        )
        if self.settings.get("wake_at_period_end", False):
            end_epoch = self._next_quiet_hours_end()
            if end_epoch and self._schedule_rtc_wake(end_epoch):
                self.rtc_wake_pending = True
                self.rtc_wake_target = end_epoch
                self._save_runtime_state()
        await self.trigger_suspend()
        return True

    async def _enter_standby_after_rtc_wake(self):
        """
        Called after a resume that was triggered by the RTC alarm the plugin set up at the
        start of a quiet-hours sleep. Short delay so the kernel finishes bringing the
        hardware back, then enters the plugin's standby for a controller to wake later.

        Wake cooldown is cleared explicitly: it exists to stop the power-button press that
        woke the console from immediately re-sleeping it, but an RTC-triggered wake had no
        button press, so the cooldown is spurious here and would reject request_standby.
        """
        await asyncio.sleep(5.0)
        if self.is_background_mode:
            return
        if (not self.settings.get("standby_on_power_off", False)
                or not self.settings.get("wake_at_period_end", False)):
            logger.info("[NSM RTC WAKE] Standby option is off; staying awake.")
            return
        if not self._effective_enabled(max_age=0.0):
            # The RTC may already have been armed before power was removed.
            # AC-only mode must not become a battery-powered standby on this wake.
            if self.settings.get("enable_plugin_when_plugged_in", False):
                await self.trigger_suspend("rtc_wake_plugin_inactive")
            return
        self.wake_cooldown_until = 0.0
        logger.info("[NSM RTC WAKE] Entering the plugin's new suspend mode.")
        # Both `_maybe_real_sleep_instead` (called from request_standby) and the main
        # loop's periodic check will see us as inside quiet hours if the RTC fired a
        # hair before the end minute, and would re-trigger real sleep in a loop. The
        # direct enter_background_mode path skips both.
        if not self.is_background_mode:
            await self.enter_background_mode("quiet_hours_rtc_end")

    async def request_standby(self, reason: str = "standby") -> bool:
        """
        Shows the standby splash first, then enters the mode.

        The splash has to be drawn while the panel is still lit. Entering the mode first
        and drawing after put the logo on a screen whose backlight was already at zero,
        which is why nothing appeared to show up at all.
        """
        if (not self._effective_enabled(max_age=0.0) or self.is_background_mode
                or self.transition_in_progress or self.wake_presentation_active
                or self.standby_request_pending or self.suspend_in_progress):
            return False
        if time.time() < self.wake_cooldown_until:
            logger.info("Standby request ignored: the console just woke up.")
            return False

        # Quiet-hours short-circuit: before entering our mode, run the real SteamOS
        # sleep if the configured hour has passed and no download is active.
        if await self._maybe_real_sleep_instead(reason):
            return False

        self.standby_request_pending = True
        try:
            splash_seconds = max(0, int(self.settings.get("hud_timeout_seconds", 5)))
            if splash_seconds > 0:
                await self.loop.run_in_executor(
                    None, self._run_transition_locked_safe, self._lock_inputs_for_splash
                )
            await decky.emit("on_standby_requested", {
                "splash_seconds": splash_seconds,
                "reason": reason,
            })
            if splash_seconds <= 0:
                return await self.enter_background_mode(reason)

            # The frontend draws the splash and then enters. If it never does (not
            # running, or an error), the mode is entered here so the power button is
            # never a no-op.
            await asyncio.sleep(splash_seconds + 2.5)
            if not self.is_background_mode and time.time() >= self.wake_cooldown_until:
                logger.info("Frontend did not enter standby in time; entering from the backend.")
                return await self.enter_background_mode(reason)
            return True
        finally:
            self.standby_request_pending = False
            if not self.is_background_mode and not self.transition_in_progress:
                await self.loop.run_in_executor(
                    None, self._run_transition_locked_safe, self._release_splash_lockout_if_aborted
                )

    async def trigger_suspend_intercept(self) -> Dict[str, Any]:
        """
        API called by the frontend when the Steam client intercepts a suspend.

        The verdict comes back because the frontend is the only one that can hand a
        suspend over to SteamOS after the fact: when this says 'allow', the Steam power
        menu's Sleep has to go through as usual.
        """
        verdict = self._trigger_suspend_intercepted("frontend_hook")
        return {
            "verdict": verdict,
            "intercepted": verdict in ("hud", "standby", "wake"),
            "download_info": self.download_info,
        }

    async def request_menu_sleep(self) -> Dict[str, Any]:
        """Decide the menu's Sleep using current power, not the frontend's last poll."""
        if not self._effective_enabled(max_age=0.0):
            self._update_inhibitor_state()
            return {"verdict": "allow"}
        if self.settings.get("standby_on_power_off", False):
            entered = await self.request_standby("standby_power_menu")
            if not entered and not self._effective_enabled(max_age=0.0):
                return {"verdict": "allow"}
            return {"verdict": "standby" if entered else "ignored"}
        return await self.trigger_suspend_intercept()
