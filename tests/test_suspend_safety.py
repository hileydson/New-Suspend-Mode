"""Run with: PYTHONPATH=py_modules:. python3 -m unittest discover -s tests -v

Hardware operations are mocked. Process tests signal only child workers created here.
"""
import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

from main import Plugin
from new_suspend_mode.constants import DEFAULT_SETTINGS
from new_suspend_mode.power_saving import PowerSavingMixin
from new_suspend_mode.restore import RestoreMixin


class BatteryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.battery = self.root / "BAT0"
        self.battery.mkdir()
        (self.battery / "type").write_text("Battery")
        (self.battery / "capacity").write_text("65")
        self.plugin = Plugin()

    def read_battery(self, status, online=None, supply_name="ADP1"):
        (self.battery / "status").write_text(status)
        supplies = [str(self.battery)]
        if online is not None:
            adapter = self.root / supply_name
            adapter.mkdir(exist_ok=True)
            (adapter / "type").write_text("USB")
            (adapter / "online").write_text(online)
            supplies.append(str(adapter))
        def paths(pattern):
            return [str(self.battery)] if pattern.endswith("BAT*") else supplies
        with patch("main.glob.glob", side_effect=paths):
            return self.plugin._get_battery_info(max_age=0)

    def test_discharging_is_not_charging(self):
        info = self.read_battery("Discharging", "0")
        self.assertFalse(info["is_charging"])
        self.assertFalse(info["is_plugged"])
        self.assertTrue(info["power_known"])

    def test_adapter_names_and_full_battery(self):
        for name in ("ACAD", "ADP1", "ucsi-source-psy-USBC000:001"):
            with self.subTest(name=name):
                info = self.read_battery("Full", "1", name)
                self.assertTrue(info["is_plugged"])
                self.assertFalse(info["is_charging"])

    def test_online_overrides_stale_battery_status(self):
        self.assertFalse(self.read_battery("Charging", "0")["is_plugged"])
        self.assertTrue(self.read_battery("Discharging", "1")["is_plugged"])

    def test_missing_adapter_falls_back_to_exact_status(self):
        self.assertTrue(self.read_battery("Charging")["is_plugged"])
        self.assertFalse(self.read_battery("Discharging")["is_plugged"])
        self.assertFalse(self.read_battery("Unknown")["power_known"])


