import React, { FC, useState } from "react";
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
import { AdvancedSettings } from "./AdvancedSettings";

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
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const updateSetting = async <K extends keyof PluginSettings>(
    key: K,
    val: PluginSettings[K]
  ) => {
    if (saving) return;
    const updated = { ...settings, [key]: val };
    if (key === "enabled" && val === true) updated.enable_plugin_when_plugged_in = false;
    if (key === "enable_plugin_when_plugged_in" && val === true) updated.enabled = false;
    setSaving(true);
    setSettings(updated);
    try {
      const saved: PluginSettings = await call("save_settings", updated);
      setSettings(saved);
    } catch (e) {
      setSettings(settings);
      console.error("[NewSuspendMode] Error saving settings:", e);
      toaster.toast({ title: "New Suspend Mode", body: "Could not save settings.", duration: 4000 });
    } finally {
      setSaving(false);
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
            description="Keeps the plugin enabled on battery and AC power. Turns off the AC-only option below. The configured real-sleep period still applies."
            disabled={saving}
            checked={settings.enabled}
            onChange={(checked) => updateSetting("enabled", checked)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label="Enable Plugin When Plugged In"
            description="Enables the plugin only on AC power and turns off Enable Plugin above. Unplugging during New Suspend Mode enters normal SteamOS sleep. Connecting power while already asleep does not wake the device."
            disabled={saving}
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
              className={`nsm-status-tag ${
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
              className={`nsm-status-tag ${
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
            label="Replace Sleep With New Suspend Mode"
            description="The power button AND the Sleep option in the SteamOS power menu both enter the plugin's new suspend mode instead of the stock one: screen black, downloads carry on, a controller brings it back. Shut Down still powers off for real."
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
                label="Return To New Suspend Mode At Period End"
                description="At the end of the period, the RTC wakes the system from the real sleep and the plugin immediately re-enters the new suspend mode, so a controller can wake it. If off, the console stays in the real sleep until you wake it manually."
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
                  title: "New Suspend Mode",
                  body: "Hardware restored: clocks, power limits and speed caps are back to normal.",
                  duration: 4000,
                });
              } catch (e) {
                toaster.toast({
                  title: "New Suspend Mode",
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

      {advanced && <AdvancedSettings settings={settings} updateSetting={updateSetting} />}

      <PanelSection title="Reset Settings">
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            description="Restores all options to their defaults, including advanced settings, the sleep schedule and AC-only activation."
            disabled={saving}
            onClick={async () => {
              if (saving) return;
              setSaving(true);
              setResetting(true);
              try {
                const defaults: PluginSettings = await call("reset_defaults");
                setSettings(defaults);
                toaster.toast({ title: "New Suspend Mode", body: "All settings restored to defaults.", duration: 4000 });
              } catch (e) {
                console.error("[NewSuspendMode] Error resetting defaults:", e);
                toaster.toast({ title: "New Suspend Mode", body: "Could not reset settings; see the plugin log.", duration: 4000 });
              } finally {
                setSaving(false);
                setResetting(false);
              }
            }}
          >
            {resetting ? "Resetting…" : "Reset Defaults"}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
    </div>
  );
};
