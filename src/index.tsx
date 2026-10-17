import React, { FC, useState, useEffect, useRef } from "react";
import { definePlugin, routerHook, call, addEventListener, removeEventListener } from "@decky/api";
import { FaDownload } from "react-icons/fa";
import { Overlay } from "./components/Overlay";
import { SettingsPanel } from "./components/SettingsPanel";
import { PluginSettings, DownloadInfo, SystemStatus } from "./types";
import { PLUGIN_STYLES } from "./styles";

// Declare SteamClient global on window
declare global {
  interface Window {
    SteamClient?: {
      Downloads?: {
        GetDownloadOverview?: () => any;
        GetQueue?: () => any;
        RegisterForDownloadOverviewChanges?: (callback: (data: any) => void) => { unregister: () => void };
      };
      System?: {
        RegisterForOnSuspendRequest?: (callback: () => Promise<boolean> | boolean) => { unregister: () => void };
      };
    };
  }
}

const DEFAULT_SETTINGS: PluginSettings = {
  enabled: true,
  min_battery_threshold: 15,
  hud_timeout_seconds: 5,
  auto_suspend_delay_seconds: 15,
  throttle_cpu: true,
  throttle_gpu: true,
  mute_audio: true,
  turn_off_backlight: true,
  oled_black_screen: true,
};

const DEFAULT_DOWNLOAD_INFO: DownloadInfo = {
  is_downloading: false,
  bytes_per_second: 0,
  total_bytes: 0,
  completed_bytes: 0,
  progress_percent: 0,
  game_title: "Steam Game Download",
  estimated_seconds_remaining: 0,
};

// Global shared state for communication between QAM panel and Global Overlay
let sharedDownloadInfo: DownloadInfo = { ...DEFAULT_DOWNLOAD_INFO };
let sharedSettings: PluginSettings = { ...DEFAULT_SETTINGS };
let sharedBatteryCapacity: number = 100;
let sharedIsCharging: boolean = false;
let sharedPowerPlugged: boolean = false;
let sharedIsBackgroundMode: boolean = false;

const stateListeners = new Set<() => void>();
function notifyStateListeners() {
  stateListeners.forEach((cb) => cb());
}

// Global Overlay Container Component registered in routerHook
const GlobalOverlayContainer: FC = () => {
  const [, setTick] = useState<number>(0);

  useEffect(() => {
    const update = () => setTick((t) => t + 1);
    stateListeners.add(update);
    return () => {
      stateListeners.delete(update);
    };
  }, []);

  return (
    <>
      <style>{PLUGIN_STYLES}</style>
      <Overlay
        downloadInfo={sharedDownloadInfo}
        settings={sharedSettings}
        batteryCapacity={sharedBatteryCapacity}
        isCharging={sharedIsCharging}
      />
    </>
  );
};

// Plugin Quick Access Menu Content
const PluginContent: FC = () => {
  const [settings, setSettings] = useState<PluginSettings>(sharedSettings);
  const [downloadInfo, setDownloadInfo] = useState<DownloadInfo>(sharedDownloadInfo);
  const [isBackgroundMode, setIsBackgroundMode] = useState<boolean>(sharedIsBackgroundMode);
  const [batteryCapacity, setBatteryCapacity] = useState<number>(sharedBatteryCapacity);
  const [isCharging, setIsCharging] = useState<boolean>(sharedIsCharging);
  const [powerPlugged, setPowerPlugged] = useState<boolean>(sharedPowerPlugged);

  useEffect(() => {
    const update = () => {
      setSettings(sharedSettings);
      setDownloadInfo(sharedDownloadInfo);
      setIsBackgroundMode(sharedIsBackgroundMode);
      setBatteryCapacity(sharedBatteryCapacity);
      setIsCharging(sharedIsCharging);
      setPowerPlugged(sharedPowerPlugged);
    };

    stateListeners.add(update);
    return () => {
      stateListeners.delete(update);
    };
  }, []);

  const handleUpdateSettings = (newSettings: PluginSettings) => {
    sharedSettings = newSettings;
    setSettings(newSettings);
    notifyStateListeners();
  };

  return (
    <SettingsPanel
      settings={settings}
      setSettings={handleUpdateSettings}
      downloadInfo={downloadInfo}
      isBackgroundMode={isBackgroundMode}
      batteryCapacity={batteryCapacity}
      isCharging={isCharging}
      powerPlugged={powerPlugged}
    />
  );
};

