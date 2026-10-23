"""Wake-path regressions; no real display, audio, input or power writes."""
import asyncio
import subprocess
import signal
import threading
import os
import socket
import tempfile
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, Mock, patch

from main import Plugin


class DisplayDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nsm-display-")
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name) / "1000"
        self.runtime.mkdir()
        self.plugin = Plugin()
        self.override = patch.dict(os.environ, {"GAMESCOPE_WAYLAND_DISPLAY": ""})
        self.override.start()
        self.addCleanup(self.override.stop)

    def unix_socket(self, name):
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(listener.close)
        listener.bind(str(self.runtime / name))
        listener.listen(1)
        return listener

    def test_only_wayland_numbered_sockets_are_discovered(self):
        self.unix_socket("gamescope-0")
        self.unix_socket("gamescope-2")
        # Both regular files and *real sockets* can be auxiliary Gamescope data.
        self.unix_socket("gamescope-control")
        self.unix_socket("gamescope-stats")
        for name in ("gamescope-environment", "gamescope-0.lock", "gamescope-stats.lck", "gamescope-3"):
            (self.runtime / name).write_text("not a Wayland socket")
        (self.runtime / "gamescope-cache").mkdir()
        self.assertEqual(self.plugin._gamescope_display_sockets(str(self.runtime)), ["gamescope-0", "gamescope-2"])

    def test_no_socket_means_no_display(self):
        (self.runtime / "gamescope-0").write_text("regular file with a numeric name")
        self.assertEqual(self.plugin._gamescope_display_sockets(str(self.runtime)), [])

    def test_explicit_custom_socket_is_preserved(self):
        self.unix_socket("custom-display")
        with patch.dict(os.environ, {"GAMESCOPE_WAYLAND_DISPLAY": "custom-display"}):
            self.assertEqual(self.plugin._gamescope_display_sockets(str(self.runtime)), ["custom-display"])

    def test_absolute_override_is_scoped_to_its_runtime_directory(self):
        self.unix_socket("custom-display")
        other = Path(self.temp.name) / "1001"
        other.mkdir()
        with patch.dict(os.environ, {"GAMESCOPE_WAYLAND_DISPLAY": str(self.runtime / "custom-display")}):
            self.assertEqual(self.plugin._gamescope_display_sockets(str(self.runtime)), ["custom-display"])
            self.assertEqual(self.plugin._gamescope_display_sockets(str(other)), [])

    def test_sleep_and_wake_never_probe_auxiliary_sockets(self):
        self.unix_socket("gamescope-0")
        self.unix_socket("gamescope-control")
        self.unix_socket("gamescope-stats")
        for name in ("gamescope-environment", "gamescope-stats.lck", "gamescope-0.lock"):
            (self.runtime / name).write_text("auxiliary")
        import glob
        real_glob = glob.glob
        def paths(pattern):
            return [str(self.runtime)] if pattern == "/run/user/*" else real_glob(pattern)
        attempts = []
        def command(cmd, **kwargs):
            display = kwargs["env"]["GAMESCOPE_WAYLAND_DISPLAY"]
            attempts.append((display, cmd[-1]))
            if display != "gamescope-0":
                # The old broad glob attempted four calls per auxiliary socket,
                # each waiting two seconds for a Wayland response that never came.
                raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        self.plugin._get_session_user = Mock(return_value="deck")
        with patch("new_suspend_mode.display_audio.glob.glob", side_effect=paths), \
                patch("new_suspend_mode.display_audio.shutil.which", return_value="/usr/bin/gamescopectl"), \
                patch("new_suspend_mode.display_audio.subprocess.run", side_effect=command):
            self.plugin._set_gamescope_display(sleep=True)
            self.plugin._set_gamescope_display(sleep=False)
        self.assertEqual(attempts, [("gamescope-0", "1"), ("gamescope-0", "1"),
                                    ("gamescope-0", "0"), ("gamescope-0", "0")])


