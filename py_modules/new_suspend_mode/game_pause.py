"""Pause Steam-launched game processes without stopping Steam or its downloads."""
import glob
import os
import signal
import time
from typing import Any, Dict, Optional

from .constants import logger


class GamePauseMixin:
    # Shared session services must never be stopped, even if they inherited a game's
    # environment. Do not guess from executable paths: Proton also lives in common/.
    GAME_PAUSE_EXCLUDED = {
        "steam", "steamwebhelper", "steamservice", "steam-runtime-l",
        "gamescope", "gamescope-wl", "xwayland", "xorg", "systemd",
        "pipewire", "pipewire-pulse", "wireplumber", "inputplumber", "hhd",
        "plugin_loader", "decky-loader",
    }

    def _game_process_info(self, pid: int) -> Optional[Dict[str, Any]]:
        try:
            with open(f"/proc/{pid}/stat", "r") as f:
                stat = f.read()
            # comm may itself contain spaces and parentheses. Field 22 is starttime.
            fields = stat[stat.rfind(")") + 2:].split()
            comm = stat[stat.find("(") + 1:stat.rfind(")")].lower()
            with open(f"/proc/{pid}/environ", "rb") as f:
                env = dict(part.split(b"=", 1) for part in f.read().split(b"\0") if b"=" in part)
            app_id = next((env[k].decode("ascii") for k in (b"SteamGameId", b"SteamAppId")
                           if env.get(k, b"").isdigit() and int(env[k]) > 0), "")
            return {"pid": pid, "start_time": fields[19], "state": fields[0],
                    "comm": comm, "app_id": app_id}
        except (OSError, ValueError, IndexError, UnicodeError):
            return None

    def _game_pause_boot_id(self) -> str:
        with open("/proc/sys/kernel/random/boot_id", "r") as f:
            return f.read().strip()

    def _game_threads_stopped(self, pid: int) -> bool:
        for path in glob.glob(f"/proc/{pid}/task/[0-9]*/stat"):
            try:
                with open(path, "r") as f:
                    stat = f.read()
                if stat[stat.rfind(")") + 2:].split()[0] not in ("T", "Z", "X"):
                    return False
            except FileNotFoundError:
                continue  # Thread exited while being inspected.
        return True

    def _signal_game_process(self, entry: Dict[str, Any], sig: int) -> bool:
        """Use a stable PID handle and check identity before signalling (also on reload)."""
        if entry["boot_id"] != self._game_pause_boot_id():
            return False
        try:
            fd = os.pidfd_open(entry["pid"])
        except ProcessLookupError:
            return False
        try:
            current = self._game_process_info(entry["pid"])
            if not current or current["start_time"] != entry["start_time"]:
                return False
            signal.pidfd_send_signal(fd, sig)
            return True
        except ProcessLookupError:
            return False
        finally:
            os.close(fd)

    def _pause_running_games(self):
        if not self.settings.get("pause_running_games", True):
            return
        if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
            raise RuntimeError("Game pause requires Linux pidfd signal support")
        boot_id = self._game_pause_boot_id()
        # Exclude our ancestry too, so a development launch from Steam cannot freeze
        # the loader (or a shell that is hosting it).
        ancestors = {os.getpid(), 1}
        pid = os.getppid()
        while pid > 1 and pid not in ancestors:
            ancestors.add(pid)
            try:
                with open(f"/proc/{pid}/stat", "r") as f:
                    stat = f.read()
                pid = int(stat[stat.rfind(")") + 2:].split()[1])
            except (OSError, ValueError, IndexError):
                break

        try:
            # Re-scan after stopping parents to catch children forked during discovery.
            # A bounded wait also rejects processes stuck in uninterruptible I/O rather
            # than lowering clocks while a game is still executing.
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                added = False
                for path in glob.glob("/proc/[0-9]*/stat"):
                    pid = int(path.split("/")[2])
                    if pid in ancestors or pid in self.paused_game_processes:
                        continue
                    info = self._game_process_info(pid)
                    if (not info or not info["app_id"] or info["comm"] in self.GAME_PAUSE_EXCLUDED
                            or info["comm"].startswith(("gamescope", "steam-runtime", "steamwebhelper"))
                            or info["state"] in ("T", "t", "Z", "X")):
                        continue
                    entry = {k: info[k] for k in ("pid", "start_time", "app_id")}
                    entry["boot_id"] = boot_id
                    # Write ahead: never stop a process without a durable recovery record.
                    self.paused_game_processes[pid] = entry
                    if not self._save_runtime_state():
                        del self.paused_game_processes[pid]
                        raise RuntimeError("Could not record game pause for crash recovery")
                    if not self._signal_game_process(entry, signal.SIGSTOP):
                        del self.paused_game_processes[pid]
                    added = True

                pending = []
                for entry in list(self.paused_game_processes.values()):
                    info = self._game_process_info(entry["pid"])
                    if (info and info["start_time"] == entry["start_time"]
                            and not self._game_threads_stopped(entry["pid"])):
                        pending.append(entry["pid"])
                if not added and not pending:
                    logger.info(f"Paused {len(self.paused_game_processes)} game process(es).")
                    return
                time.sleep(0.03)
            raise RuntimeError("Timed out waiting for game processes to pause")
        except Exception:
            self._resume_running_games()
            raise

    def _resume_running_games(self):
        """Only resume processes we stopped; leave pre-existing stops untouched."""
        if not self.paused_game_processes:
            return
        for pid, entry in list(self.paused_game_processes.items()):
            try:
                self._signal_game_process(entry, signal.SIGCONT)
                del self.paused_game_processes[pid]
            except Exception as e:
                logger.error(f"Could not resume game process {pid}: {e}")
        self._save_runtime_state()

    async def _resume_games_after_system_sleep(self):
        # Called by both resume detectors; the transition lock makes repeats harmless.
        if not self.games_waiting_for_resume or self.is_background_mode:
            return
        await self.loop.run_in_executor(None, self._run_transition_locked, self._resume_running_games)
        self.games_waiting_for_resume = bool(self.paused_game_processes)