@unittest.skipUnless(hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"), "Linux pidfd required")
class GameProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.plugin = Plugin()
        self.plugin.runtime_state_file = str(Path(self.temp.name) / "state.json")
        self.workers = []
        self.addCleanup(self.clean_workers)

    def clean_workers(self):
        for proc in self.workers:
            if proc.poll() is None:
                os.kill(proc.pid, signal.SIGCONT)
                proc.kill()
            proc.wait(timeout=5)

    def worker(self, game=True, comm=None):
        env = {k: v for k, v in os.environ.items() if k not in ("SteamAppId", "SteamGameId")}
        if game:
            env["SteamAppId"] = "12345"
        code = "import time; time.sleep(60)"
        if comm:
            code = f"import ctypes; ctypes.CDLL(None).prctl(15, {comm.encode()!r}, 0, 0, 0); " + code
        proc = subprocess.Popen([sys.executable, "-c", code], env=env)
        self.workers.append(proc)
        # Wait until exec has installed the child's environment/name.
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            info = self.plugin._game_process_info(proc.pid)
            if info and bool(info["app_id"]) == game and (not comm or info["comm"] == comm):
                return proc
            time.sleep(0.01)
        self.fail("Worker did not start")

    def scan_workers(self):
        import glob
        real_glob = glob.glob
        return patch("new_suspend_mode.game_pause.glob.glob", side_effect=lambda pattern: [
            f"/proc/{proc.pid}/stat" for proc in self.workers
        ] if pattern == "/proc/[0-9]*/stat" else real_glob(pattern))

    def wait_state(self, proc, stopped):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            info = self.plugin._game_process_info(proc.pid)
            if info and (info["state"] == "T") == stopped:
                return
            time.sleep(0.01)
        self.fail(f"Process {proc.pid} did not reach stopped={stopped}")

    def test_pause_and_reload_recovery_only_touch_games(self):
        game = self.worker()
        other = self.worker(game=False)
        steam = self.worker(comm="steam")
        with self.scan_workers():
            self.plugin._pause_running_games()
        self.wait_state(game, True)
        self.wait_state(other, False)
        self.wait_state(steam, False)
        state = json.loads(Path(self.plugin.runtime_state_file).read_text())
        self.assertEqual([entry["pid"] for entry in state["paused_game_processes"]], [game.pid])
        reloaded = Plugin()
        reloaded.runtime_state_file = self.plugin.runtime_state_file
        reloaded._load_runtime_state(state)
        reloaded._resume_running_games()
        self.wait_state(game, False)
        self.assertFalse(reloaded.paused_game_processes)

    def test_previously_stopped_game_is_not_resumed(self):
        game = self.worker()
        os.kill(game.pid, signal.SIGSTOP)
        self.wait_state(game, True)
        with self.scan_workers():
            self.plugin._pause_running_games()
        self.assertFalse(self.plugin.paused_game_processes)
        self.plugin._resume_running_games()
        self.wait_state(game, True)

    def test_no_signal_without_durable_record(self):
        game = self.worker()
        with self.scan_workers(), patch.object(self.plugin, "_save_runtime_state", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "record game pause"):
                self.plugin._pause_running_games()
        self.wait_state(game, False)

    def test_partial_pause_failure_rolls_back(self):
        first, second = self.worker(), self.worker()
        original = self.plugin._signal_game_process
        def send(entry, sig):
            if entry["pid"] == second.pid and sig == signal.SIGSTOP:
                raise PermissionError("test stop failure")
            return original(entry, sig)
        with self.scan_workers(), patch.object(self.plugin, "_signal_game_process", side_effect=send):
            with self.assertRaises(PermissionError):
                self.plugin._pause_running_games()
        self.wait_state(first, False)
        self.wait_state(second, False)
        self.assertFalse(self.plugin.paused_game_processes)

    def test_old_boot_or_reused_pid_is_not_signalled(self):
        game = self.worker()
        info = self.plugin._game_process_info(game.pid)
        entry = {"pid": game.pid, "boot_id": self.plugin._game_pause_boot_id(),
                 "start_time": info["start_time"], "app_id": "12345"}
        with patch("new_suspend_mode.game_pause.signal.pidfd_send_signal") as send:
            self.assertFalse(self.plugin._signal_game_process({**entry, "boot_id": "old-boot"}, signal.SIGCONT))
            self.assertFalse(self.plugin._signal_game_process({**entry, "start_time": "0"}, signal.SIGCONT))
            send.assert_not_called()

    def test_resume_failure_keeps_recovery_record(self):
        game = self.worker()
        with self.scan_workers():
            self.plugin._pause_running_games()
        with patch.object(self.plugin, "_signal_game_process", side_effect=PermissionError("test resume failure")):
            self.plugin._resume_running_games()
        self.plugin._clear_runtime_state()
        state = json.loads(Path(self.plugin.runtime_state_file).read_text())
        self.assertEqual(state["paused_game_processes"][0]["pid"], game.pid)
        self.plugin._resume_running_games()
        self.wait_state(game, False)

    def test_setting_can_disable_pause(self):
        game = self.worker()
        self.plugin.settings["pause_running_games"] = False
        with self.scan_workers():
            self.plugin._pause_running_games()
        self.wait_state(game, False)


class TransitionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.plugin = Plugin()
        self.plugin.loop = asyncio.get_running_loop()
        self.plugin.settings.update(enabled=True, enable_plugin_when_plugged_in=False)

    async def test_ac_only_unplug_suspends_even_when_effectively_disabled(self):
        p = self.plugin
        p.settings.update(enabled=False, enable_plugin_when_plugged_in=True)
        p.is_background_mode = True
        p._get_battery_info = Mock(return_value={"is_plugged": False, "power_known": True})
        p._clear_rtc_wake = Mock()
        p.trigger_suspend = AsyncMock()
        self.assertFalse(p._effective_enabled())
        self.assertTrue(await p._suspend_if_ac_only_unplugged())
        p.trigger_suspend.assert_awaited_once_with("ac_disconnected")
        p._clear_rtc_wake.assert_called_once()

    async def test_unplug_does_not_suspend_other_modes_or_unknown_power(self):
        p = self.plugin
        p.trigger_suspend = AsyncMock()
        for enabled, ac_only, background, known, plugged, transitioning in (
            (True, False, True, True, False, False),
            (False, False, True, True, False, False),
            (False, True, False, True, False, False),
            (False, True, True, False, False, False),
            (False, True, True, True, True, False),
            (False, True, True, True, False, True),
        ):
            p.settings.update(enabled=enabled, enable_plugin_when_plugged_in=ac_only)
            p.is_background_mode = background
            p.transition_in_progress = transitioning
            p._get_battery_info = Mock(return_value={"power_known": known, "is_plugged": plugged})
            self.assertFalse(await p._suspend_if_ac_only_unplugged())
        p.trigger_suspend.assert_not_awaited()

    async def test_disabled_monitor_still_handles_charger_removal(self):
        p = self.plugin
        p.settings.update(enabled=False, enable_plugin_when_plugged_in=True)
        p.is_background_mode = True
        p._get_battery_info = Mock(return_value={"is_plugged": False, "power_known": True})
        p._clear_rtc_wake = Mock()
        async def suspend(reason):
            p.stop_threads = True
        p.trigger_suspend = AsyncMock(side_effect=suspend)
        with patch("new_suspend_mode.monitor_loop.asyncio.sleep", new_callable=AsyncMock):
            await asyncio.wait_for(p._background_monitor_loop(), timeout=1)
        p.trigger_suspend.assert_awaited_once_with("ac_disconnected")

    async def test_disabled_monitor_recovers_missing_resume_notification(self):
        p = self.plugin
        p.settings.update(enabled=False, enable_plugin_when_plugged_in=False)
        p.games_waiting_for_resume = True
        p.paused_game_processes = {123: {"pid": 123}}
        p._update_inhibitor_state = Mock()
        def resume():
            p.paused_game_processes.clear()
            p.stop_threads = True
        p._resume_running_games = Mock(side_effect=resume)
        with patch("new_suspend_mode.monitor_loop.asyncio.sleep", new_callable=AsyncMock):
            await asyncio.wait_for(p._background_monitor_loop(), timeout=1)
        p._resume_running_games.assert_called_once()
        self.assertFalse(p.games_waiting_for_resume)

    async def test_entry_failure_restores_and_reports_failure(self):
        p = self.plugin
        p._apply_power_saving_and_screen_off = Mock(side_effect=RuntimeError("pause failed"))
        p._restore_system_power_and_display = Mock()
        p._acquire_sleep_inhibitor = Mock()
        p._update_inhibitor_state = Mock()
        with patch("new_suspend_mode.transitions.decky.emit", new_callable=AsyncMock):
            self.assertFalse(await p.enter_background_mode())
        p._apply_power_saving_and_screen_off.assert_called_once()
        p._restore_system_power_and_display.assert_called_once()
        self.assertFalse(p.is_background_mode)
        self.assertFalse(p.transition_in_progress)

    async def test_sleep_handoff_keeps_games_paused_until_resume(self):
        p = self.plugin
        p.is_background_mode = True
        p.paused_game_processes = {123: {"pid": 123}}
        order = []
        def restore():
            self.assertTrue(p.games_waiting_for_resume)
            order.append("restore")
        p._restore_system_power_and_display = restore
        p._resume_running_games = Mock(side_effect=lambda: p.paused_game_processes.clear())
        p._update_inhibitor_state = Mock()
        p._release_sleep_inhibitor = Mock(side_effect=lambda: order.append("release"))
        p._clear_stale_sleep_masks = Mock()
        def suspend(*args, **kwargs):
            self.assertTrue(p.paused_game_processes)
            order.append("suspend")
            return subprocess.CompletedProcess(args, 0)
        with patch("new_suspend_mode.transitions.subprocess.run", side_effect=suspend), \
                patch("new_suspend_mode.transitions.asyncio.sleep", new_callable=AsyncMock), \
                patch("new_suspend_mode.transitions.decky.emit", new_callable=AsyncMock) as emit:
            await p.trigger_suspend("ac_disconnected")
        self.assertEqual(order, ["restore", "release", "suspend"])
        self.assertEqual(emit.await_args_list[0].args[0], "real_suspend_requested")
        p._resume_running_games.assert_not_called()
        await p._resume_games_after_system_sleep()
        await p._resume_games_after_system_sleep()
        p._resume_running_games.assert_called_once()
        self.assertFalse(p.games_waiting_for_resume)

    async def test_failed_sleep_resumes_games(self):
        p = self.plugin
        p.paused_game_processes = {123: {"pid": 123}}
        p._resume_running_games = Mock(side_effect=lambda: p.paused_game_processes.clear())
        p._release_sleep_inhibitor = Mock()
        p._clear_stale_sleep_masks = Mock()
        with patch("new_suspend_mode.transitions.subprocess.run", return_value=subprocess.CompletedProcess([], 1)), \
                patch("new_suspend_mode.transitions.asyncio.sleep", new_callable=AsyncMock), \
                patch("new_suspend_mode.transitions.decky.emit", new_callable=AsyncMock):
            await p.trigger_suspend()
        p._resume_running_games.assert_called_once()
        self.assertFalse(p.games_waiting_for_resume)
        self.assertFalse(p.suspend_in_progress)


class SettingsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.plugin = Plugin()
        self.plugin.settings_file = str(Path(self.temp.name) / "settings.json")
        self.plugin._update_inhibitor_state = Mock()
        self.plugin.exit_background_mode = AsyncMock()

    async def test_activation_modes_and_power(self):
        p = self.plugin
        for enabled, ac_only, plugged, expected in (
            (False, False, False, False), (False, False, True, False),
            (True, False, False, True), (True, False, True, True),
            (False, True, False, False), (False, True, True, True),
            (True, True, False, False), (True, True, True, True),
        ):
            with self.subTest(enabled=enabled, ac_only=ac_only, plugged=plugged):
                p.settings.update(enabled=enabled, enable_plugin_when_plugged_in=ac_only)
                p._get_battery_info = Mock(return_value={"is_plugged": plugged})
                self.assertEqual(p._effective_enabled(), expected)

    async def test_enabling_either_mode_turns_other_off_and_persists(self):
        p = self.plugin
        await p.save_settings({"enabled": True})
        self.assertTrue(p.settings["enabled"])
        self.assertFalse(p.settings["enable_plugin_when_plugged_in"])
        await p.save_settings({"enable_plugin_when_plugged_in": True})
        self.assertFalse(p.settings["enabled"])
        self.assertTrue(p.settings["enable_plugin_when_plugged_in"])
        await p.save_settings({"enabled": True, "enable_plugin_when_plugged_in": True})
        self.assertFalse(p.settings["enabled"])
        self.assertTrue(p.settings["enable_plugin_when_plugged_in"])
        self.assertEqual(json.loads(Path(p.settings_file).read_text()), p.settings)
        await p.save_settings({"enable_plugin_when_plugged_in": False})
        self.assertFalse(p._effective_enabled())

    async def test_legacy_activation_settings_migrate_without_changing_single_modes(self):
        for stored, expected in (
            ({"enabled": True}, (True, False)),
            ({"enabled": False}, (False, False)),
            ({"enabled": False, "enable_plugin_when_plugged_in": False}, (False, False)),
            ({"enabled": True, "enable_plugin_when_plugged_in": True}, (False, True)),
            ({"enable_plugin_when_plugged_in": True}, (False, True)),
        ):
            with self.subTest(stored=stored):
                Path(self.plugin.settings_file).write_text(json.dumps(stored))
                loaded = Plugin()
                loaded.settings_file = self.plugin.settings_file
                loaded._load_settings()
                self.assertEqual((loaded.settings["enabled"], loaded.settings["enable_plugin_when_plugged_in"]), expected)

    async def test_fresh_install_and_reset_restore_every_default(self):
        p = self.plugin
        p._load_settings()
        self.assertEqual(json.loads(Path(p.settings_file).read_text()), DEFAULT_SETTINGS)
        for key in ("enable_plugin_when_plugged_in", "standby_on_power_off",
                    "enter_real_sleep_after_time", "wake_at_period_end", "limit_download_speed"):
            self.assertTrue(p.settings[key])
        self.assertFalse(p.settings["enabled"])
        p.settings = {key: not val if isinstance(val, bool) else val + 10
                      for key, val in DEFAULT_SETTINGS.items()}
        p.settings["obsolete_setting"] = True
        p._save_settings_sync()
        restored = await p.reset_defaults()
        self.assertEqual(restored, DEFAULT_SETTINGS)
        self.assertEqual(json.loads(Path(p.settings_file).read_text()), DEFAULT_SETTINGS)
        loaded = Plugin()
        loaded.settings_file = p.settings_file
        loaded._load_settings()
        self.assertEqual(loaded.settings, DEFAULT_SETTINGS)
        restored["enabled"] = True
        self.assertFalse(p.settings["enabled"])

    async def test_reset_save_failure_keeps_existing_file_and_settings(self):
        p = self.plugin
        p.settings.update(enabled=True, enable_plugin_when_plugged_in=False, min_battery_threshold=22)
        previous = p.settings.copy()
        p._save_settings_sync()
        with patch("main.os.replace", side_effect=OSError("test write failure")):
            with self.assertRaises(RuntimeError):
                await p.reset_defaults()
        self.assertEqual(p.settings, previous)
        self.assertEqual(json.loads(Path(p.settings_file).read_text()), previous)

    async def test_switching_to_ac_only_on_battery_exits_existing_mode(self):
        p = self.plugin
        p.settings.update(enabled=True, enable_plugin_when_plugged_in=False)
        p.is_background_mode = True
        p._get_battery_info = Mock(return_value={"is_plugged": False})
        await p.save_settings({"enable_plugin_when_plugged_in": True})
        p.exit_background_mode.assert_awaited_once_with("disabled_in_settings")

    async def test_menu_sleep_checks_fresh_power_without_automatic_entry_on_plug(self):
        p = self.plugin
        p._get_battery_info = Mock(return_value={"is_plugged": False})
        p.request_standby = AsyncMock(return_value=True)
        self.assertEqual((await p.request_menu_sleep())["verdict"], "allow")
        p.request_standby.assert_not_awaited()
        p._get_battery_info = Mock(return_value={"is_plugged": True})
        # Reading status on plug does not itself start standby.
        self.assertTrue(p._effective_enabled())
        p.request_standby.assert_not_awaited()
        p._get_battery_info.reset_mock()
        self.assertEqual((await p.request_menu_sleep())["verdict"], "standby")
        p._get_battery_info.assert_called_once_with(max_age=0.0)
        p.request_standby.assert_awaited_once_with("standby_power_menu")

    async def test_sleep_intercept_allows_stock_sleep_on_battery(self):
        p = self.plugin
        p._get_battery_info = Mock(return_value={"is_plugged": False})
        p._refresh_download_state = Mock(return_value=True)
        self.assertEqual(p._trigger_suspend_intercepted(), "allow")
        p._refresh_download_state.assert_not_called()

    async def test_rtc_wake_without_ac_returns_to_real_sleep(self):
        p = self.plugin
        p._get_battery_info = Mock(return_value={"is_plugged": False})
        p.trigger_suspend = AsyncMock()
        p.enter_background_mode = AsyncMock()
        with patch("new_suspend_mode.suspend_policy.asyncio.sleep", new_callable=AsyncMock):
            await p._enter_standby_after_rtc_wake()
        p.trigger_suspend.assert_awaited_once_with("rtc_wake_plugin_inactive")
        p.enter_background_mode.assert_not_awaited()

    async def test_always_on_mode_still_respects_quiet_hours(self):
        p = self.plugin
        p.settings.update(enabled=True, enable_plugin_when_plugged_in=False, wake_at_period_end=False)
        p._inside_quiet_hours = Mock(return_value=True)
        p._is_active_download = Mock(return_value=False)
        p.trigger_suspend = AsyncMock()
        self.assertTrue(await p._maybe_real_sleep_instead("test"))
        p.trigger_suspend.assert_awaited_once()

    async def test_disabled_plugin_does_not_act_on_old_rtc_wake(self):
        p = self.plugin
        p.settings.update(enabled=False, enable_plugin_when_plugged_in=False)
        p.trigger_suspend = AsyncMock()
        p.enter_background_mode = AsyncMock()
        with patch("new_suspend_mode.suspend_policy.asyncio.sleep", new_callable=AsyncMock):
            await p._enter_standby_after_rtc_wake()
        p.trigger_suspend.assert_not_awaited()
        p.enter_background_mode.assert_not_awaited()


class OrderingTests(unittest.TestCase):
    def test_pause_precedes_every_hardware_change(self):
        p = Plugin()
        p._pause_running_games = Mock(side_effect=RuntimeError("pause refused"))
        p._snapshot_power_originals = Mock()
        with self.assertRaises(RuntimeError):
            PowerSavingMixin._apply_power_saving_and_screen_off(p)
        p._snapshot_power_originals.assert_not_called()

    def test_game_resume_follows_hardware_and_input_restore(self):
        p = Plugin()
        order = []
        for name in ("_restore_backlight", "_restore_download_pacing", "_heal_steam_scheduling",
                     "_restore_platform_profile", "_restore_apu_power_limits", "_restore_cpu_settings",
                     "_restore_gpu_settings", "_restore_audio", "_restore_leds", "_release_all_gamepad_inputs",
                     "_resume_running_games"):
            setattr(p, name, Mock(side_effect=lambda name=name: order.append(name)))
        p._restore_targets_snapshot = Mock(return_value={})
        p._converge_restore = Mock(return_value=[])
        p._verify_and_force_restore = Mock(return_value=[])
        p._arm_watchdog_from_targets = Mock()
        RestoreMixin._restore_system_power_and_display(p)
        self.assertEqual(order[-1], "_resume_running_games")
        p.games_waiting_for_resume = True
        p._resume_running_games.reset_mock()
        RestoreMixin._restore_system_power_and_display(p)
        p._resume_running_games.assert_not_called()


if __name__ == "__main__":
    unittest.main()