class DisplayRouteTests(unittest.TestCase):
    def setUp(self):
        self.plugin = Plugin()
        self.plugin._get_session_user = Mock(return_value="deck")
        self.plugin._save_runtime_state = Mock(return_value=True)
        self.plugin._write_sysfs = Mock(return_value=True)
        self.plugin._gamescope_display_sockets = Mock(return_value=["gamescope-0"])
        self.glob = patch("new_suspend_mode.display_audio.glob.glob", side_effect=lambda pattern:
                          ["/run/user/1000"] if pattern == "/run/user/*" else ["/run/user/1000/gamescope-0"])
        self.exists = patch("new_suspend_mode.display_audio.os.path.exists", return_value=True)
        self.which = patch("new_suspend_mode.display_audio.shutil.which", return_value="/usr/bin/gamescopectl")
        for helper in (self.glob, self.exists, self.which):
            helper.start()
            self.addCleanup(helper.stop)

    @staticmethod
    def success():
        return subprocess.CompletedProcess([], 0, stdout="", stderr="")

    def test_success_does_not_repeat_command_with_sudo(self):
        with patch("new_suspend_mode.display_audio.subprocess.run", return_value=self.success()) as run:
            self.plugin._set_gamescope_display(sleep=True)
            self.assertEqual(run.call_count, 2)
            self.assertEqual({call.args[0][1] for call in run.call_args_list},
                             {"drm_sleep_internal_screen", "drm_sleep_external_screen"})

    def test_wake_reuses_route_that_worked_on_entry(self):
        def result(cmd, **kwargs):
            return self.success() if cmd[0] == "sudo" else subprocess.CompletedProcess(cmd, 1, stdout="", stderr="denied")
        with patch("new_suspend_mode.display_audio.subprocess.run", side_effect=result) as run:
            self.plugin._set_gamescope_display(sleep=True)
            self.assertEqual(run.call_count, 4)
            run.reset_mock()
            self.plugin._set_gamescope_display(sleep=False)
            self.assertEqual(run.call_count, 2)
            self.assertTrue(all(call.args[0][0] == "sudo" for call in run.call_args_list))

    def test_stale_cached_route_still_tries_alternative(self):
        p = self.plugin
        p.gamescope_command_routes = {
            ("/run/user/1000", "gamescope-0", subcommand): 1
            for subcommand in ("drm_sleep_internal_screen", "drm_sleep_external_screen")
        }
        def result(cmd, **kwargs):
            return self.success() if cmd[0] != "sudo" else subprocess.CompletedProcess(cmd, 1, stdout="", stderr="denied")
        with patch("new_suspend_mode.display_audio.subprocess.run", side_effect=result) as run:
            p._set_gamescope_display(sleep=False)
            self.assertEqual(run.call_count, 4)
            self.assertEqual(set(p.gamescope_command_routes.values()), {0})

    def test_zero_exit_with_error_does_not_skip_fallback(self):
        def result(cmd, **kwargs):
            return self.success() if cmd[0] == "sudo" else subprocess.CompletedProcess(cmd, 0, stdout="", stderr="unsupported property")
        with patch("new_suspend_mode.display_audio.subprocess.run", side_effect=result) as run:
            self.plugin._set_gamescope_display(sleep=False)
            self.assertEqual(run.call_count, 4)

    def test_missing_socket_does_not_run_commands(self):
        with patch("new_suspend_mode.display_audio.os.path.exists", return_value=False), \
                patch("new_suspend_mode.display_audio.subprocess.run") as run:
            self.plugin._set_gamescope_display(sleep=False)
        run.assert_not_called()

    def test_tv_connectors_restored_even_when_commands_fail(self):
        p = self.plugin
        p.forced_off_connectors = ["card0-HDMI-A-1"]
        with patch("new_suspend_mode.display_audio.subprocess.run", side_effect=subprocess.TimeoutExpired("test", 2)):
            p._set_gamescope_display(sleep=False)
        p._write_sysfs.assert_called_once_with("/sys/class/drm/card0-HDMI-A-1/status", "detect")
        self.assertFalse(p.forced_off_connectors)

    def test_audio_timeout_keeps_other_fallbacks_and_is_bounded(self):
        def result(cmd, **kwargs):
            self.assertEqual(kwargs["timeout"], 2.0)
            if cmd[0] != "pactl":
                raise subprocess.TimeoutExpired(cmd, 2)
            return self.success()
        with patch("new_suspend_mode.display_audio.subprocess.run", side_effect=result) as run:
            self.plugin._set_audio_mute(False)
        self.assertEqual([call.args[0][0] for call in run.call_args_list], ["amixer", "wpctl", "pactl"])

    def test_timeout_names_the_endpoint_in_normal_logs(self):
        with patch("new_suspend_mode.display_audio.subprocess.run", side_effect=subprocess.TimeoutExpired("test", 2)), \
                self.assertLogs("NewSuspendMode", level="WARNING") as messages:
            self.plugin._set_gamescope_display(sleep=False)
        self.assertEqual(len(messages.output), 4)
        self.assertTrue(all("gamescope-0" in line and "elapsed=" in line and "route=" in line
                            for line in messages.output))


class WakeConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.plugin = Plugin()
        self.plugin.loop = asyncio.get_running_loop()

    async def test_hardware_restore_starts_while_frontend_is_slow(self):
        p = self.plugin
        p.is_background_mode = True
        restored = threading.Event()
        p._restore_system_power_and_display = Mock(side_effect=restored.set)
        p._update_inhibitor_state = Mock()
        p.suspend_in_progress = True  # No delayed hardware reset in this test.
        async def slow_frontend(*args):
            self.assertTrue(await asyncio.to_thread(restored.wait, 1), "Hardware waited for the frontend")
        with patch("new_suspend_mode.transitions.decky.emit", side_effect=slow_frontend):
            self.assertTrue(await p.exit_background_mode("power_button_wake"))
        p._restore_system_power_and_display.assert_called_once()
        self.assertFalse(p.transition_in_progress)

    async def test_failed_frontend_notification_still_restores_hardware(self):
        p = self.plugin
        p.is_background_mode = True
        p.suspend_in_progress = True
        p._restore_system_power_and_display = Mock()
        p._update_inhibitor_state = Mock()
        with patch("new_suspend_mode.transitions.decky.emit", side_effect=[RuntimeError("frontend unavailable"), None]):
            self.assertTrue(await p.exit_background_mode())
        p._restore_system_power_and_display.assert_called_once()

    async def test_slow_bluetooth_query_does_not_block_power_wake(self):
        p = self.plugin
        p.is_background_mode = True
        p.standby_mode = True
        entered = threading.Event()
        release = threading.Event()
        def bluetooth():
            entered.set()
            release.wait(2)
            return ["Controller"]
        p._newly_connected_bluetooth_gamepads = Mock(side_effect=bluetooth)
        query = asyncio.create_task(p._check_bluetooth_wake(30))
        try:
            self.assertTrue(await asyncio.to_thread(entered.wait, 1))
            p.is_background_mode = False  # Power wake ran while the D-Bus call was waiting.
            p.standby_mode = False
        finally:
            release.set()
        p.exit_background_mode = AsyncMock()
        self.assertFalse(await query)
        p.exit_background_mode.assert_not_awaited()

    async def test_bluetooth_result_from_previous_session_does_not_wake_new_session(self):
        p = self.plugin
        p.is_background_mode = p.standby_mode = True
        p.background_mode_entered_time = 100
        def bluetooth():
            p.background_mode_entered_time = 200
            return ["Old controller"]
        p._newly_connected_bluetooth_gamepads = Mock(side_effect=bluetooth)
        p.exit_background_mode = AsyncMock()
        self.assertFalse(await p._check_bluetooth_wake(30))
        p.exit_background_mode.assert_not_awaited()


class InputReleaseTests(unittest.TestCase):
    def test_independent_services_thaw_in_parallel_before_signals(self):
        p = Plugin()
        barrier = threading.Barrier(2)
        finished = set()
        signalled = []
        def thaw(cmd, **kwargs):
            barrier.wait(timeout=1)
            finished.add(cmd[-1].removesuffix(".service"))
            return subprocess.CompletedProcess(cmd, 0)
        def resume(daemon, sig):
            signalled.append((daemon, sig, daemon in finished))
            return []
        p._signal_daemon = Mock(side_effect=resume)
        with patch("new_suspend_mode.system_control.subprocess.run", side_effect=thaw):
            p._resume_controller_daemons()
        self.assertEqual(len(finished), 2)
        self.assertEqual(len(signalled), 2)
        self.assertTrue(all(sig == signal.SIGCONT and thawed for _, sig, thawed in signalled))

    def test_service_timeout_does_not_skip_sigcont(self):
        p = Plugin()
        p._signal_daemon = Mock(return_value=[])
        with patch("new_suspend_mode.system_control.subprocess.run", side_effect=subprocess.TimeoutExpired("test", 5)):
            p._resume_controller_daemons()
        self.assertEqual({call.args for call in p._signal_daemon.call_args_list},
                         {("inputplumber", signal.SIGCONT), ("hhd", signal.SIGCONT)})

    def test_device_reader_scan_is_not_before_input_release(self):
        p = Plugin()
        p.inhibited_inputs = ["test"]
        p._log_input_diagnostics = Mock()
        for name in ("_teardown_standby_wake_sources", "_uninhibit_all_inputs", "_flush_grabbed_inputs", "_rebind_gamepad_hids"):
            setattr(p, name, Mock())
        p._controller_daemons_look_frozen = Mock(return_value=False)
        p._release_all_gamepad_inputs()
        p._uninhibit_all_inputs.assert_called_once()
        p._log_input_diagnostics.assert_not_called()
        self.assertTrue(p.input_diagnostics_pending)
