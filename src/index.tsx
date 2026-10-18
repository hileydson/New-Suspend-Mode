import React, { FC, useState, useEffect } from "react";
import { definePlugin, routerHook, call, addEventListener, removeEventListener, toaster } from "@decky/api";
import { Navigation } from "@decky/ui";
import { FaDownload } from "react-icons/fa";
import { Overlay } from "./components/Overlay";
import { SettingsPanel } from "./components/SettingsPanel";
import { PluginSettings, DownloadInfo, SystemStatus } from "./types";
import { PLUGIN_STYLES } from "./styles";

// Declare SteamClient global on window
declare global {
  interface Window {
    SteamClient?: {
      URL?: {
        ExecuteSteamURL?: (url: string) => void;
      };
      Downloads?: {
        GetDownloadOverview?: () => any;
        GetQueue?: () => any;
        RegisterForDownloadOverviewChanges?: (callback: (data: any) => void) => { unregister: () => void };
      };
      System?: {
        RegisterForOnSuspendRequest?: (callback: () => Promise<boolean> | boolean) => { unregister: () => void };
        NavigateToLibraryHome?: () => void;
      };
    };
  }
}

const DEFAULT_SETTINGS: PluginSettings = {
  enabled: true,
  min_battery_threshold: 15,
  hud_timeout_seconds: 5,
  auto_suspend_delay_seconds: 120,
  throttle_cpu: true,
  throttle_gpu: true,
  mute_audio: true,
  turn_off_backlight: true,
  oled_black_screen: true,
  deep_input_lockout: true,
};

// Must match WAKE_COOLDOWN_SECONDS in main.py: the window after a wake in which
// suspend requests are ignored, so the press that woke the console cannot re-sleep it.
const WAKE_COOLDOWN_MS = 5000;

// Backend round-trip cadence. While nothing is downloading the plugin polls slowly and
// sends nothing, so an enabled plugin with no download costs SteamOS nothing.
const POLL_ACTIVE_MS = 2000;
const POLL_IDLE_MS = 5000;
const POLL_DISABLED_MS = 10000;

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
let sharedBackgroundModeEnteredTime: number = 0;
let sharedShowHud: boolean = false;
let sharedCountdown: number = 5;
let sharedWakeCooldownUntil: number = 0;
let sharedHudTimer: NodeJS.Timeout | null = null;

const stateListeners = new Set<() => void>();
function notifyStateListeners() {
  stateListeners.forEach((cb) => cb());
}

/**
 * Closes any open side menu / Quick Access panel, repeatedly, for ~4 seconds.
 *
 * A button pressed while the screen was off is queued by the frozen controller daemon
 * and replayed when it is thawed during the wake, which lands a few hundred
 * milliseconds to a few seconds in. So closing once is not enough: the panel would
 * simply open again right afterwards. Retrying across that whole window is what stops
 * the console from coming back with the sidebar exposed. The current screen is left
 * alone on purpose, so waking up never interrupts a game that is running.
 */
const closeSteamSideMenus = () => {
  const close = () => {
    try {
      Navigation.CloseSideMenus?.();
    } catch (e) {}
  };
  close();
  [150, 400, 800, 1400, 2000, 2800, 3600].forEach((delay) => setTimeout(close, delay));
};

/**
 * Triggers a complete system wake:
 * 1. Synchronously drops any black screen or HUD from the DOM
 * 2. Activates the cooldown against re-sleep
 * 3. Calls backend exit_background_mode to restore hardware/backlight
 * 4. Keeps dismissing any menu a stray button press may have opened
 */
const triggerFullWake = async (reason: string = "wake") => {
  console.log("[DownloadInBackground] triggerFullWake called! Reason:", reason);
  sharedIsBackgroundMode = false;
  sharedShowHud = false;
  sharedWakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;

  if (sharedHudTimer) {
    clearInterval(sharedHudTimer);
    sharedHudTimer = null;
  }

  // Instantly unmounts overlay from the DOM
  notifyStateListeners();
  closeSteamSideMenus();

  try {
    await call("exit_background_mode", reason);
  } catch (e) {
    console.error("[DownloadInBackground] Error calling exit_background_mode:", e);
  }

  toaster.toast({
    title: "Download in Background",
    body: "Console awakened!",
    duration: 2000,
  });
};

