"""The periodic loop: downloads, battery, quiet hours and the automatic suspends."""
import os
import time
import asyncio

from .constants import (
    decky,
    logger,
    ACTIVE_LOOP_INTERVAL,
    IDLE_LOOP_INTERVAL,
    DISABLED_LOOP_INTERVAL,
    WAKE_COOLDOWN_SECONDS,
    BT_CONNECT_GRACE_SECONDS,
    TELEMETRY_INTERVAL,
)


class MonitorLoopMixin:
    """The periodic loop: downloads, battery, quiet hours and the automatic suspends."""

    # ==========================================
    # Periodic Background Loop (Download & Battery)
    # ==========================================
    async def _check_bluetooth_wake(self, time_in_bg: float) -> bool:
        if not self.standby_mode or not self.settings.get("wake_on_bluetooth_connect", True):
            return False
        entered_at = self.background_mode_entered_time
        # D-Bus can take seconds when an adapter is busy. Never block the event
        # loop that is also receiving Power and USB/controller wake requests.
        connected = await self.loop.run_in_executor(None, self._newly_connected_bluetooth_gamepads)
        if (not self.is_background_mode or not self.standby_mode or self.transition_in_progress
                or self.background_mode_entered_time != entered_at):
            return False
        if connected and time_in_bg > BT_CONNECT_GRACE_SECONDS:
            logger.info(f"Bluetooth controller connected in standby ({', '.join(connected)}) -> waking.")
            await self.exit_background_mode("bluetooth_controller_connected")
            return True
        return False

    async def _suspend_if_ac_only_unplugged(self) -> bool:
        """Handle loss of AC before the disabled-plugin shortcut stops monitoring."""
        if (not self.is_background_mode or self.transition_in_progress or self.suspend_in_progress
                or not self.settings.get("enable_plugin_when_plugged_in", False)):
            return False
        bat = self._get_battery_info(max_age=0.0)
        # An unreadable power supply is not evidence of an unplug.
        if not bat.get("power_known") or bat["is_plugged"]:
            return False
        logger.info("AC-only background mode lost external power -> real SteamOS sleep.")
        self._clear_rtc_wake()
        await self.trigger_suspend("ac_disconnected")
        return True

    async def _background_monitor_loop(self):
        logger.info("Starting background monitor loop...")
        self.last_loop_timestamp = time.time()
        interval = ACTIVE_LOOP_INTERVAL
        while not self.stop_threads:
            try:
                await asyncio.sleep(interval)

                now = time.time()
                dt = now - self.last_loop_timestamp
                self.last_loop_timestamp = now
                enabled = self._effective_enabled()
                slept_for = interval

                # Poll fast only when there is something to watch over. Idle means the
                # plugin stays out of the way and barely touches the disk.
                if self.is_background_mode or self.games_waiting_for_resume:
                    interval = ACTIVE_LOOP_INTERVAL
                elif not enabled:
                    interval = DISABLED_LOOP_INTERVAL
                elif self._is_active_download():
                    interval = ACTIVE_LOOP_INTERVAL
                else:
                    interval = IDLE_LOOP_INTERVAL

                # 0. Kernel Sleep Resume Detection: a gap far larger than the sleep we
                # just did means the machine was actually suspended in between.
                time_in_bg = (now - self.background_mode_entered_time) if self.is_background_mode else 999.0
                if dt > (slept_for + 10.0) and time_in_bg > 10.0:
                    logger.info(
                        f"System wake from kernel suspend detected (dt={dt:.1f}s, time_in_bg={time_in_bg:.1f}s)! "
                        "Enforcing wake cooldown and exiting background mode."
                    )
                    self.wake_cooldown_until = now + WAKE_COOLDOWN_SECONDS
                    if not self.suspend_in_progress:
                        await self._resume_games_after_system_sleep()
                    if self.is_background_mode:
                        self.is_background_mode = False
                        self.transition_in_progress = True
                        try:
                            await self.loop.run_in_executor(
                                None, self._run_transition_locked, self._restore_system_power_and_display
                            )
                        finally:
                            self.transition_in_progress = False
                        self._update_inhibitor_state()
                        await decky.emit("background_mode_changed", {
                            "is_background_mode": False,
                            "reason": "system_resume_clock_jump",
                        })

                    # Quiet-hours RTC wake handling, independent of logind journal messages.
                    # The journal path may miss the resume event on some distros (different
                    # log phrasing, journald not up yet), so the clock-jump path has to
                    # own the hand-off into our new suspend mode as well.
                    if self.rtc_wake_pending:
                        diff = abs(now - self.rtc_wake_target)
                        if diff <= 180:
                            logger.info(
                                f"[NSM RTC WAKE] Clock-jump resume at {int(now)}, target was "
                                f"{self.rtc_wake_target} (diff {diff:.1f}s) -> entering new suspend mode."
                            )
                            self.rtc_wake_pending = False
                            self.rtc_wake_target = 0
                            self.rtc_wake_grace_until = now + 600.0
                            self._save_runtime_state()
                            asyncio.create_task(self._enter_standby_after_rtc_wake())
                        else:
                            logger.info(
                                f"[NSM RTC WAKE] Clock-jump resume at {int(now)} is far from the "
                                f"RTC target {self.rtc_wake_target} (diff {diff:.1f}s); "
                                "treating as a manual wake and clearing the alarm."
                            )
                            self._clear_rtc_wake()

                # A successful systemctl call only queues suspend. The journal/clock
                # detectors resume games on wake; this timeout also recovers a rejected
                # or very short sleep if neither detector reported it.
                if (self.games_waiting_for_resume and not self.suspend_in_progress
                        and now >= self.game_resume_fallback_at):
                    await self._resume_games_after_system_sleep()

                if (self.paused_game_processes and not self.games_waiting_for_resume
                        and not self.is_background_mode and not self.transition_in_progress):
                    await self.loop.run_in_executor(
                        None, self._run_transition_locked, self._resume_running_games
                    )

                if await self._suspend_if_ac_only_unplugged():
                    continue

                if not enabled and not self.is_background_mode:
                    self._update_inhibitor_state()
                    continue

                # 1. Native Download & Network Detection
                is_dl = self._refresh_download_state()

                # Sync inhibitor state
                self._update_inhibitor_state()

                # Safety net: input must never stay blocked outside background mode.
                # A dead console is the worst failure this plugin could cause, so it is
                # checked every pass rather than trusted to the exit path alone.
                if (
                    not self.is_background_mode
                    and not self.transition_in_progress
                    and not self.standby_request_pending
                    and not self.wake_presentation_active
                    and (self.inhibited_inputs or self.grabbed_gamepad_fds)
                ):
                    logger.warning("Input was still blocked outside background mode; releasing it now.")
                    self._uninhibit_all_inputs()
                    self._release_all_gamepad_inputs()

                # Same reasoning for the display: a screen left at "no signal" outside
                # the mode is as bad as dead input, and on a single-display desktop it
                # would look like the machine died. Checked every pass rather than
                # trusted to the exit path alone.
                if (
                    not self.is_background_mode
                    and not self.transition_in_progress
                    and self.forced_off_connectors
                ):
                    logger.warning(
                        "Display connectors were still forced off outside background "
                        f"mode ({', '.join(self.forced_off_connectors)}); restoring them now."
                    )
                    self._set_gamescope_display(sleep=False)

                # A restore can be undone a second or two AFTER it finishes, because
                # changing the ACPI profile makes the firmware re-apply its own limits on
                # its own schedule. The restore itself has stopped looking by then, so a
                # console that was verified back to normal can quietly go slow again.
                if self.post_restore_until and not self.is_background_mode and not self.transition_in_progress:
                    if now < self.post_restore_until:
                        undone = self._recheck_after_restore()
                        if undone:
                            logger.warning(
                                f"[NSM POST-RESTORE] Something undid the restore; put back: {undone}"
                            )
                    else:
                        self.post_restore_until = 0.0
                        self.post_restore_targets = {}
                        self.post_restore_marks = {}

                # Permanent watchdog: a safety net for the cases none of the paths above
                # catch. Runs quietly every ~20s while NOT in the mode, and corrects
                # ONLY values that match the plugin's own cap exactly. See the function.
                if self.watchdog_targets or self.watchdog_ryzenadj:
                    self._throttle_watchdog()

                # 2. In Background Mode Checks
                if self.is_background_mode and not self.transition_in_progress:
                    # Keep the panels we dimmed dark (Steam re-lights them on its own)
                    for bp in list(self.saved_brightness.keys()):
                        bpow = os.path.join(os.path.dirname(bp), "bl_power")
                        try:
                            with open(bp, "r") as f:
                                if int(f.read().strip()) > 0:
                                    self._write_sysfs(bp, "0")
                        except Exception:
                            pass
                        try:
                            with open(bpow, "r") as pf:
                                if pf.read().strip() != "4":
                                    self._write_sysfs(bpow, "4")
                        except Exception:
                            pass

                    # Keep the lockout airtight: drop anything buffered, and grab plus
                    # inhibit devices that showed up after entering (a pad waking up, a
                    # recreated virtual controller) so they cannot reach Steam either.
                    self._flush_grabbed_inputs()
                    self._grab_new_inputs()
                    self._inhibit_all_inputs()

                    # A USB/dongle controller that connects AFTER standby began has no wake
                    # capability unless this adds it, and its buttons would act on the
                    # console in the window before the next grab/inhibit pass.
                    if self.standby_mode:
                        self._refresh_standby_wake_sources()

                    # A Bluetooth controller connecting is itself the wake signal: there is
                    # no button to press, the pairing is the request for the console back.
                    if await self._check_bluetooth_wake(time_in_bg):
                        continue
                    if not self.is_background_mode or self.transition_in_progress:
                        continue

                    # Quiet hours while already in the mode: a session that began at
                    # 22:50 reaches 23:00 while sitting here, and the user chose the
                    # real sleep for that case too. The exit comes first so the mode's
                    # restore runs cleanly; the real suspend follows.
                    if (
                        self.standby_mode
                        and self._inside_quiet_hours()
                        and not self._is_active_download()
                        and time.time() >= self.rtc_wake_grace_until
                    ):
                        logger.info(
                            "[NSM QUIET HOURS] Entered the quiet-hours period while in our mode; "
                            "exiting it and running real SteamOS sleep."
                        )
                        if self.settings.get("wake_at_period_end", False):
                            end_epoch = self._next_quiet_hours_end()
                            if end_epoch and self._schedule_rtc_wake(end_epoch):
                                self.rtc_wake_pending = True
                                self.rtc_wake_target = end_epoch
                                self._save_runtime_state()
                        await self.trigger_suspend("quiet_hours_real_sleep")
                        continue

                    if now - self.last_telemetry_time >= TELEMETRY_INTERVAL:
                        self.last_telemetry_time = now
                        self._log_power_telemetry()

                    bat = self._get_battery_info()

                    # Condition A: Low battery auto-suspend
                    min_thresh = int(self.settings.get("min_battery_threshold", 15))
                    if not bat["is_charging"] and bat["capacity"] <= min_thresh:
                        logger.warning(
                            f"Battery level {bat['capacity']}% <= {min_thresh}%. "
                            "Auto-suspending to protect battery!"
                        )
                        await decky.emit("battery_critical_suspend", {
                            "capacity": bat["capacity"],
                            "threshold": min_thresh,
                        })
                        await self.trigger_suspend("low_battery")
                        continue

                    # Condition B: Downloads finished or paused auto-suspend.
                    # Never in standby: there the console is meant to sit and wait for a
                    # controller, so suspending it for lack of a download would defeat it.
                    if not is_dl and not self.standby_mode:
                        elapsed_since_dl = now - self.last_download_active_time
                        auto_sleep_delay = max(30.0, float(self.settings.get("auto_suspend_delay_seconds", 120)))

                        if elapsed_since_dl >= auto_sleep_delay:
                            logger.info(
                                f"Downloads inactive or completed ({elapsed_since_dl:.1f}s inactive). "
                                "Auto-suspending system!"
                            )
                            await decky.emit("downloads_completed_suspend", {
                                "elapsed_seconds": elapsed_since_dl,
                            })
                            await self.trigger_suspend("downloads_completed")
                            continue

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in background monitor loop: {e}")
                await asyncio.sleep(2.0)
