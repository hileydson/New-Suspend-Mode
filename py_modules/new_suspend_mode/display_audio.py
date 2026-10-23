"""Audio mute and the gamescope / DRM display controls."""
import os
import glob
import subprocess
import shutil

from .constants import logger


class DisplayAudioMixin:
    """Audio mute and the gamescope / DRM display controls."""

    # ==========================================
    # Power Saving & Screen Control
    # ==========================================
    def _set_audio_mute(self, mute: bool):
        val = "1" if mute else "0"
        amixer_arg = "mute" if mute else "unmute"
        # 1. ALSA hardware master mute (works directly at hardware level)
        try:
            subprocess.run(["amixer", "-q", "set", "Master", amixer_arg], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=2.0, stdin=subprocess.DEVNULL)
        except Exception:
            pass

        # 2. PipeWire & PulseAudio per-user session sockets
        for uid_dir in glob.glob("/run/user/*"):
            if os.path.basename(uid_dir).isdigit():
                if not (os.path.exists(os.path.join(uid_dir, "pipewire-0"))
                        or os.path.exists(os.path.join(uid_dir, "pulse/native"))):
                    continue
                env = os.environ.copy()
                env["XDG_RUNTIME_DIR"] = uid_dir
                try:
                    subprocess.run(
                        ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", val],
                        env=env,
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=2.0,
                        stdin=subprocess.DEVNULL,
                    )
                except Exception:
                    pass
                try:
                    subprocess.run(
                        ["pactl", "set-sink-mute", "@DEFAULT_SINK@", val],
                        env=env,
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=2.0,
                        stdin=subprocess.DEVNULL,
                    )
                except Exception:
                    pass

    def _set_gamescope_display(self, sleep: bool):
        """
        Puts the display into a real standby, so an external TV or monitor stops showing
        a black screen and enters its own no-signal state.

        On a handheld (ROG Ally, Steam Deck) the backlight sysfs path was enough - the
        panel itself went dark. A TV is different: it manages its own backlight and
        decides "signal present" from the TMDS clock and sync, not from pixel content.
        A black frame is a perfectly valid signal, so the TV stays lit. There is no
        "null video signal" to send instead; the only way to reach its standby is to
        stop the clock, which means disabling the connector.

          1. gamescopectl drm_sleep_{internal,external}_screen -> ask the DRM master
          2. The DRM connector `status` attribute              -> force "no signal"

        Both are wrapped per-call, so a path a given build does not support only logs
        what the compositor said and the next one runs.
        """
        arg = "1" if sleep else "0"

        # Path 1: gamescope, the DRM master. Only the compositor can stop scanning out,
        # so this is the cooperative route and is tried first.
        #
        # gamescopectl reads GAMESCOPE_WAYLAND_DISPLAY (default "gamescope-0") and never
        # WAYLAND_DISPLAY, and its socket lives in the SESSION user's runtime dir, not
        # root's - a root caller that leaves XDG_RUNTIME_DIR at /run/user/0 silently
        # reaches nothing. It also returns 0 after the roundtrip whether or not the
        # property was accepted, so the only way to know is to read stderr.
        gamescopectl = shutil.which("gamescopectl") or next(
            (p for p in ("/usr/bin/gamescopectl", "/usr/local/bin/gamescopectl") if os.path.exists(p)),
            None,
        )
        if gamescopectl:
            user = self._get_session_user()
            for uid_dir in sorted(glob.glob("/run/user/*")):
                uid = os.path.basename(uid_dir)
                # /run/user/0 is root's own dir; gamescope never runs there, and a root
                # shell inherits it, which is what made every previous attempt a no-op.
                if not uid.isdigit() or uid == "0":
                    continue
                sockets = [
                    os.path.basename(p)
                    for p in glob.glob(os.path.join(uid_dir, "gamescope-*"))
                    if not p.endswith(".lock")
                ] or ["gamescope-0"]
                for socket in sockets:
                    if not os.path.exists(os.path.join(uid_dir, socket)):
                        continue
                    env = os.environ.copy()
                    env["XDG_RUNTIME_DIR"] = uid_dir
                    env["GAMESCOPE_WAYLAND_DISPLAY"] = socket
                    for subcommand in ("drm_sleep_internal_screen", "drm_sleep_external_screen"):
                        commands = (
                            [gamescopectl, subcommand, arg],
                            ["sudo", "-n", "-u", user, "env",
                             f"XDG_RUNTIME_DIR={uid_dir}",
                             f"GAMESCOPE_WAYLAND_DISPLAY={socket}",
                             gamescopectl, subcommand, arg],
                        )
                        key = (uid_dir, socket, subcommand)
                        preferred = self.gamescope_command_routes.get(key, 0)
                        for route in (preferred, 1 - preferred):
                            cmd = commands[route]
                            try:
                                res = subprocess.run(
                                    cmd, env=env, check=False, capture_output=True,
                                    text=True, timeout=2.0, stdin=subprocess.DEVNULL,
                                )
                                detail = (res.stderr or res.stdout or "").strip()
                                logger.info(
                                    f"gamescopectl {subcommand} {arg} "
                                    f"[{uid_dir}:{socket}] rc={res.returncode}"
                                    + (f" :: {detail[:200]}" if detail else "")
                                )
                                # gamescopectl may return 0 for a rejected property;
                                # stderr must also be empty before trusting a route.
                                if res.returncode == 0 and not (res.stderr or "").strip():
                                    self.gamescope_command_routes[key] = route
                                    break
                            except Exception as e:
                                logger.debug(f"gamescopectl {subcommand} failed: {e}")

        # Path 2: force the DRM connector's status, which is the ONLY way to produce a
        # real "no signal" for an external TV.
        #
        # The connector's `dpms` and `enabled` attributes are 0444 - read-only even for
        # root - so writing them was always a no-op, whatever earlier versions claimed.
        # `status` is 0644 and accepts "off" / "on" / "detect": writing "off" makes the
        # kernel report the connector disconnected and fire a hotplug uevent, so the
        # compositor drops the output and the TMDS clock stops. That is the same event
        # as unplugging the cable, which compositors handle routinely.
        #
        # Internal panels (eDP / LVDS / DSI) are never touched: on a handheld the
        # backlight path already blanks the panel, and disabling its only connector
        # would leave the device with nowhere to draw.
        if sleep:
            if not self.settings.get("tv_force_connector_off", False):
                return
            for conn in sorted(glob.glob("/sys/class/drm/card*-*")):
                label = os.path.basename(conn)
                if any(k in label.upper() for k in ("EDP", "LVDS", "DSI", "WRITEBACK")):
                    continue
                status_file = os.path.join(conn, "status")
                if not os.path.exists(status_file):
                    continue
                try:
                    if self._read_text(status_file) != "connected":
                        continue
                    if self._write_sysfs(status_file, "off"):
                        if label not in self.forced_off_connectors:
                            self.forced_off_connectors.append(label)
                        logger.info(f"Forced DRM connector {label} status -> off (TV should lose signal).")
                    else:
                        logger.info(f"Could not force {label} status to off.")
                except Exception as e:
                    logger.debug(f"Forcing {label} status off failed: {e}")
            self._save_runtime_state()
        else:
            # Restore every connector this plugin forced off. "detect" hands control back
            # to normal hotplug detection rather than pinning it on.
            for label in list(self.forced_off_connectors):
                status_file = os.path.join("/sys/class/drm", label, "status")
                try:
                    if os.path.exists(status_file) and self._write_sysfs(status_file, "detect"):
                        logger.info(f"Restored DRM connector {label} status -> detect.")
                    else:
                        logger.warning(f"Could not restore {label} status; it may need a replug.")
                except Exception as e:
                    logger.warning(f"Restoring {label} status failed: {e}")
            if self.forced_off_connectors:
                self.forced_off_connectors = []
                self._save_runtime_state()
