import React, { FC } from "react";
import {
  PanelSection,
  PanelSectionRow,
  ToggleField,
  SliderField,
  Field,
  ProgressBar,
} from "@decky/ui";
import { call, toaster } from "@decky/api";
import { PluginSettings, DownloadInfo } from "../types";

interface SettingsPanelProps {
  settings: PluginSettings;
  setSettings: (newSettings: PluginSettings) => void;
  downloadInfo: DownloadInfo;
  isBackgroundMode: boolean;
  batteryCapacity: number;
  isCharging: boolean;
  powerPlugged: boolean;
}

export const SettingsPanel: FC<SettingsPanelProps> = ({
  settings,
  setSettings,
  downloadInfo,
  isBackgroundMode,
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

  return (
    <div>
      {/* Current Status Section */}
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
            label="Background Download Mode"
            description={
              isBackgroundMode
                ? "Active (Screen off & power saving enabled)"
                : "Inactive (Normal operation)"
            }
          >
            <span
              className={`dib-status-tag ${
                isBackgroundMode ? "active" : "idle"
              }`}
            >
              {isBackgroundMode ? "ACTIVE" : "STANDBY"}
            </span>
          </Field>
        </PanelSectionRow>
      </PanelSection>

      {/* Main Settings */}
      <PanelSection title="Behavior Settings">
        <PanelSectionRow>
          <ToggleField
            label="Enable Plugin"
            description="Intercepts suspend when downloading, turns off screen, and saves power."
            checked={settings.enabled}
            onChange={(checked) => updateSetting("enabled", checked)}
          />
        </PanelSectionRow>

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

      {/* Power Optimization Options */}
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
    </div>
  );
};
