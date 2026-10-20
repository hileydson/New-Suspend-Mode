"""Detects Steam downloads from the backend side: manifests, the content log and network rate."""
import os
import glob
import time
import re
from typing import Dict, Any, Optional, List, Set, Tuple

from .constants import decky


class SteamDownloadDetector:
    """
    Natively inspects Steam library folders, appmanifest files, and network traffic
    to detect downloads with 100% reliability without relying on CEF JavaScript.
    """
    def __init__(self):
        self.cached_libraries: List[str] = []
        self.last_lib_scan: float = 0
        self.last_net_bytes: int = 0
        self.last_net_time: float = 0.0
        self.last_net_rate: float = 0.0
        self.last_completed_bytes: int = 0
        self.last_dl_calc_time: float = time.time()
        # appmanifest path -> (mtime_ns, parsed fields). Steam rewrites a manifest
        # while it downloads, so the mtime alone tells us when a re-read is needed.
        self.manifest_cache: Dict[str, Tuple[int, Optional[Dict[str, Any]]]] = {}

    def get_library_paths(self) -> List[str]:
        now = time.time()
        if self.cached_libraries and (now - self.last_lib_scan) < 20:
            return self.cached_libraries

        libs: Set[str] = set()

        # Check decky.DECKY_USER_HOME, /home/* and ~
        candidate_homes = glob.glob("/home/*") + [decky.DECKY_USER_HOME, os.path.expanduser("~")]
        for ch in candidate_homes:
            if not ch or not os.path.isdir(ch):
                continue
            for rel in [".local/share/Steam", ".steam/steam", ".steam/root"]:
                steam_base = os.path.join(ch, rel)
                sa = os.path.join(steam_base, "steamapps")
                if os.path.isdir(sa):
                    libs.add(sa)
                    vdf_file = os.path.join(sa, "libraryfolders.vdf")
                    if os.path.isfile(vdf_file):
                        try:
                            with open(vdf_file, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                            matches = re.findall(r"\"path\"\s*\"([^\"]+)\"", content)
                            for m in matches:
                                extra_sa = os.path.join(m, "steamapps")
                                if os.path.isdir(extra_sa):
                                    libs.add(extra_sa)
                        except Exception:
                            pass

        # Check removable media (SD Card, second NVMe partition, USB)
        for rem in glob.glob("/run/media/*/*") + glob.glob("/media/*/*") + glob.glob("/mnt/*"):
            sa = os.path.join(rem, "steamapps")
            if os.path.isdir(sa):
                libs.add(sa)

        self.cached_libraries = list(libs)
        self.last_lib_scan = now
        return self.cached_libraries

    def get_network_rx_rate(self, min_sample_age: float = 0.5) -> float:
        """
        Reads real received bytes per second across all non-lo network interfaces.

        Calls made less than min_sample_age apart return the previous result instead of
        re-sampling: two samples taken milliseconds apart always read as ~0 B/s, which
        used to make the plugin believe an active download had stopped.
        """
        now = time.time()
        if (now - self.last_net_time) < min_sample_age:
            return self.last_net_rate

        curr_bytes = 0
        try:
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()[2:]
            for line in lines:
                parts = line.split(":")
                if len(parts) == 2 and parts[0].strip() != "lo":
                    vals = parts[1].split()
                    if vals:
                        curr_bytes += int(vals[0])
        except Exception:
            pass

        dt = max(0.1, now - self.last_net_time)
        bps = 0.0
        if self.last_net_bytes > 0 and curr_bytes >= self.last_net_bytes:
            bps = (curr_bytes - self.last_net_bytes) / dt

        self.last_net_bytes = curr_bytes
        self.last_net_time = now
        self.last_net_rate = bps
        return bps

    def _has_recent_download_writes(self, libs: List[str], max_age_seconds: float = 6.0) -> bool:
        """Checks if files in steamapps/downloading/ were modified within max_age_seconds."""
        now = time.time()
        for sa in libs:
            dl_dir = os.path.join(sa, "downloading")
            if not os.path.isdir(dl_dir):
                continue
            try:
                count = 0
                for root, dirs, files in os.walk(dl_dir):
                    for fname in files:
                        count += 1
                        if count > 60:
                            break
                        fpath = os.path.join(root, fname)
                        try:
                            if (now - os.path.getmtime(fpath)) <= max_age_seconds:
                                return True
                        except OSError:
                            pass
                    if count > 60:
                        break
            except Exception:
                pass
        return False

    def _read_manifest(self, path: str) -> Optional[Dict[str, Any]]:
        """Parses an appmanifest, reusing the cached result while its mtime is unchanged."""
        try:
            mtime_ns = os.stat(path).st_mtime_ns
        except OSError:
            self.manifest_cache.pop(path, None)
            return None

        cached = self.manifest_cache.get(path)
        if cached is not None and cached[0] == mtime_ns:
            return cached[1]

        parsed: Optional[Dict[str, Any]] = None
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                txt = f.read()

            state_m = re.search(r"\"StateFlags\"\s*\"(\d+)\"", txt)
            if state_m:
                name_m = re.search(r"\"name\"\s*\"([^\"]+)\"", txt)
                dl_m = re.search(r"\"BytesDownloaded\"\s*\"(\d+)\"", txt)
                tot_m = re.search(r"\"BytesToDownload\"\s*\"(\d+)\"", txt)

                b_dl = int(dl_m.group(1)) if dl_m else 0
                b_tot = int(tot_m.group(1)) if tot_m else 0
                parsed = {
                    "state": int(state_m.group(1)),
                    "game_title": name_m.group(1) if name_m else "Steam Download",
                    "completed_bytes": b_dl,
                    "total_bytes": b_tot,
                    "progress_percent": (b_dl / b_tot * 100) if b_tot > 0 else 0,
                }
        except Exception:
            parsed = None

        self.manifest_cache[path] = (mtime_ns, parsed)
        return parsed

    def detect(self) -> Dict[str, Any]:
        libs = self.get_library_paths()
        active_candidates: List[Dict[str, Any]] = []
        paused_candidates: List[Dict[str, Any]] = []
        seen_manifests: Set[str] = set()

        # Check appmanifest files in all libraries
        for sa in libs:
            for mf in glob.glob(os.path.join(sa, "appmanifest_*.acf")):
                seen_manifests.add(mf)
                parsed = self._read_manifest(mf)
                if not parsed:
                    continue

                state = parsed["state"]
                cand = {
                    "game_title": parsed["game_title"],
                    "completed_bytes": parsed["completed_bytes"],
                    "total_bytes": parsed["total_bytes"],
                    "progress_percent": parsed["progress_percent"],
                }

                # StateFlags:
                # 512 = StateUpdatePaused
                # 1048576 = StateUpdateStopping
                # 1024 = StateUpdateStarted, 256 = StateUpdateRunning, 131072 = StateDownloading, 262144 = StateStaging, 65536 = StatePreallocating
                is_paused = bool(state & 512)
                is_stopping = bool(state & 1048576)
                is_updating = bool((state & 1024) or (state & 256) or (state & 131072) or (state & 262144) or (state & 65536))

                if is_paused or is_stopping:
                    paused_candidates.append(cand)
                elif is_updating:
                    active_candidates.append(cand)

        # Forget manifests for games that were uninstalled or moved to another library
        for stale in set(self.manifest_cache) - seen_manifests:
            self.manifest_cache.pop(stale, None)

        net_bps = self.get_network_rx_rate()

        # Walking steamapps/downloading/ is the only expensive check here, so it only runs
        # when a manifest or the network already hints that something may be downloading.
        has_recent_writes = False
        if active_candidates or paused_candidates or net_bps > 50000:
            has_recent_writes = self._has_recent_download_writes(libs, max_age_seconds=8.0)

        # Case 1: Active updating candidate in manifests
        if active_candidates:
            active_dl = active_candidates[0]
            # Verify network is actually flowing or disk is actively being written
            if net_bps > 15000 or has_recent_writes:
                active_dl["is_downloading"] = True
                active_dl["is_paused"] = False
                active_dl["bytes_per_second"] = net_bps
                if net_bps > 0 and active_dl["total_bytes"] > active_dl["completed_bytes"]:
                    rem_bytes = active_dl["total_bytes"] - active_dl["completed_bytes"]
                    active_dl["estimated_seconds_remaining"] = int(rem_bytes / net_bps)
                else:
                    active_dl["estimated_seconds_remaining"] = 0
                return active_dl

        # Case 2: No active downloads, but games are paused in download queue
        if paused_candidates and not has_recent_writes and net_bps < 30000:
            paused_dl = paused_candidates[0]
            return {
                "is_downloading": False,
                "is_paused": True,
                "game_title": paused_dl["game_title"],
                "completed_bytes": paused_dl["completed_bytes"],
                "total_bytes": paused_dl["total_bytes"],
                "progress_percent": paused_dl["progress_percent"],
                "bytes_per_second": 0,
                "estimated_seconds_remaining": 0,
            }

        # Case 3: High network traffic + active file writes (fallback for unmanifested downloads)
        if net_bps > 50000 and has_recent_writes:
            return {
                "is_downloading": True,
                "is_paused": False,
                "game_title": "Steam Game Download",
                "bytes_per_second": net_bps,
                "completed_bytes": 0,
                "total_bytes": 0,
                "progress_percent": 0,
                "estimated_seconds_remaining": 0,
            }

        # Case 4: Completely idle or paused
        return {
            "is_downloading": False,
            "is_paused": bool(paused_candidates),
            "game_title": paused_candidates[0]["game_title"] if paused_candidates else "",
            "bytes_per_second": net_bps,
            "completed_bytes": 0,
            "total_bytes": 0,
            "progress_percent": 0,
            "estimated_seconds_remaining": 0,
        }