export default definePlugin(() => {
  // Register global overlay in SteamOS DOM
  routerHook.addGlobalComponent("DownloadInBackgroundOverlay", GlobalOverlayContainer);

  let pollInterval: NodeJS.Timeout | null = null;
  let dlUnregister: (() => void) | null = null;
  let suspendUnregister: (() => void) | null = null;

  // Sync state with Python backend
  const syncBackendStatus = async () => {
    try {
      const status: SystemStatus = await call("get_status");
      if (status) {
        sharedIsBackgroundMode = Boolean(status.is_background_mode);
        sharedBatteryCapacity = Number(status.battery_capacity ?? 100);
        sharedIsCharging = Boolean(status.is_charging);
        sharedPowerPlugged = Boolean(status.power_plugged);
        if (status.settings) {
          sharedSettings = { ...sharedSettings, ...status.settings };
        }
        if (status.download_info) {
          sharedDownloadInfo = { ...sharedDownloadInfo, ...status.download_info };
        }
        notifyStateListeners();
      }
    } catch (e) {
      console.error("[DownloadInBackground] Error polling backend status:", e);
    }
  };

  // Poll / Query SteamClient Downloads API
  const querySteamDownloads = async () => {
    try {
      if (window.SteamClient?.Downloads?.GetDownloadOverview) {
        const overview = window.SteamClient.Downloads.GetDownloadOverview();
        if (overview) {
          const bps = Number(overview.bytes_per_second ?? overview.current_bytes_per_second ?? 0);
          const totalBytes = Number(overview.total_bytes ?? overview.bytes_total ?? 0);
          const completedBytes = Number(overview.completed_bytes ?? overview.bytes_downloaded ?? 0);
          const percent = totalBytes > 0
            ? (completedBytes / totalBytes) * 100
            : Number(overview.overall_percent_complete ?? 0);

          let etaSeconds = 0;
          if (bps > 0 && totalBytes > completedBytes) {
            etaSeconds = Math.round((totalBytes - completedBytes) / bps);
          }

          let gameTitle = overview.game_name ?? overview.app_name ?? overview.title;
          if (!gameTitle && window.SteamClient?.Downloads?.GetQueue) {
            const queue = window.SteamClient.Downloads.GetQueue();
            if (Array.isArray(queue) && queue.length > 0) {
              gameTitle = queue[0]?.display_name ?? queue[0]?.app_name ?? queue[0]?.name;
            }
          }

          const isDl = bps > 10000 || overview.bIsDownloading === true || overview.downloading === true;

          const updatedInfo: DownloadInfo = {
            is_downloading: isDl,
            bytes_per_second: bps,
            total_bytes: totalBytes,
            completed_bytes: completedBytes,
            progress_percent: percent,
            game_title: gameTitle || "Steam Download",
            estimated_seconds_remaining: etaSeconds,
          };

          sharedDownloadInfo = updatedInfo;
          notifyStateListeners();

          // Sync download metrics to backend
          call("update_download_status", updatedInfo).catch(() => {});
        }
      }
    } catch (e) {
      // Quietly ignore if SteamClient isn't ready
    }
  };

  // Initialize SteamClient listeners if available
  try {
    if (window.SteamClient?.Downloads?.RegisterForDownloadOverviewChanges) {
      const reg = window.SteamClient.Downloads.RegisterForDownloadOverviewChanges((data: any) => {
        if (data) {
          querySteamDownloads();
        }
      });
      if (reg && typeof reg.unregister === "function") {
        dlUnregister = reg.unregister;
      }
    }
  } catch (e) {
    console.warn("[DownloadInBackground] Could not register for download overview changes:", e);
  }

  // Hook Steam Client Suspend Request if available
  try {
    if (window.SteamClient?.System?.RegisterForOnSuspendRequest) {
      const reg = window.SteamClient.System.RegisterForOnSuspendRequest(async () => {
        console.log("[DownloadInBackground] SteamClient Suspend Request event received!");
        if (sharedSettings.enabled && sharedDownloadInfo.is_downloading) {
          // Intercept SteamClient suspend!
          // Trigger overlay HUD countdown
          window.dispatchEvent(new CustomEvent("decky_event_on_suspend_intercepted", {
            detail: {
              download_info: sharedDownloadInfo,
              hud_timeout: sharedSettings.hud_timeout_seconds,
            }
          }));
          return false; // Prevent suspend in SteamClient
        }
        return true; // Allow suspend
      });
      if (reg && typeof reg.unregister === "function") {
        suspendUnregister = reg.unregister;
      }
    }
  } catch (e) {
    console.warn("[DownloadInBackground] Could not hook SteamClient.System.RegisterForOnSuspendRequest:", e);
  }

  // Initial fetch and start interval
  syncBackendStatus();
  querySteamDownloads();
  pollInterval = setInterval(() => {
    syncBackendStatus();
    querySteamDownloads();
  }, 2000);

  return {
    name: "Download in Background",
    icon: <FaDownload />,
    content: <PluginContent />,
    onDismount() {
      routerHook.removeGlobalComponent("DownloadInBackgroundOverlay");
      if (pollInterval) {
        clearInterval(pollInterval);
      }
      if (dlUnregister) {
        try {
          dlUnregister();
        } catch (e) {}
      }
      if (suspendUnregister) {
        try {
          suspendUnregister();
        } catch (e) {}
      }
    },
  };
});
