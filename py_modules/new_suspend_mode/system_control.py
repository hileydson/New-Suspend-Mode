"""sysfs writes, the controller daemons, and Steam's process scheduling."""
import os
import glob
import subprocess
import signal
from typing import List, Tuple

from .constants import logger, SCHED_BATCH, SCHED_IDLE, STEAM_UI_COMMS


class SystemControlMixin:
    """sysfs writes, the controller daemons, and Steam's process scheduling."""

    def _write_sysfs(self, path: str, value: str) -> bool:
        """Writes a string value to sysfs/proc, with automatic passwordless sudo tee fallback."""
        try:
            with open(path, "w") as f:
                f.write(str(value))
            return True
        except Exception:
            try:
                p = subprocess.run(
                    ["sudo", "tee", path],
                    input=f"{value}\n",
                    text=True,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1.0,
                )
                return p.returncode == 0
            except Exception:
                return False

    def _find_daemon_pids(self, daemon: str) -> List[int]:
        """
        Finds PIDs whose executable (argv[0] or python script argv[1]) is exactly the daemon name.
        Never uses pkill -f, which also matches its own sudo parent and freezes it (hanging the plugin).
        """
        pids = []
        my_pid = os.getpid()
        for proc_dir in glob.glob("/proc/[0-9]*"):
            try:
                pid = int(os.path.basename(proc_dir))
                if pid == my_pid:
                    continue
                with open(os.path.join(proc_dir, "cmdline"), "rb") as f:
                    args = [a.decode("utf-8", errors="ignore") for a in f.read().split(b"\x00") if a]
                if not args:
                    continue
                exe = os.path.basename(args[0])
                # First non-flag argument after the interpreter (handles 'python3 -sP /usr/bin/hhd')
                script = next((os.path.basename(a) for a in args[1:] if not a.startswith("-")), "")
                if exe == daemon or (exe.startswith("python") and script == daemon):
                    pids.append(pid)
            except Exception:
                pass
        return pids

    def _signal_daemon(self, daemon: str, sig: int) -> List[int]:
        pids = self._find_daemon_pids(daemon)
        for pid in pids:
            try:
                os.kill(pid, sig)
            except Exception as e:
                logger.warning(f"Could not send signal {sig} to {daemon} ({pid}): {e}")
        return pids

    def _pause_controller_daemons(self):
        """
        Freezes controller mapping daemons (InputPlumber and Handheld Daemon) with SIGSTOP
        and systemctl freeze, so they stop translating button presses into the virtual
        controller Steam reads. Plugin runs as root (plugin.json flags), so signals are
        sent directly by PID.
        """
        self.frozen_daemons = []
        for daemon in ["inputplumber", "hhd"]:
            try:
                pids = self._signal_daemon(daemon, signal.SIGSTOP)
                subprocess.run(
                    ["systemctl", "freeze", f"{daemon}.service"],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5.0,
                )
                if pids:
                    self.frozen_daemons.append(daemon)
                    logger.info(f"Froze controller daemon {daemon} (pids={pids}).")
            except Exception as e:
                logger.warning(f"Freezing daemon {daemon} failed: {e}")

    def _controller_daemons_look_frozen(self) -> bool:
        """True if InputPlumber/HHD are sitting stopped, e.g. after a crash mid-lockout."""
        for daemon in ["inputplumber", "hhd"]:
            for pid in self._find_daemon_pids(daemon):
                try:
                    with open(f"/proc/{pid}/stat", "r") as f:
                        stat = f.read()
                    state = stat[stat.rfind(")") + 2:].split()[0]
                except Exception:
                    continue
                if state in ("T", "t"):
                    return True
        return False

    def _resume_controller_daemons(self, quiet: bool = False):
        """
        Unfreezes the controller mapping daemons.

        Called before the virtual controllers are rebound on purpose: a frozen daemon has
        the button presses from the lockout still queued on its input fds, and it replays
        them the moment it runs again. Letting it replay while its output device is still
        unbound is what keeps a press made with the screen off from opening the Quick
        Access Menu on wake.
        """
        for daemon in ["inputplumber", "hhd"]:
            try:
                subprocess.run(
                    ["systemctl", "thaw", f"{daemon}.service"],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5.0,
                )
                pids = self._signal_daemon(daemon, signal.SIGCONT)
                if pids and not quiet:
                    logger.info(f"Resumed controller daemon {daemon} (pids={pids}).")
            except Exception as e:
                logger.warning(f"Resuming daemon {daemon} failed: {e}")
        self.frozen_daemons = []

    def _iter_process_scheduling(self) -> List[Tuple[int, str, int, int]]:
        """Returns (pid, comm, nice, sched_policy) for every process, for the repair below."""
        found: List[Tuple[int, str, int, int]] = []
        my_pid = os.getpid()
        for proc_dir in glob.glob("/proc/[0-9]*"):
            try:
                pid = int(os.path.basename(proc_dir))
                if pid == my_pid:
                    continue
                with open(os.path.join(proc_dir, "stat"), "r") as f:
                    stat = f.read()
                # The comm field is wrapped in parentheses and may itself contain spaces.
                close = stat.rfind(")")
                comm = stat[stat.find("(") + 1:close]
                fields = stat[close + 2:].split()
                # /proc/pid/stat: field 19 is nice, field 41 is the scheduling policy;
                # both are offset by 3 here because state is the first field after comm.
                nice = int(fields[16])
                policy = int(fields[38])
                found.append((pid, comm, nice, policy))
            except Exception:
                continue
        return found

    def _heal_steam_scheduling(self) -> int:
        """
        Puts Steam's own processes back on normal CPU and I/O scheduling.

        Older versions of this plugin dropped everything matching 'steam' to SCHED_IDLE
        and nice 19 while the screen was off. Processes Steam started during that window
        inherited it and were never found again on wake, which left Gaming Mode
        permanently sluggish. Nothing throttles Steam any more, and this runs on every
        wake (and at startup) to repair consoles that are still in that state.
        """
        victims: List[int] = []
        for pid, comm, nice, policy in self._iter_process_scheduling():
            starved = nice > 0 or policy in (SCHED_BATCH, SCHED_IDLE)
            if not starved:
                continue
            if comm.lower() in STEAM_UI_COMMS:
                victims.append(pid)
                continue
            # Also rescue a running game that inherited idle scheduling from Steam.
            if policy == SCHED_IDLE:
                try:
                    with open(f"/proc/{pid}/cmdline", "rb") as f:
                        cmdline = f.read().decode("utf-8", errors="ignore")
                    if "/steamapps/common/" in cmdline:
                        victims.append(pid)
                except Exception:
                    pass

        if not victims:
            return 0

        pid_strs = [str(p) for p in victims]
        subprocess.run(
            ["renice", "-n", "0", "-p"] + pid_strs,
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for pid in pid_strs:
            for cmd in (
                ["chrt", "-o", "-p", "0", pid],
                ["ionice", "-c", "2", "-n", "4", "-p", pid],
            ):
                try:
                    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0)
                except Exception:
                    pass
        logger.info(f"Reset CPU/IO scheduling to normal for {len(victims)} Steam process(es).")
        return len(victims)
