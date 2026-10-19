# New Suspend Mode (Decky Loader Plugin)

<p align="center">
  <img src="assets/icon.svg" width="128" height="128" alt="New Suspend Mode Icon" />
</p>

A full replacement for the SteamOS "Sleep". Press the Sleep item in the power menu or the hardware power button and the console goes to a plugin-managed standby: the screen blacks out, the fans go quiet, Steam downloads keep running in the background, Bluetooth stays reachable, and any paired controller — Xbox, PlayStation, 8BitDo, generic — can bring the console back by itself.

Runs on handhelds (Steam Deck LCD/OLED, ROG Ally, ROG Ally X, Legion Go) and on any desktop PC with SteamOS or a SteamOS-like gamescope session.

---

## What the plugin does

### Replaces Sleep with a controller-aware standby

Both the power menu's Sleep and the hardware power button are redirected to a new mode where the system is _on_ but silent:

- Panel backlight at 0, pure black overlay on OLED, audio muted.
- CPU/GPU parked at power-saving limits, platform profile set to quiet.
- All inputs blocked except the sources that are supposed to wake the console.
- Steam downloads carry on, with a configurable speed cap and CPU share.
- A Bluetooth controller pairing, a USB/dongle controller button press (Guide / Home / Select / Start), or the power button wakes it back up.

Shut Down from the power menu still powers off for real; this is only the Sleep replacement.

### Quiet-hours real sleep + RTC return

Inside a user-configured period (sliders in 10-minute steps, wraps across midnight), with no download running, Sleep enters the **real** SteamOS suspend instead of the plugin's standby — same battery drain as the stock sleep.

Optionally, the RTC alarm is armed for the end of the period: when it fires, the plugin detects the wake via a kernel-clock jump and immediately re-enters its own new suspend mode. The console is back in standby waiting for a controller before you walk into the room.

### Download management

- Native detection of Steam downloads via libraries overview + network RX fallback.
- Hard bandwidth cap via `tc` on the active interface.
- CPU budget via cgroup `cpu.max` quota, so the chip stays cool enough for the fans to idle.
- Suspend intercepted automatically if a download starts and the plugin is enabled.
- Battery-aware: handhelds drop to a real suspend if battery falls below the configured threshold during standby.

### Hardware watchdog

Nine signals cover everything the plugin itself can touch — `scaling_max_freq`, `cpufreq/boost`, `ryzenadj` state, `platform_profile`, GPU DPM, governor, EPP, cgroup `cpu.max`, `tc ingress`. If anything the plugin set is still in place after a wake (or a crash left it behind), an eight-step hard reset puts everything back without a reboot, including an ACPI profile bounce to make the firmware re-apply its own limits.

The reset is also exposed as a button in the settings panel.

### Enable When Plugged In

Separate toggle: when on, the plugin force-enables itself whenever the device is on AC power — regardless of the main Enable Plugin toggle. Meant for a desktop PC that is always plugged in, or a handheld you only want the plugin active for while charging.

---

## Settings

The panel opens with a short **Essentials** section. Everything else is hidden behind an **Advanced Features** toggle, so the common path is a handful of switches.

### Always visible

- **Enable Plugin** — master switch.
- **Enable Plugin When Plugged In** — force-enable on AC regardless of the above.

### Essentials

- **Replace Sleep With New Suspend Mode** _(default on)_ — Sleep and the power button enter the new suspend mode instead of real sleep.
- **Real Sleep During A Time Period** _(default on, 00:00 - 07:00)_ — inside the period, with no download, Sleep goes to the stock SteamOS sleep instead.
  - **Period Start / Period End** — 10-minute sliders. The period wraps midnight: 23:00 - 07:00 means 23:00 through 06:59.
- **Return To New Suspend Mode At Period End** _(default on)_ — RTC wake at the end of the window, then back to the new suspend mode automatically.
- **Slow Down Download** _(default on)_ — downloads capped so decompression stays cold.
- **Restore Hardware Now** — one-click button to put every clock, limit, cap and quota back to normal, even ones left by a crash.
- **Advanced Features** _(default off)_ — reveals the sections below.

### Advanced