/**
 * Enters Pitch Black mode (download continuing in background)
 */
const triggerEnterBlackout = async (reason: string = "countdown_completed") => {
  if (Date.now() < sharedWakeCooldownUntil) {
    console.log("[DownloadInBackground] Wake cooldown active, blocking enter blackout.");
    return;
  }

  if (sharedHudTimer) {
    clearInterval(sharedHudTimer);
    sharedHudTimer = null;
  }

  sharedShowHud = false;
  sharedIsBackgroundMode = true;
  sharedBackgroundModeEnteredTime = Date.now();
  notifyStateListeners();

  try {
    const success: any = await call("enter_background_mode", reason);
    if (success === false) {
      // Backend rejected entry -> restore to normal
      sharedIsBackgroundMode = false;
      notifyStateListeners();
    }
  } catch (e) {
    console.error("[DownloadInBackground] Error entering background mode:", e);
  }
};

/**
 * Starts initial HUD Countdown before turning screen black
 */
const startHudCountdown = (customTimeout?: number) => {
  if (sharedIsBackgroundMode || Date.now() < sharedWakeCooldownUntil) {
    return;
  }

  const timeoutSec = customTimeout ?? sharedSettings.hud_timeout_seconds ?? 5;
  if (timeoutSec <= 0) {
    triggerEnterBlackout("immediate");
    return;
  }

  if (sharedHudTimer) {
    clearInterval(sharedHudTimer);
  }

  sharedCountdown = timeoutSec;
  sharedShowHud = true;
  sharedIsBackgroundMode = false;
  notifyStateListeners();

  let remaining = timeoutSec;
  sharedHudTimer = setInterval(() => {
    remaining -= 1;
    sharedCountdown = remaining;
    notifyStateListeners();

    if (remaining <= 0) {
      if (sharedHudTimer) {
        clearInterval(sharedHudTimer);
        sharedHudTimer = null;
      }
      triggerEnterBlackout("countdown_completed");
    }
  }, 1000);
};

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

  // Intercept and swallow keyboard/gamepad navigation while in background mode
  useEffect(() => {
    if (!sharedIsBackgroundMode) return;

    const blockInput = (e: Event) => {
      e.stopPropagation();
      e.stopImmediatePropagation();
      e.preventDefault();
    };

    const events = [
      "keydown", "keyup", "keypress",
      "pointerdown", "pointerup", "pointermove",
      "touchstart", "touchend", "touchmove",
      "mousedown", "mouseup", "click", "contextmenu"
    ];

    events.forEach((ev) => window.addEventListener(ev, blockInput, true));

    return () => {
      events.forEach((ev) => window.removeEventListener(ev, blockInput, true));
    };
  }, [sharedIsBackgroundMode]);

  // CRITICAL: If NOT in background mode and NOT showing HUD: DO NOT RENDER ANYTHING!
  // This guarantees that once awakened, the black div is 100% UNMOUNTED from the DOM.
  if (!sharedIsBackgroundMode && !sharedShowHud) {
    return null;
  }

  return (
    <>
      <style>{PLUGIN_STYLES}</style>
      <Overlay
        isBackgroundMode={sharedIsBackgroundMode}
        showHud={sharedShowHud}
        countdown={sharedCountdown}
        downloadInfo={sharedDownloadInfo}
        settings={sharedSettings}
        batteryCapacity={sharedBatteryCapacity}
        isCharging={sharedIsCharging}
        onWake={() => triggerFullWake("overlay_wake")}
        onEnterBlackout={() => triggerEnterBlackout("manual_screen_off")}
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

  let pollTimer: NodeJS.Timeout | null = null;
  let pollStopped = false;
  let dlUnregister: (() => void) | null = null;
  let suspendUnregister: (() => void) | null = null;
  let modeUnregister: any = null;
  let suspendEventUnregister: any = null;
  let batteryCriticalUnregister: any = null;
  let downloadsCompletedUnregister: any = null;

  // Listen directly for background mode changes from Python backend
  try {
    modeUnregister = addEventListener("background_mode_changed", (data: any) => {
      console.log("[DownloadInBackground] background_mode_changed event received:", data);
      const isBg = typeof data === "boolean" ? data : Boolean(data?.is_background_mode);
      if (!isBg) {
        // System awakened from backend!
        sharedIsBackgroundMode = false;
        sharedShowHud = false;
        sharedWakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;
        if (sharedHudTimer) {
          clearInterval(sharedHudTimer);
          sharedHudTimer = null;
        }
        notifyStateListeners();
        closeSteamSideMenus();
      } else {
        sharedIsBackgroundMode = true;
        sharedBackgroundModeEnteredTime = Date.now();
        sharedShowHud = false;
        notifyStateListeners();
      }
    });
  } catch (e) {
    console.warn("[DownloadInBackground] Could not register background_mode_changed listener:", e);
  }

  // Listen for suspend intercepted events from backend
  try {
    suspendEventUnregister = addEventListener("on_suspend_intercepted", (data: any) => {
      console.log("[DownloadInBackground] on_suspend_intercepted event received:", data);
      const now = Date.now();
      if (sharedIsBackgroundMode) {
        // If already in background mode, this is a wake action!
        triggerFullWake("suspend_event_during_bg");
        return;
      }
      if (now < sharedWakeCooldownUntil) {
        console.log("[DownloadInBackground] Ignoring on_suspend_intercepted during wake cooldown.");
        return;
      }
      const timeoutSec = data?.hud_timeout ?? sharedSettings.hud_timeout_seconds ?? 5;
      startHudCountdown(timeoutSec);
    });
  } catch (e) {
    console.warn("[DownloadInBackground] Could not register on_suspend_intercepted listener:", e);
  }

  // Critical battery auto-suspend notification
  try {
    batteryCriticalUnregister = addEventListener("battery_critical_suspend", (data: any) => {
      toaster.toast({
        title: "Download in Background",
        body: `Battery reached ${data?.capacity ?? 15}%. Entering sleep now.`,
        duration: 4000,
        critical: true,
      });
    });
  } catch (e) {}

  // Downloads completed notification
  try {
    downloadsCompletedUnregister = addEventListener("downloads_completed_suspend", () => {
      toaster.toast({
        title: "Download in Background",
        body: "All downloads completed! Suspending console.",
        duration: 3500,
      });
    });
  } catch (e) {}

  // Last snapshot read straight from the Steam client, and when it was taken.
  // It is more accurate than the backend's own detection, but only while it is fresh.
  let lastFrontendInfo: DownloadInfo | null = null;
  let lastFrontendInfoTime = 0;

  // Sync state with Python backend
  const syncBackendStatus = async () => {
    try {
      const status: SystemStatus = await call("get_status");
      if (status) {
        const backendIsBg = Boolean(status.is_background_mode);
        if (sharedIsBackgroundMode && !backendIsBg) {
          console.log("[DownloadInBackground] Backend woke up -> Synchronizing frontend!");
          sharedIsBackgroundMode = false;
          sharedShowHud = false;
          sharedWakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;
          if (sharedHudTimer) {
            clearInterval(sharedHudTimer);
            sharedHudTimer = null;
          }
          notifyStateListeners();
          closeSteamSideMenus();
        } else {
          sharedIsBackgroundMode = backendIsBg;
        }

        sharedBatteryCapacity = Number(status.battery_capacity ?? 100);
        sharedIsCharging = Boolean(status.is_charging);
        sharedPowerPlugged = Boolean(status.power_plugged);
        if (status.settings) {
          sharedSettings = { ...sharedSettings, ...status.settings };
        }
        if (status.download_info) {
          const frontendIsFresh = Date.now() - lastFrontendInfoTime < 6000;
          sharedDownloadInfo =
            frontendIsFresh && lastFrontendInfo
              ? { ...status.download_info, ...lastFrontendInfo }
              : { ...sharedDownloadInfo, ...status.download_info };
        }
        notifyStateListeners();
      }
    } catch (e) {
      console.error("[DownloadInBackground] Error polling backend status:", e);
    }
  };

  // Hand download metrics to the backend only when they actually changed, or every 8s
  // while downloading so the backend knows the frontend is still reporting.
  let lastSentKey = "";
  let lastSentTime = 0;
  const pushDownloadStatus = (info: DownloadInfo) => {
    const key = [
      info.is_downloading,
      info.is_paused,
      info.game_title,
      Math.round(info.progress_percent),
    ].join("|");
    const now = Date.now();
    const isIdle = !info.is_downloading && !info.is_paused;
    if (key === lastSentKey && (isIdle || now - lastSentTime < 8000)) {
      // Idle and unchanged: say nothing at all, so an enabled plugin with no download
      // is completely silent instead of poking the backend twice a second.
      return;
    }
    lastSentKey = key;
    lastSentTime = now;
    call("update_download_status", info).catch(() => {});
  };

  // Poll / Query SteamClient Downloads API
  const querySteamDownloads = async () => {
    if (sharedSettings.enabled === false) {
      return;
    }
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

          const isPaused = Boolean(
            overview.bIsPaused ||
            overview.paused ||
            overview.bPaused ||
            overview.bQueuePaused ||
            overview.is_paused ||
            overview.m_bPaused
          );

          let queuePaused = false;
          if (window.SteamClient?.Downloads?.GetQueue) {
            const queue = window.SteamClient.Downloads.GetQueue();
            if (Array.isArray(queue)) {
              if (queue.length === 0) {
                queuePaused = true;
              } else {
                const hasActiveUnpaused = queue.some(
                  (item: any) =>
                    (item.bDownloading || item.bIsDownloading || item.active) &&
                    !item.bPaused &&
                    !item.bIsPaused &&
                    !item.paused
                );
                if (!hasActiveUnpaused) {
                  queuePaused = true;
                }
              }
            }
          }

          const isDl =
            !isPaused &&
            !queuePaused &&
            (bps > 10000 || (overview.bIsDownloading === true && bps > 0));

          const updatedInfo: DownloadInfo = {
            is_downloading: isDl,
            is_paused: isPaused || queuePaused,
            bytes_per_second: isDl ? bps : 0,
            total_bytes: totalBytes,
            completed_bytes: completedBytes,
            progress_percent: percent,
            game_title: gameTitle || "Steam Download",
            estimated_seconds_remaining: isDl ? etaSeconds : 0,
          };

          sharedDownloadInfo = updatedInfo;
          lastFrontendInfo = updatedInfo;
          lastFrontendInfoTime = Date.now();
          notifyStateListeners();

          // Sync download metrics to backend
          pushDownloadStatus(updatedInfo);
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
        const now = Date.now();

        // 1. If currently in background mode, this suspend request is actually a WAKE request from the Power Button!
        if (sharedIsBackgroundMode) {
          const timeInBg = Date.now() - sharedBackgroundModeEnteredTime;
          if (timeInBg < 2000) {
            console.log(`[DownloadInBackground] Ignoring suspend request in initial transition grace period (${timeInBg}ms).`);
            return false;
          }
          console.log("[DownloadInBackground] Power button pressed while in background mode -> WAKING UP!");
          await triggerFullWake("power_button_wake");
          return false; // Prevent Steam from suspending
        }

        // 2. Cooldown check: ignore suspend request if the system just woke up
        if (now < sharedWakeCooldownUntil) {
          console.log("[DownloadInBackground] Ignoring suspend request: within wake cooldown period.");
          return false;
        }

        // 3. With the plugin off, or nothing downloading as of the last poll, get out of
        // the way immediately: no backend round-trip, no HUD, so SteamOS suspends with
        // its own animation exactly as it does without this plugin installed.
        if (!sharedSettings.enabled) {
          return true;
        }
        if (!sharedDownloadInfo.is_downloading || sharedDownloadInfo.is_paused) {
          console.log("[DownloadInBackground] No active download -> Allowing stock SteamOS suspend.");
          return true;
        }

        // 4. Confirm against the Steam client before taking the suspend over
        await querySteamDownloads();

        const isDownloading = Boolean(
          sharedDownloadInfo.is_downloading && !sharedDownloadInfo.is_paused
        );

        if (isDownloading) {
          console.log("[DownloadInBackground] Active download running -> Intercepting suspend and showing HUD");
          try {
            await call("trigger_suspend_intercept");
          } catch (e) {
            console.error("[DownloadInBackground] Error calling trigger_suspend_intercept:", e);
          }
          startHudCountdown(sharedSettings.hud_timeout_seconds ?? 5);
          return false; // Prevent suspend in SteamClient
        }

        console.log("[DownloadInBackground] Download is paused or idle -> Allowing normal Steam suspend without intercepting.");
        return true; // Allow suspend immediately
      });
      if (reg && typeof reg.unregister === "function") {
        suspendUnregister = reg.unregister;
      }
    }
  } catch (e) {
    console.warn("[DownloadInBackground] Could not hook SteamClient.System.RegisterForOnSuspendRequest:", e);
  }

  // Poll the backend on an adaptive schedule instead of a fixed 1.5s interval
  const scheduleNextPoll = () => {
    const isActive =
      sharedIsBackgroundMode ||
      sharedShowHud ||
      Boolean(sharedDownloadInfo.is_downloading && !sharedDownloadInfo.is_paused);
    const delay = !sharedSettings.enabled
      ? POLL_DISABLED_MS
      : isActive
      ? POLL_ACTIVE_MS
      : POLL_IDLE_MS;
    pollTimer = setTimeout(runPoll, delay);
  };

  const runPoll = async () => {
    try {
      await syncBackendStatus();
      await querySteamDownloads();
    } finally {
      if (!pollStopped) {
        scheduleNextPoll();
      }
    }
  };

  // Initial fetch, then keep polling
  runPoll();

  // Kernel sleep resume detection via clock-jump heartbeat
  let lastHeartbeat = Date.now();
  const heartbeatInterval = setInterval(() => {
    const now = Date.now();
    const delta = now - lastHeartbeat;
    lastHeartbeat = now;

    // CRITICAL: Do NOT trigger clock jump wake if we are intentionally in background mode!
    // Background mode intentionally throttles CPU and browser threads, causing setInterval delays.
    // Clock-jump detection is ONLY meant to wake up from actual Linux kernel sleep.
    if (sharedIsBackgroundMode) {
      return;
    }

    if (delta > 15000) {
      console.log(`[DownloadInBackground] Kernel resume detected (delta=${delta}ms)! Enforcing wake state.`);
      sharedWakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;
      if (sharedHudTimer) {
        clearInterval(sharedHudTimer);
        sharedHudTimer = null;
      }
      sharedShowHud = false;
      sharedIsBackgroundMode = false;
      notifyStateListeners();
      call("exit_background_mode", "kernel_resume_clock_jump").catch(() => {});
    }
  }, 2000);

  return {
    name: "Download in Background",
    icon: <FaDownload />,
    content: <PluginContent />,
    onDismount() {
      routerHook.removeGlobalComponent("DownloadInBackgroundOverlay");
      pollStopped = true;
      if (pollTimer) {
        clearTimeout(pollTimer);
        pollTimer = null;
      }
      if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
      }
      if (sharedHudTimer) {
        clearInterval(sharedHudTimer);
        sharedHudTimer = null;
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
      if (modeUnregister) {
        try {
          removeEventListener("background_mode_changed", modeUnregister);
        } catch (e) {}
      }
      if (suspendEventUnregister) {
        try {
          removeEventListener("on_suspend_intercepted", suspendEventUnregister);
        } catch (e) {}
      }
      if (batteryCriticalUnregister) {
        try {
          removeEventListener("battery_critical_suspend", batteryCriticalUnregister);
        } catch (e) {}
      }
      if (downloadsCompletedUnregister) {
        try {
          removeEventListener("downloads_completed_suspend", downloadsCompletedUnregister);
        } catch (e) {}
      }
    },
  };
});
