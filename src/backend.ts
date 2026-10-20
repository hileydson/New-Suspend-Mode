import { addEventListener, call, removeEventListener, toaster } from "@decky/api";
import { SystemStatus } from "./types";
import { WAKE_COOLDOWN_MS, getState, isPluginEnabled, runtime, setState } from "./state";
import {
  cancelHudCountdown,
  clearStandbySplash,
  finishWakeUi,
  startHudCountdown,
  startStandbySplash,
  triggerFullWake,
} from "./flows";
import { freshSteamDownloadInfo, querySteamDownloads } from "./steam/downloads";

// Backend round-trip cadence. While nothing is downloading the plugin polls slowly and
// sends nothing, so an enabled plugin with no download costs SteamOS nothing.
const POLL_ACTIVE_MS = 2000;
const POLL_IDLE_MS = 5000;
const POLL_DISABLED_MS = 10000;

/** Subscribes to everything the Python backend announces. Returns the unsubscribe. */
export const listenToBackend = (): (() => void) => {
  const subscriptions: Array<[string, any]> = [];
  const listen = (event: string, handler: (data: any) => void) => {
    try {
      subscriptions.push([event, addEventListener(event, handler)]);
    } catch (e) {
      console.warn(`[NewSuspendMode] Could not register ${event} listener:`, e);
    }
  };

  listen("background_mode_changed", (data: any) => {
    console.log("[NewSuspendMode] background_mode_changed event received:", data);
    const isBg = typeof data === "boolean" ? data : Boolean(data?.is_background_mode);
    if (!isBg) {
      // System awakened from the backend: same cleanup as a wake asked for here.
      finishWakeUi(String(data?.reason ?? "backend_wake"));
      return;
    }
    runtime.backgroundModeEnteredTime = Date.now();
    clearStandbySplash();
    setState({
      isBackgroundMode: true,
      showHud: false,
      ...(Boolean(data?.standby) ? { standbyMode: true } : {}),
    });
  });

  listen("on_suspend_intercepted", (data: any) => {
    console.log("[NewSuspendMode] on_suspend_intercepted event received:", data);
    if (getState().isBackgroundMode) {
      // If already in background mode, this is a wake action!
      triggerFullWake("suspend_event_during_bg");
      return;
    }
    if (Date.now() < runtime.wakeCooldownUntil) {
      console.log("[NewSuspendMode] Ignoring on_suspend_intercepted during wake cooldown.");
      return;
    }
    startHudCountdown(data?.hud_timeout ?? getState().settings.hud_timeout_seconds ?? 5);
  });

  // Backend asked for standby: draw the plugin mark first, then go dark
  listen("on_standby_requested", (data: any) => {
    console.log("[NewSuspendMode] on_standby_requested received:", data);
    if (getState().isBackgroundMode) {
      return;
    }
    const seconds = Number(data?.splash_seconds ?? getState().settings.hud_timeout_seconds ?? 5);
    startStandbySplash(seconds, String(data?.reason ?? "standby_splash"));
  });

  listen("battery_critical_suspend", (data: any) => {
    // A suspend the plugin itself asked for: Steam must be allowed to prepare for it.
    runtime.realSuspendUntil = Date.now() + 60000;
    toaster.toast({
      title: "New Suspend Mode",
      body: `Battery reached ${data?.capacity ?? 15}%. Entering sleep now.`,
      duration: 4000,
      critical: true,
    });
  });

  listen("downloads_completed_suspend", () => {
    // Also a real suspend: let Steam suspend its games properly on the way down.
    runtime.realSuspendUntil = Date.now() + 60000;
    toaster.toast({
      title: "New Suspend Mode",
      body: "All downloads completed! Suspending console.",
      duration: 3500,
    });
  });

  return () => {
    for (const [event, listener] of subscriptions) {
      try {
        removeEventListener(event, listener);
      } catch (e) {}
    }
  };
};

/** Brings the interface's state in line with the backend's. */
const syncBackendStatus = async () => {
  try {
    const status: SystemStatus = await call("get_status");
    if (!status) return;

    const backendIsBg = Boolean(status.is_background_mode);
    if (getState().isBackgroundMode && !backendIsBg) {
      console.log("[NewSuspendMode] Backend woke up -> Synchronizing frontend!");
      finishWakeUi("status_poll_sync");
    }

    const current = getState();
    const fresh = freshSteamDownloadInfo();
    setState({
      isBackgroundMode: backendIsBg,
      standbyMode: Boolean(status.standby_mode),
      batteryCapacity: Number(status.battery_capacity ?? 100),
      isCharging: Boolean(status.is_charging),
      powerPlugged: Boolean(status.power_plugged),
      settings: status.settings ? { ...current.settings, ...status.settings } : current.settings,
      downloadInfo: status.download_info
        ? fresh
          ? { ...status.download_info, ...fresh }
          : { ...current.downloadInfo, ...status.download_info }
        : current.downloadInfo,
    });
  } catch (e) {
    console.error("[NewSuspendMode] Error polling backend status:", e);
  }
};

/**
 * Polls the backend on an adaptive schedule, and watches for a kernel resume.
 * Returns the function that stops both.
 */
export const startBackendSync = (): (() => void) => {
  let stopped = false;
  let pollTimer: ReturnType<typeof setTimeout> | null = null;

  const scheduleNextPoll = () => {
    const s = getState();
    const isActive =
      s.isBackgroundMode ||
      s.showHud ||
      Boolean(s.downloadInfo.is_downloading && !s.downloadInfo.is_paused);
    const delay = !isPluginEnabled() ? POLL_DISABLED_MS : isActive ? POLL_ACTIVE_MS : POLL_IDLE_MS;
    pollTimer = setTimeout(runPoll, delay);
  };

  const runPoll = async () => {
    try {
      await syncBackendStatus();
      await querySteamDownloads();
    } finally {
      if (!stopped) {
        scheduleNextPoll();
      }
    }
  };

  runPoll();

  // Kernel sleep resume detection: the clock jumps forward across a real suspend.
  let lastHeartbeat = Date.now();
  const heartbeat = setInterval(() => {
    const now = Date.now();
    const delta = now - lastHeartbeat;
    lastHeartbeat = now;

    // Our own mode throttles the CPU, which delays timers on purpose; only a real
    // kernel sleep counts here.
    if (getState().isBackgroundMode) {
      return;
    }

    if (delta > 15000) {
      console.log(`[NewSuspendMode] Kernel resume detected (delta=${delta}ms)! Enforcing wake state.`);
      runtime.wakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;
      cancelHudCountdown();
      setState({ showHud: false, isBackgroundMode: false });
      call("exit_background_mode", "kernel_resume_clock_jump").catch(() => {});
    }
  }, 2000);

  return () => {
    stopped = true;
    if (pollTimer) clearTimeout(pollTimer);
    clearInterval(heartbeat);
  };
};
