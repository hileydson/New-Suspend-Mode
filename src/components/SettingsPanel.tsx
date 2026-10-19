import React, { FC } from "react";
import {
  PanelSection,
  PanelSectionRow,
  ToggleField,
  SliderField,
  Field,
  ProgressBar,
  ButtonItem,
} from "@decky/ui";
import { call, toaster } from "@decky/api";
import { PluginSettings, DownloadInfo } from "../types";

interface SettingsPanelProps {
  settings: PluginSettings;
  setSettings: (newSettings: PluginSettings) => void;
  downloadInfo: DownloadInfo;
  isBackgroundMode: boolean;
  standbyMode?: boolean;
  batteryCapacity: number;
  isCharging: boolean;
  powerPlugged: boolean;
}

const formatHM = (minutes: number): string => {
  const safe = Math.max(0, Math.min(1430, Math.round(minutes / 10) * 10));
  const h = Math.floor(safe / 60);
  const m = safe % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
};

export const SettingsPanel: FC<SettingsPanelProps> = ({
  settings,
  setSettings,
  downloadInfo,
  isBackgroundMode,
  standbyMode,
  batteryCapacity,
  isCharging,
  powerPlugged,
}) => {
  const updateSetting = async <K extends keyof PluginSettings>(
    key: K,
    val: PluginSettings[K]
  ) => {
    const updated = { ...settings, [key]: val };
    setSettings(updated);
    try {
      await call("save_settings", updated);
    } catch (e) {
      console.error("[DownloadInBackground] Error saving settings:", e);
    }
  };

  const formatSpeed = (bytesPerSec: number): string => {
    if (!bytesPerSec || bytesPerSec <= 0) return "0 KB/s";
    const mb = bytesPerSec / (1024 * 1024);
    if (mb >= 1) return `${mb.toFixed(1)} MB/s`;
    return `${(bytesPerSec / 1024).toFixed(0)} KB/s`;
  };

  const isPaused = Boolean(downloadInfo.is_paused);
  const isDownloading =
    !isPaused &&
    Boolean(
      downloadInfo.is_downloading ||
      (downloadInfo.bytes_per_second || 0) > 10000
    );

  const advanced = settings.advanced_mode === true;
  const startMin = settings.real_sleep_start_minutes ?? 0;
  const endMin = settings.real_sleep_end_minutes ?? 420;

  return (
    <div>
      {/* Plugin on/off — always first, always visible */}
      <PanelSection title="Plugin">
        <PanelSectionRow>
          <ToggleField
            label="Enable Plugin"
            description="Intercepts suspend when downloading, turns off screen, and saves power."
            checked={settings.enabled}
            onChange={(checked) => updateSetting("enabled", checked)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label="Enable Plugin When Plugged In"
            description="Force-enables the plugin whenever the device is on AC power, regardless of the toggle above. Handy for a desktop PC that is always plugged in, or a handheld where you only want the plugin active while charging."
            checked={settings.enable_plugin_when_plugged_in === true}
            onChange={(checked) => updateSetting("enable_plugin_when_plugged_in", checked)}
          />
        </PanelSectionRow>
      </PanelSection>

      {/* Current Status Section (informational, always visible) */}
      <PanelSection title="Download & System Status">
        <PanelSectionRow>
          <Field
            label="Download Status"
            description={
              isDownloading
                ? `${downloadInfo.game_title || "Steam Download"} (${formatSpeed(
                    downloadInfo.bytes_per_second
                  )})`
                : isPaused
                ? `${downloadInfo.game_title ? downloadInfo.game_title + " (Paused)" : "Downloads paused"}`
                : "No active downloads"
            }
          >
            <span
              className={`dib-status-tag ${
                isDownloading ? "downloading" : isPaused ? "paused" : "idle"
              }`}
            >
              {isDownloading ? "DOWNLOADING" : isPaused ? "PAUSED" : "IDLE"}
            </span>
          </Field>
        </PanelSectionRow>

        {(isDownloading || (isPaused && downloadInfo.total_bytes > 0)) && (
          <PanelSectionRow>
            <div style={{ width: "100%", margin: "4px 0" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: "12px",
                  color: "#cbd5e1",
                  marginBottom: "4px",
                }}
              >
                <span>Progress: {downloadInfo.progress_percent.toFixed(1)}%</span>
                <span>
                  {isDownloading
                    ? `Speed: ${formatSpeed(downloadInfo.bytes_per_second)}`
                    : "Paused"}
                </span>
              </div>
              <ProgressBar
                nProgress={downloadInfo.progress_percent || 0}
              />
            </div>
          </PanelSectionRow>
        )}

        <PanelSectionRow>
          <Field
            label="Battery Level"
            description={`Auto-sleep threshold: ${settings.min_battery_threshold}%`}
          >
            <span style={{ fontWeight: "bold" }}>
              {batteryCapacity}% {isCharging ? "⚡ (Charging)" : "🔋"}
            </span>
          </Field>
        </PanelSectionRow>

        <PanelSectionRow>
          <Field
            label={standbyMode ? "Standby Mode" : "Background Download Mode"}
            description={
              standbyMode
                ? "Console off, waiting for a controller"
                : isBackgroundMode
                ? "Active (Screen off & power saving enabled)"
                : "Inactive (Normal operation)"
            }
          >
            <span
              className={`dib-status-tag ${
                isBackgroundMode ? "active" : "idle"
              }`}
            >
              {standbyMode ? "STANDBY" : isBackgroundMode ? "ACTIVE" : "IDLE"}
            </span>
          </Field>
        </PanelSectionRow>
      </PanelSection>

      {/* Essentials — shown in both basic and advanced modes */}
      <PanelSection title="Essentials">
        <PanelSectionRow>
          <ToggleField
            label="Replace Sleep With Standby"
            description="The power button AND the Sleep option in the SteamOS power menu both enter the plugin's standby instead of suspending: screen black, downloads carry on, a controller brings it back. Shut Down still powers off for real."
            checked={settings.standby_on_power_off}
            onChange={(checked) => updateSetting("standby_on_power_off", checked)}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
            label="Real Sleep During A Time Period"
            description="Inside the period below, with no download running, a Sleep from the power menu or the power button triggers the REAL SteamOS sleep instead of our standby. The period wraps across midnight (e.g. 23:00 - 07:00 means 23:00 through 06:59)."
            checked={settings.enter_real_sleep_after_time === true}
            onChange={(checked) => updateSetting("enter_real_sleep_after_time", checked)}
          />
        </PanelSectionRow>

        {settings.enter_real_sleep_after_time && (
          <>
            <PanelSectionRow>
              <SliderField
                label={`Period Start — ${formatHM(startMin)}`}
                description={`Period: ${formatHM(startMin)} - ${formatHM(endMin)}. Inside the window, real sleep. Outside, our standby as usual.`}
                value={startMin}
                min={0}
                max={1430}
                step={10}
                onChange={(val) => updateSetting("real_sleep_start_minutes", val)}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <SliderField
                label={`Period End — ${formatHM(endMin)}`}
                value={endMin}
                min={0}
                max={1430}
                step={10}
                onChange={(val) => updateSetting("real_sleep_end_minutes", val)}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <ToggleField
                label="Wake At End Of Period"
                description="Programs the system clock to wake the console at the end of the period, then re-enters our standby so a controller can wake it. Uses the RTC alarm, which works on any handheld or PC that exposes it."
                checked={settings.wake_at_period_end === true}
                onChange={(checked) => updateSetting("wake_at_period_end", checked)}
              />
            </PanelSectionRow>
          </>
        )}

        <PanelSectionRow>
          <ToggleField
            label="Slow Down Download"
            description="Caps incoming speed so there is far less to decompress and write. Downloads take longer, the console stays cold and the fans stay off."
            checked={settings.limit_download_speed}
            onChange={(checked) => updateSetting("limit_download_speed", checked)}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={async () => {
              try {
                await call("force_restore");
                toaster.toast({
                  title: "Download in Background",
                  body: "Hardware restored: clocks, power limits and speed caps are back to normal.",
                  duration: 4000,
                });
              } catch (e) {
                toaster.toast({
                  title: "Download in Background",
                  body: "Could not restore the hardware; see the plugin log.",
                  duration: 4000,
                });
              }
            }}
          >
            Restore Hardware Now
          </ButtonItem>
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
            label="Advanced Features"
            description="Reveals every tuning option: battery thresholds, per-component throttles, standby wake sources, download pace limits and troubleshooting toggles. Leave off for a short, friendly panel."
            checked={advanced}
            onChange={(checked) => updateSetting("advanced_mode", checked)}
          />
        </PanelSectionRow>
      </PanelSection>

      {advanced && (
        <>
          {/* Behavior (advanced) */}
          <PanelSection title="Behavior">
            <PanelSectionRow>
              <SliderField
                label="Auto-Suspend Battery Threshold"
                description="Console suspends automatically if battery drops below this limit during download."
                value={settings.min_battery_threshold}
                min={5}
                max={30}
                step={1}
                showValue
                valueSuffix="%"
                onChange={(val) => updateSetting("min_battery_threshold", val)}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <SliderField
                label="HUD Display Countdown"
                description="Seconds the download card shows on screen before turning display off."
                value={settings.hud_timeout_seconds}
                min={0}
                max={15}
                step={1}
                showValue
                valueSuffix="s"
                onChange={(val) => updateSetting("hud_timeout_seconds", val)}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <SliderField
                label="Completion Suspend Delay"
                description="Seconds to wait after all downloads complete before automatically sleeping."
                value={settings.auto_suspend_delay_seconds}
                min={30}
                max={600}
                step={30}
                showValue
                valueSuffix="s"
                onChange={(val) => updateSetting("auto_suspend_delay_seconds", val)}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <ToggleField
                label="Block All Input While Screen Is Off"
                description="Freezes button mapping and disconnects external controllers so only the power button responds. Turn off if a controller misbehaves after waking."
                checked={settings.deep_input_lockout}
                onChange={(checked) => updateSetting("deep_input_lockout", checked)}
              />
            </PanelSectionRow>
          </PanelSection>

          {/* Power & screen (advanced) */}
          <PanelSection title="Power Saving & Screen Options">
            <PanelSectionRow>
              <ToggleField
                label="Turn Off Display Backlight"
                description="Physically drops LCD/OLED panel backlight brightness to 0."
                checked={settings.turn_off_backlight}
                onChange={(checked) => updateSetting("turn_off_backlight", checked)}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <ToggleField
                label="Pitch Black OLED Mode"
                description="Presents a pure black overlay, shutting off individual OLED pixels."
                checked={settings.oled_black_screen}
                onChange={(checked) => updateSetting("oled_black_screen", checked)}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <ToggleField
                label="Throttle CPU to Powersave"
                description="Switches power profile to power-saver and lowers CPU clock frequencies."
                checked={settings.throttle_cpu}
                onChange={(checked) => updateSetting("throttle_cpu", checked)}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <ToggleField
                label="Throttle GPU to 200MHz"
                description="Sets AMD GPU performance level to low, minimizing GPU power draw."
                checked={settings.throttle_gpu}
                onChange={(checked) => updateSetting("throttle_gpu", checked)}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <ToggleField
                label="Mute Audio While Screen Off"
                description="Silences audio output during background download to prevent disturbance."
                checked={settings.mute_audio}
                onChange={(checked) => updateSetting("mute_audio", checked)}
              />
            </PanelSectionRow>
          </PanelSection>

          {/* Standby wake sources (advanced) */}
          <PanelSection title="Standby Wake Sources">
            <PanelSectionRow>
              <Field
                label="What You Will See"
                description={
                  settings.standby_on_power_off
                    ? "Downloading: the download card, then black. Nothing downloading: just the plugin logo, then black."
                    : "Standby off: sleep is intercepted only while a download is active, and the download card is shown."
                }
              />
            </PanelSectionRow>

            {settings.standby_on_power_off && (
              <>
                <PanelSectionRow>
                  <ToggleField
                    label="Wake When A Bluetooth Pad Connects"
                    description="Bluetooth stays on in standby. Turning a paired controller on is enough to wake the console, no button needed."
                    checked={settings.wake_on_bluetooth_connect}
                    onChange={(checked) => updateSetting("wake_on_bluetooth_connect", checked)}
                  />
                </PanelSectionRow>

                <PanelSectionRow>
                  <ToggleField
                    label="Wake On Controller Button"
                    description="For USB and dongle controllers, connecting is not enough: press Guide/Home, Select or Start to wake. The console's own buttons stay dead - only power works there."
                    checked={settings.wake_on_controller_button}
                    onChange={(checked) => updateSetting("wake_on_controller_button", checked)}
                  />
                </PanelSectionRow>

                <PanelSectionRow>
                  <Field
                    label="Battery In Standby"
                    description={`Standby keeps the console powered, so it does use battery. It drops to a real suspend at ${settings.min_battery_threshold}% to protect it.`}
                  />
                </PanelSectionRow>
              </>
            )}
          </PanelSection>

          {/* Download pace (advanced) */}
          <PanelSection title="Download Pace (Fan & Heat)">
            {settings.limit_download_speed && (
              <PanelSectionRow>
                <SliderField
                  label="Download Speed Cap"
                  description="Lower is quieter and cooler. 6 MB/s still downloads about 21 GB per hour."
                  value={settings.download_speed_limit_mbps}
                  min={1}
                  max={30}
                  step={1}
                  showValue
                  valueSuffix=" MB/s"
                  onChange={(val) => updateSetting("download_speed_limit_mbps", val)}
                />
              </PanelSectionRow>
            )}

            <PanelSectionRow>
              <SliderField
                label="Steam CPU Budget"
                description="Hard limit on the CPU Steam may use while the screen is off, as a share of one core. This is what keeps the chip cool enough for the fans to idle."
                value={settings.download_cpu_percent}
                min={0}
                max={100}
                step={5}
                showValue
                valueSuffix="%"
                onChange={(val) => updateSetting("download_cpu_percent", val)}
              />
            </PanelSectionRow>
          </PanelSection>

          {/* Troubleshooting (advanced) */}
          <PanelSection title="Troubleshooting">
            <PanelSectionRow>
              <ToggleField
                label="Also Disconnect Built-In Controller"
                description="EXPERIMENTAL. Only enable if buttons still act while the screen is off. Detaches the built-in pad's raw HID interface, which crashed the session on some consoles."
                checked={settings.block_controller_hidraw}
                onChange={(checked) => updateSetting("block_controller_hidraw", checked)}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <ToggleField
                label="Recover The Interface On Wake"
                description="If the screen is still blank after waking from a sleep started in the SteamOS power menu, navigates home and, as a last resort, reloads the Steam interface."
                checked={settings.ui_recovery_on_wake !== false}
                onChange={(checked) => updateSetting("ui_recovery_on_wake", checked)}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <ToggleField
                label="Auto Restore Hardware After Wake"
                description="Ten seconds after waking, if anything still looks capped at the plugin's own values (frequency, turbo, ryzenadj, platform profile), runs the same hard reset the button above does. Turn off if another tool manages your TDP and you prefer the button."
                checked={settings.auto_hard_reset_after_wake !== false}
                onChange={(checked) => updateSetting("auto_hard_reset_after_wake", checked)}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <ToggleField
                label="Write Diagnostic Logs"
                description="Records the full input and thermal picture to the plugin log on every screen-off. Leave on while tuning."
                checked={settings.debug_logging}
                onChange={(checked) => updateSetting("debug_logging", checked)}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <Field
                label="Restore Hardware Now — When to use it"
                description="The button above puts every clock, power limit and speed cap back without rebooting, even ones left behind by a crash. It also re-enables turbo boost, makes the firmware re-apply the current power profile, and raises any CPU ceiling still below what the chip reports — so it will overrule another tool's TDP settings while it runs."
                bottomSeparator="none"
              />
            </PanelSectionRow>
          </PanelSection>
        </>
      )}
    </div>
  );
};