- **Behavior** — battery threshold, HUD countdown, completion-suspend delay, input lockout toggle.
- **Power Saving & Screen Options** — backlight off, OLED pitch black, CPU/GPU throttle, mute audio.
- **Standby Wake Sources** — wake on Bluetooth connect, wake on controller button, battery note.
- **Download Pace** — speed cap in MB/s, CPU budget as % of one core.
- **Troubleshooting** — hidraw unbind escalation, UI recovery on wake, auto hard reset after wake, diagnostic logs.

---

## How things are detected

- **Steam downloads**: SteamClient libraries overview from the frontend, network RX as a fallback when the overview is stale.
- **Hardware wake**: logind journal (`operation 'sleep' finished`, `system is resuming`) plus a kernel-clock-jump detector in the monitor loop, so a resume is caught even if the journal path misses it.
- **RTC wake**: `/sys/class/rtc/rtc0/wakealarm`. Standard Linux kernel feature, works on every tested handheld and PC. A 10-minute grace period after an RTC wake prevents the quiet-hours check from re-sleeping the console at the boundary minute.
- **Bluetooth controllers**: BlueZ D-Bus (`busctl`) by icon (`input-gaming`, `input-gamepad`, `input-joystick`) and by Modalias vendor id, so PS5 DualSense, Xbox over `xpadneo`, 8BitDo, Nintendo, Razer, etc. all count as wake sources.
- **TV standby**: `gamescopectl drm_sleep_internal_screen` and `drm_sleep_external_screen` first, then DRM DPMS via `/sys/class/drm/card*-*/dpms` as a fallback for desktops.

---

## Hardware supported

The plugin is written to be generic. All of these paths are tried as available and quietly skipped if absent:

- **Steam Deck LCD / OLED**: ryzenadj (STAPM / fast / slow limits in mW), AMD platform profile.
- **ROG Ally / Ally X**: ryzenadj + ASUS WMI (`ppt_pl1_spl`, `ppt_pl2_sppt`, `ppt_fppt`, `throttle_thermal_policy`, `fan_boost_mode`).
- **Legion Go**: ACPI platform profile.
- **Desktop PC with SteamOS**: `scaling_governor`, `cpufreq/boost`, `energy_performance_preference`, GPU DPM levels, DRM DPMS for the external screen.
- **Everything**: cgroup v2 `cpu.max` quota, `tc` ingress policer, systemd-inhibitor, systemd-logind watcher.

---

## Install

### Via the installer script

From the plugin folder:

```bash
./install.sh
```

Installs to `~/homebrew/plugins/NewSuspendMode`. Restart Decky with `sudo systemctl restart plugin_loader` or reboot Game Mode.

### Via the Makefile

```bash
make install
```

Same thing.

### Via the zip (manual)

Build the zip with `pnpm run package`. It writes `NewSuspendMode.zip`. In Decky Loader → Developer → Install Plugin from URL or ZIP, point at that file.

### Upgrade from the old name

Previous users of this plugin had it installed under `DownloadInBackground`. The settings and runtime state kept there (`~/.config/DownloadInBackground/*.json`) are copied over to `~/.config/NewSuspendMode/` on first run, so sliders and toggles survive the rename. The old `~/homebrew/plugins/DownloadInBackground/` folder can be removed by hand once Decky loads the new one.

---

## Build from source

```bash
pnpm install
pnpm run build        # frontend
pnpm run package      # NewSuspendMode.zip
```

Python backend is a single file (`main.py`), no dependencies to install.

---

## Files

- `main.py` — backend. State machine, download detection, hardware control, logind watcher, RTC alarm, watchdog, hard reset.
- `src/` — frontend. React/TSX, Decky UI. Entry point `src/index.tsx`.
  - `src/components/SettingsPanel.tsx` — the settings panel.
  - `src/components/Overlay.tsx` — the HUD and the black overlay.
- `plugin.json` — Decky manifest.
- `install.sh`, `Makefile` — install helpers.

---

## Privacy / autonomy

The plugin runs entirely offline. No telemetry, no network calls, no accounts. Everything it writes lives under `~/.config/NewSuspendMode/`. Everything it reads from the system is standard Linux sysfs / D-Bus / systemd interfaces.

---

## License

See `LICENSE`.
