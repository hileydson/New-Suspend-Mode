"""Download pacing: the cgroup CPU quota and the tc bandwidth limit."""
import os
import glob
import subprocess
import shutil
from typing import Optional, List, Set, Tuple

from .constants import logger, CPU_QUOTA_PERIOD


class DownloadPacingMixin:
    """Download pacing: the cgroup CPU quota and the tc bandwidth limit."""

    # ==========================================
    # Download Pacing (the "handheld console" profile)
    # ==========================================
    def _steam_cgroup_dir(self) -> Optional[str]:
        """
        The cgroup v2 directory that already holds the main Steam process.

        Its cpu.max is written in place rather than moving processes into a cgroup of our
        own: moving them out of their systemd unit confuses systemd's tracking, while a
        cpu.max write is local, reversible, and the worst case if it is ever left behind
        is that systemd resets it on the next reload.
        """
        for pid, comm, _, _ in self._iter_process_scheduling():
            if comm.lower() != "steam":
                continue
            try:
                with open(f"/proc/{pid}/cgroup", "r") as f:
                    lines = f.readlines()
            except Exception:
                continue

            for line in lines:
                if not line.startswith("0::"):
                    continue  # Only the unified (v2) hierarchy carries cpu.max
                rel = line.strip().split("::", 1)[1]
                path = os.path.join("/sys/fs/cgroup", rel.lstrip("/"))
                # Steam's own cgroup, and only if the cpu controller is already enabled
                # there. Walking up to an ancestor would quietly throttle every other app
                # in that slice, and enabling the controller ourselves changes a cgroup
                # that belongs to systemd. Neither is worth the risk for a download.
                if os.path.exists(os.path.join(path, "cpu.max")):
                    return path
                logger.info(
                    f"CPU pacing unavailable: no cpu.max in Steam's own cgroup ({path}). "
                    "The download speed cap and the clock limits still apply."
                )
                return None
        return None

    def _cgroup_subtree_comms(self, cgroup_dir: str) -> Set[str]:
        comms: Set[str] = set()
        procs_files = [os.path.join(cgroup_dir, "cgroup.procs")]
        procs_files += glob.glob(os.path.join(cgroup_dir, "**", "cgroup.procs"), recursive=True)
        for procs_file in procs_files:
            try:
                with open(procs_file, "r") as f:
                    for line in f:
                        pid = line.strip()
                        if not pid:
                            continue
                        with open(f"/proc/{pid}/comm", "r") as cf:
                            comms.add(cf.read().strip().lower())
            except Exception:
                continue
        return comms

    def _apply_cpu_quota(self):
        """
        Caps how much CPU Steam may use while the screen is off.

        This is the lever that keeps the console cool, and it is what the old SCHED_IDLE
        throttling failed to do: with nothing else running, an idle-priority process
        still gets 100% of the CPU, so Steam decompressed at full speed and the fans
        spun up. A hard quota bounds the work per second, so the download settles at a
        calm pace and the SoC stays near idle - a download that takes longer but never
        heats the console up, the way a handheld console does it.
        """
        percent = int(self.settings.get("download_cpu_percent", 30))
        if percent <= 0 or percent >= 100:
            logger.info(f"CPU pacing disabled (download_cpu_percent={percent}).")
            return

        cgroup_dir = self._steam_cgroup_dir()
        if not cgroup_dir:
            logger.info("CPU pacing skipped: could not locate Steam's cgroup (cpu controller may be off).")
            return

        # Never throttle a cgroup the compositor shares: starving gamescope can take the
        # whole session down with it.
        comms = self._cgroup_subtree_comms(cgroup_dir)
        blockers = {c for c in comms if "gamescope" in c or "xwayland" in c}
        if blockers:
            logger.warning(f"CPU pacing skipped: Steam shares its cgroup with {sorted(blockers)}.")
            return

        cpu_max = os.path.join(cgroup_dir, "cpu.max")
        original = self._read_attr(cgroup_dir, "cpu.max") or "max 100000"
        quota = int(CPU_QUOTA_PERIOD * percent / 100)
        if self._write_sysfs(cpu_max, f"{quota} {CPU_QUOTA_PERIOD}"):
            self.saved_cpu_quota = (cpu_max, original)
            # Remembered separately so the final check can still verify this file even
            # after the restore has cleared saved_cpu_quota.
            self.last_cpu_quota_path = cpu_max
            logger.info(f"Paced Steam to {percent}% of one CPU core via {cpu_max} (was '{original}').")
        else:
            logger.warning(f"Could not write CPU quota to {cpu_max}.")

    def _restore_cpu_quota(self, saved: Optional[Tuple[str, str]] = None):
        entry = saved or self.saved_cpu_quota
        if not entry:
            return
        cpu_max, original = entry
        self.last_cpu_quota_path = cpu_max
        if os.path.exists(cpu_max):
            # An unreadable original would have been stored as the safe default, so this
            # always ends in an uncapped cgroup rather than a guess.
            target = original if original and not original.startswith("0 ") else f"max {CPU_QUOTA_PERIOD}"
            self._write_sysfs(cpu_max, target)
            logger.info(f"Restored CPU quota on {cpu_max} to '{target}'.")
        self.saved_cpu_quota = None

    def _network_interfaces(self, default_only: bool = True) -> List[str]:
        """Interfaces carrying the default route, or every live non-loopback interface."""
        ifaces: List[str] = []
        if default_only:
            try:
                with open("/proc/net/route", "r") as f:
                    for line in f.readlines()[1:]:
                        parts = line.split()
                        # Destination 00000000 == default route
                        if len(parts) > 2 and parts[1] == "00000000":
                            ifaces.append(parts[0])
            except Exception:
                pass
        if not ifaces:
            for path in sorted(glob.glob("/sys/class/net/*")):
                name = os.path.basename(path)
                if name == "lo":
                    continue
                if self._read_attr(path, "operstate") in ("up", "unknown"):
                    ifaces.append(name)
        return list(dict.fromkeys(ifaces))

    def _tc_binary(self) -> Optional[str]:
        return shutil.which("tc") or next((p for p in ("/usr/sbin/tc", "/sbin/tc") if os.path.exists(p)), None)

    def _tc_has_ingress(self, tc: str, iface: str) -> bool:
        try:
            res = subprocess.run(
                [tc, "qdisc", "show", "dev", iface, "ingress"],
                capture_output=True, text=True, check=False, timeout=5.0,
            )
            return "ingress" in (res.stdout or "")
        except Exception:
            return False

    def _limit_download_bandwidth(self):
        """
        Caps incoming bandwidth with an ingress policer, so Steam simply receives less
        data per second and therefore has far less to decompress and write. Pacing the
        bytes is the most direct way to keep the whole chain - radio, CPU, SSD - quiet.
        """
        if not self.settings.get("limit_download_speed", True):
            return
        tc = self._tc_binary()
        if not tc:
            logger.info("Download speed cap skipped: tc (iproute2) is not installed.")
            return

        megabytes = max(1, int(self.settings.get("download_speed_limit_mbps", 6)))
        rate = f"{megabytes * 8}mbit"
        for iface in self._network_interfaces():
            try:
                # Start from a clean slate in case a previous run left a qdisc behind
                subprocess.run([tc, "qdisc", "del", "dev", iface, "ingress"],
                               check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5.0)
                add = subprocess.run([tc, "qdisc", "add", "dev", iface, "handle", "ffff:", "ingress"],
                                     capture_output=True, text=True, check=False, timeout=5.0)
                if add.returncode != 0:
                    logger.warning(f"Could not add ingress qdisc on {iface}: {(add.stderr or '').strip()}")
                    continue

                applied = False
                for proto, prio, match in (
                    ("ip", "50", ["match", "ip", "src", "0.0.0.0/0"]),
                    ("ipv6", "51", ["match", "ip6", "src", "::/0"]),
                ):
                    res = subprocess.run(
                        [tc, "filter", "add", "dev", iface, "parent", "ffff:", "protocol", proto,
                         "prio", prio, "u32"] + match +
                        ["police", "rate", rate, "burst", "512k", "mtu", "65535", "drop", "flowid", ":1"],
                        capture_output=True, text=True, check=False, timeout=5.0,
                    )
                    if res.returncode == 0:
                        applied = True
                    else:
                        logger.info(f"Ingress filter for {proto} on {iface} not applied: {(res.stderr or '').strip()}")

                if applied:
                    self.throttled_interfaces.append(iface)
                    logger.info(f"Download paced to ~{megabytes} MB/s on {iface} ({rate} ingress policing).")
                else:
                    subprocess.run([tc, "qdisc", "del", "dev", iface, "ingress"],
                                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5.0)
            except Exception as e:
                logger.error(f"Failed to pace download on {iface}: {e}")

    def _clear_download_bandwidth_limit(self, interfaces: Optional[List[str]] = None):
        tc = self._tc_binary()
        if not tc:
            self.throttled_interfaces.clear()
            return
        # Deleted unconditionally, never gated on detecting the qdisc first: if the
        # detection ever misreads, the cap would stay on and the console would look
        # permanently slow. Deleting a qdisc that is not there just returns an error.
        for iface in (interfaces if interfaces is not None else list(self.throttled_interfaces)):
            try:
                res = subprocess.run(
                    [tc, "qdisc", "del", "dev", iface, "ingress"],
                    capture_output=True, text=True, check=False, timeout=5.0,
                )
                if res.returncode == 0:
                    logger.info(f"Removed download speed cap on {iface}.")
            except Exception as e:
                logger.error(f"Failed to clear download cap on {iface}: {e}")
        self.throttled_interfaces.clear()
