"""Watches systemd-logind for suspend attempts and resumes."""
import time
import asyncio
import subprocess

from .constants import logger, WAKE_COOLDOWN_SECONDS, LOGIND_GRACE_SECONDS


class LogindWatcherMixin:
    """Watches systemd-logind for suspend attempts and resumes."""

    def _logind_watcher_worker(self):
        """Watches systemd-logind journal logs to intercept UI suspend clicks."""
        logger.info("Starting logind journal watcher worker...")
        while not self.stop_threads:
            proc = None
            try:
                cmd = ["journalctl", "-u", "systemd-logind", "-f", "-n", "0", "-o", "cat"]
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1
                )

                while not self.stop_threads and proc.poll() is None:
                    line = proc.stdout.readline()
                    if not line:
                        break

                    lower = line.lower()
                    now = time.time()

                    time_in_bg = (now - self.background_mode_entered_time) if self.is_background_mode else 999.0

                    # System resume from sleep detected via logind
                    if (
                        "operation 'sleep' finished" in lower
                        or "system is resuming" in lower
                    ):
                        logger.info("Logind reported system resume from sleep -> Enforcing wake cooldown.")
                        self.wake_cooldown_until = now + WAKE_COOLDOWN_SECONDS

                        # Quiet-hours RTC wake handling: a resume near the time we armed
                        # the RTC for is almost certainly our RTC alarm firing. Re-enter
                        # the plugin's standby so a controller can wake it as usual.
                        if self.rtc_wake_pending:
                            diff = abs(now - self.rtc_wake_target)
                            if diff <= 120:
                                logger.info(
                                    f"[NSM RTC WAKE] Resume at {int(now)}, target was "
                                    f"{self.rtc_wake_target} (diff {diff:.1f}s) -> entering standby."
                                )
                                self.rtc_wake_pending = False
                                self.rtc_wake_target = 0
                                self.rtc_wake_grace_until = now + 600.0
                                if self.loop and self.loop.is_running():
                                    asyncio.run_coroutine_threadsafe(
                                        self._enter_standby_after_rtc_wake(), self.loop
                                    )
                                continue
                            else:
                                logger.info(
                                    f"[NSM RTC WAKE] Resume at {int(now)} is far from the "
                                    f"RTC target {self.rtc_wake_target} (diff {diff:.1f}s); "
                                    "treating as a manual wake and clearing the alarm."
                                )
                                self._clear_rtc_wake()

                        if self.is_background_mode and time_in_bg > LOGIND_GRACE_SECONDS:
                            if self.loop and self.loop.is_running():
                                asyncio.run_coroutine_threadsafe(
                                    self.exit_background_mode("logind_resume"),
                                    self.loop
                                )
                        continue

                    if (
                        "inhibited by downloadinbackground" in lower
                        or "refusing operation" in lower
                        or "power key pressed to suspend" in lower
                        or "suspend key pressed to sleep" in lower
                        or "suspend entry requested" in lower
                    ):
                        logger.info(f"Logind journal suspend event: {line.strip()}")
                        # If in background mode, wake up after grace period
                        if self.is_background_mode:
                            if time_in_bg < LOGIND_GRACE_SECONDS:
                                logger.info(f"Ignoring logind suspend event during background entry grace period ({time_in_bg:.1f}s).")
                                continue
                            logger.info("Logind suspend event received while in background mode -> Waking system!")
                            self.wake_cooldown_until = now + WAKE_COOLDOWN_SECONDS
                            if self.loop and self.loop.is_running():
                                asyncio.run_coroutine_threadsafe(
                                    self.exit_background_mode("logind_wake"),
                                    self.loop
                                )
                            continue

                        # Ignore logind events during wake cooldown
                        if now < self.wake_cooldown_until:
                            continue

                        if self._is_active_download():
                            self._trigger_suspend_intercepted("logind_journal")
                        else:
                            # Nothing to protect: let SteamOS suspend exactly as it normally would.
                            self._update_inhibitor_state()

            except Exception as e:
                logger.error(f"Error in logind watcher: {e}")
            finally:
                if proc:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                time.sleep(2.0)
