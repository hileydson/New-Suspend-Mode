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
  block_controller_hidraw: false,
  limit_download_speed: true,
  download_speed_limit_mbps: 6,
  download_cpu_percent: 30,
  debug_logging: true,
  standby_on_power_off: false,
  wake_on_bluetooth_connect: true,
  wake_on_controller_button: true,
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
let sharedStandbyMode: boolean = false;
let sharedBackgroundModeEnteredTime: number = 0;
let sharedShowHud: boolean = false;
let sharedShowSplash: boolean = false;
let sharedSplashTimer: NodeJS.Timeout | null = null;
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
 * The Steam UI route at the moment the power menu's Sleep was taken over.
 *
 * Picking Sleep is a UI action, unlike the power button: the menu is open and Steam's
 * own click handler may move the interface somewhere (and dim or blank it) before the
 * suspend call it ends with ever reaches us. If it did, the route is put back on wake;
 * if it did not, nothing happens, because the route will not have changed.
 */
let sharedRouteBeforeTakeover: string | null = null;

const currentUiRoute = (): string | null => {
  try {
    return window.location.pathname || null;
  } catch (e) {
    return null;
  }
};

const restoreUiRoute = () => {
  const target = sharedRouteBeforeTakeover;
  sharedRouteBeforeTakeover = null;
  if (!target) return;
  const now = currentUiRoute();
  if (!now || now === target) return;
  console.log(`[DownloadInBackground] Steam UI moved to ${now} on sleep; going back to ${target}.`);
  try {
    (Navigation as any).Navigate?.(target);
  } catch (e) {
    console.warn("[DownloadInBackground] Could not restore the Steam UI route:", e);
  }
};

/**
 * Records what is actually on screen, for a wake that comes back only partially.
 *
 * The plugin's own overlay is unmounted synchronously on wake, and while it is up it
 * swallows every pointer and key event, so a screen that is black with working menus is
 * something else's. This names it: the elements under a handful of screen points, with
 * their background, opacity and stacking.
 */
const probeWakeScreen = (reason: string) => {
  if (sharedSettings.debug_logging === false) {
    return;
  }
  try {
    const points: Array<[number, number]> = [[0.5, 0.5], [0.5, 0.2], [0.5, 0.8]];
    const samples = points.map(([fx, fy]) => {
      const x = Math.round(window.innerWidth * fx);
      const y = Math.round(window.innerHeight * fy);
      const chain: any[] = [];
      let node = document.elementFromPoint(x, y) as HTMLElement | null;
      for (let depth = 0; node && depth < 5; depth++) {
        const cs = window.getComputedStyle(node);
        const rect = node.getBoundingClientRect();
        chain.push({
          tag: node.tagName,
          cls: String((node as any).className ?? "").slice(0, 120),
          bg: cs.backgroundColor,
          opacity: cs.opacity,
          z: cs.zIndex,
          pos: cs.position,
          vis: cs.visibility,
          display: cs.display,
          size: [Math.round(rect.width), Math.round(rect.height)],
        });
        node = node.parentElement;
      }
      return { at: [fx, fy], chain };
    });

    call("log_debug", {
      kind: "wake_screen_probe",
      reason,
      route: currentUiRoute(),
      route_at_takeover: sharedRouteBeforeTakeover,
      visibility: document.visibilityState,
      hidden: document.hidden,
      viewport: [window.innerWidth, window.innerHeight],
      overlay_state: {
        background_mode: sharedIsBackgroundMode,
        show_hud: sharedShowHud,
        show_splash: sharedShowSplash,
        standby: sharedStandbyMode,
      },
      samples,
    }).catch(() => {});
  } catch (e) {
    console.warn("[DownloadInBackground] Wake screen probe failed:", e);
  }
};

const clearStandbySplash = () => {
  if (sharedSplashTimer) {
    clearTimeout(sharedSplashTimer);
    sharedSplashTimer = null;
  }
  sharedShowSplash = false;
};

/**
 * Everything the interface has to undo on wake, shared by both ways a wake arrives:
 * this side asking for it, and the backend announcing it already happened.
 *
 * It used to be written out twice, and the backend's copy was the shorter one: it never
 * cleared the standby splash or the standby flag, so a wake that came from the backend
 * could leave state behind that the plugin's own overlay is drawn from.
 */
const finishWakeUi = (reason: string) => {
  sharedIsBackgroundMode = false;
  sharedShowHud = false;
  sharedStandbyMode = false;
  sharedWakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;
  clearStandbySplash();
  if (sharedHudTimer) {
    clearInterval(sharedHudTimer);
    sharedHudTimer = null;
  }

  // Unmounts the overlay from the DOM before anything else is attempted.
  notifyStateListeners();
  closeSteamSideMenus();

  // Records what is on screen while it is still wrong, then puts the interface back
  // where it was if Steam's own sleep handler moved it.
  probeWakeScreen(reason);
  restoreUiRoute();

  // A nudge for anything that stopped repainting while the screen was off.
  try {
    window.dispatchEvent(new Event("resize"));
  } catch (e) {}
};

/**
 * Enters standby, replacing the HUD with nothing: the splash has already been shown.
 */
const triggerEnterStandby = async (reason: string) => {
  if (Date.now() < sharedWakeCooldownUntil) {
    console.log("[DownloadInBackground] Wake cooldown active, not entering standby.");
    return;
  }
  if (sharedHudTimer) {
    clearInterval(sharedHudTimer);
    sharedHudTimer = null;
  }
  clearStandbySplash();
  sharedShowHud = false;
  sharedIsBackgroundMode = true;
  sharedStandbyMode = true;
  sharedBackgroundModeEnteredTime = Date.now();
  notifyStateListeners();

  try {
    const success: any = await call("enter_background_mode", reason);
    if (success === false) {
      sharedIsBackgroundMode = false;
      notifyStateListeners();
    }
  } catch (e) {
    console.error("[DownloadInBackground] Error entering standby:", e);
  }
};

/**
 * Shows the plugin mark, THEN enters standby a few seconds later.
 *
 * The order matters: the backlight is driven to zero as part of entering, so anything
 * drawn after that is invisible. This mirrors the download HUD countdown, which is why
 * a download shows its card but standby used to appear to show nothing at all.
 */
const startStandbySplash = (seconds: number, reason: string = "standby_splash") => {
  if (sharedIsBackgroundMode || Date.now() < sharedWakeCooldownUntil) {
    return;
  }
  if (seconds <= 0) {
    triggerEnterStandby(reason);
    return;
  }
  if (sharedHudTimer) {
    clearInterval(sharedHudTimer);
    sharedHudTimer = null;
  }
  clearStandbySplash();
  sharedShowHud = false;
  sharedShowSplash = true;
  notifyStateListeners();

  sharedSplashTimer = setTimeout(() => {
    sharedSplashTimer = null;
    triggerEnterStandby(reason);
  }, seconds * 1000);
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
  finishWakeUi(reason);

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

/**
 * Takes over Sleep chosen from the SteamOS power menu, at the only point where it is
 * safe to do so.
 *
 * Blocking the suspend lower down does not work. By the time logind sees the request,
 * Steam has already begun its own suspend sequence and blanked the screen; making the
 * suspend fail there (an inhibitor, or a masked systemd sleep target) leaves the session
 * on a black, lit screen that it never comes back from. So the client's own suspend
 * entry points are wrapped instead, and Steam never starts that sequence at all.
 *
 * When the plugin has no business taking the sleep over, the original method is called
 * and SteamOS suspends exactly as it does without this plugin.
 */
const SUSPEND_METHODS: Array<[string, string]> = [
  ["System", "SuspendPC"],
  ["System", "Suspend"],
  ["User", "StartSuspend"],
  ["User", "SuspendPC"],
];

interface SuspendHook {
  owner: any;
  name: string;
  original: (...args: any[]) => any;
}

let suspendHooks: SuspendHook[] = [];
let suspendPassThrough = false;

/**
 * Calls the real Steam method. The flag covers the case of one suspend entry point
 * calling another one that is also wrapped, which would otherwise loop back in here.
 */
const callOriginalSuspend = (hook: SuspendHook, args: any[]): any => {
  suspendPassThrough = true;
  try {
    return hook.original.apply(hook.owner, args);
  } finally {
    setTimeout(() => {
      suspendPassThrough = false;
    }, 0);
  }
};

const handleMenuSuspend = (hook: SuspendHook, args: any[]): any => {
  // Our own pass-through, or the plugin is off: stock behaviour.
  if (suspendPassThrough || !sharedSettings.enabled) {
    return callOriginalSuspend(hook, args);
  }

  // Our screen is already up: a sleep request now is the way out of it, not a new one.
  if (sharedIsBackgroundMode) {
    const timeInBg = Date.now() - sharedBackgroundModeEnteredTime;
    if (timeInBg >= 2000) {
      console.log(`[DownloadInBackground] ${hook.name} while in our mode -> waking up.`);
      triggerFullWake("menu_suspend_wake");
    }
    return Promise.resolve();
  }

  // The splash or the HUD is already counting down into our mode, or the console only
  // just woke up: swallow it either way.
  if (sharedShowSplash || sharedShowHud || Date.now() < sharedWakeCooldownUntil) {
    return Promise.resolve();
  }

  // Nothing of ours would happen here, so do not even pause the menu: SteamOS sleeps
  // with its own animation, as if the plugin were not installed.
  const looksIdle = !sharedDownloadInfo.is_downloading || sharedDownloadInfo.is_paused;
  if (looksIdle && !sharedSettings.standby_on_power_off) {
    return callOriginalSuspend(hook, args);
  }

  // Remember where the interface was, and dismiss the power menu that is still open.
  // Steam's own suspend flow would have taken it down; the power-button path, which
  // comes back clean, never has a menu open in the first place.
  sharedRouteBeforeTakeover = currentUiRoute();
  closeSteamSideMenus();

  // The backend decides, on state it re-reads right now rather than on the last poll,
  // and starts the standby splash itself when standby is what takes over.
  console.log(`[DownloadInBackground] Power menu sleep (${hook.name}) -> asking the backend.`);
  call("trigger_suspend_intercept")
    .then((res: any) => {
      const verdict = String(res?.verdict ?? "");
      console.log(`[DownloadInBackground] Power menu sleep verdict: ${verdict}`);
      if (verdict === "hud") {
        startHudCountdown(sharedSettings.hud_timeout_seconds ?? 5);
      } else if (verdict === "allow") {
        // Not ours after all (a download paused moments ago): hand the sleep back, and
        // forget the route, since SteamOS is about to suspend for real.
        sharedRouteBeforeTakeover = null;
        callOriginalSuspend(hook, args);
      }
    })
    .catch((e) => {
      console.error("[DownloadInBackground] trigger_suspend_intercept failed:", e);
      callOriginalSuspend(hook, args);
    });
  return Promise.resolve();
};

const installSuspendMethodHooks = (): number => {
  const sc: any = (window as any).SteamClient;
  if (!sc || suspendHooks.length > 0) {
    return suspendHooks.length;
  }
  const hooked: string[] = [];
  for (const [group, name] of SUSPEND_METHODS) {
    const owner = sc[group];
    const original = owner?.[name];
    if (typeof original !== "function") {
      continue;
    }
    const hook: SuspendHook = { owner, name: `${group}.${name}`, original };
    try {
      owner[name] = function (...args: any[]) {
        // Whatever goes wrong in here, the console must still be able to sleep.
        try {
          return handleMenuSuspend(hook, args);
        } catch (e) {
          console.error("[DownloadInBackground] Suspend hook failed, falling back to SteamOS:", e);
          return callOriginalSuspend(hook, args);
        }
      };
      if (owner[name] === original) {
        // A read-only or proxied property: do not claim it was hooked.
        console.warn(`[DownloadInBackground] SteamClient.${group}.${name} could not be replaced.`);
        continue;
      }
      suspendHooks.push(hook);
      hooked.push(hook.name);
    } catch (e) {
      console.warn(`[DownloadInBackground] Could not hook SteamClient.${group}.${name}:`, e);
    }
  }
  console.log(
    `[DownloadInBackground] Suspend entry points hooked: ${hooked.join(", ") || "none"}`
  );
  call("log_debug", {
    kind: "suspend_hooks",
    hooked,
    system_methods: sc?.System ? Object.keys(sc.System).filter((k) => /susp|sleep|power/i.test(k)) : null,
    user_methods: sc?.User ? Object.keys(sc.User).filter((k) => /susp|sleep|power/i.test(k)) : null,
  }).catch(() => {});
  return suspendHooks.length;
};

const removeSuspendMethodHooks = () => {
  for (const hook of suspendHooks) {
    try {
      const [, name] = hook.name.split(".");
      hook.owner[name] = hook.original;
    } catch (e) {}
  }
  suspendHooks = [];
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
  if (!sharedIsBackgroundMode && !sharedShowHud && !sharedShowSplash) {
    return null;
  }

  return (
    <>
      <style>{PLUGIN_STYLES}</style>
      <Overlay
        isBackgroundMode={sharedIsBackgroundMode}
        showHud={sharedShowHud}
        showSplash={sharedShowSplash}
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
  const [standbyMode, setStandbyMode] = useState<boolean>(sharedStandbyMode);
  const [batteryCapacity, setBatteryCapacity] = useState<number>(sharedBatteryCapacity);
  const [isCharging, setIsCharging] = useState<boolean>(sharedIsCharging);
  const [powerPlugged, setPowerPlugged] = useState<boolean>(sharedPowerPlugged);

  useEffect(() => {
    const update = () => {
      setSettings(sharedSettings);
      setDownloadInfo(sharedDownloadInfo);
      setIsBackgroundMode(sharedIsBackgroundMode);
      setStandbyMode(sharedStandbyMode);
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
      standbyMode={standbyMode}
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
  let standbyRequestUnregister: any = null;
  let batteryCriticalUnregister: any = null;
  let downloadsCompletedUnregister: any = null;

  // Listen directly for background mode changes from Python backend
  try {
    modeUnregister = addEventListener("background_mode_changed", (data: any) => {
      console.log("[DownloadInBackground] background_mode_changed event received:", data);
      const isBg = typeof data === "boolean" ? data : Boolean(data?.is_background_mode);
      if (!isBg) {
        // System awakened from the backend: same cleanup as a wake asked for here.
        finishWakeUi(String(data?.reason ?? "backend_wake"));
      } else {
        sharedIsBackgroundMode = true;
        sharedBackgroundModeEnteredTime = Date.now();
        sharedShowHud = false;
        clearStandbySplash();
        if (Boolean(data?.standby)) {
          sharedStandbyMode = true;
        }
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

  // Backend asked for standby: draw the plugin mark first, then go dark
  try {
    standbyRequestUnregister = addEventListener("on_standby_requested", (data: any) => {
      console.log("[DownloadInBackground] on_standby_requested received:", data);
      if (sharedIsBackgroundMode) {
        return;
      }
      const seconds = Number(data?.splash_seconds ?? sharedSettings.hud_timeout_seconds ?? 5);
      startStandbySplash(seconds, String(data?.reason ?? "standby_splash"));
    });
  } catch (e) {
    console.warn("[DownloadInBackground] Could not register on_standby_requested listener:", e);
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
          finishWakeUi("status_poll_sync");
        } else {
          sharedIsBackgroundMode = backendIsBg;
        }

        sharedStandbyMode = Boolean(status.standby_mode);
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

  // Take over the power menu's Sleep before Steam starts suspending. SteamClient is not
  // always populated the moment a plugin loads, so this retries for a while.
  let suspendHookAttempts = 0;
  let suspendHookTimer: NodeJS.Timeout | null = null;
  const tryInstallSuspendHooks = () => {
    suspendHookTimer = null;
    let installed = 0;
    try {
      installed = installSuspendMethodHooks();
    } catch (e) {
      console.warn("[DownloadInBackground] Could not install suspend hooks:", e);
    }
    if (installed === 0 && ++suspendHookAttempts < 6) {
      suspendHookTimer = setTimeout(tryInstallSuspendHooks, 3000);
    }
  };
  tryInstallSuspendHooks();

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

        // 3. Plugin off: get out of the way immediately, no backend round-trip, so
        // SteamOS suspends with its own animation exactly as without this plugin.
        if (!sharedSettings.enabled) {
          return true;
        }

        // 4. This is also the hook for Sleep chosen from the SteamOS power menu, not
        // just the physical button. With standby on, that sleep becomes our mode.
        const looksIdle = !sharedDownloadInfo.is_downloading || sharedDownloadInfo.is_paused;
        if (looksIdle && !sharedSettings.standby_on_power_off) {
          console.log("[DownloadInBackground] No active download and standby off -> Allowing stock SteamOS suspend.");
          return true;
        }

        // 5. Confirm against the Steam client before taking the suspend over
        await querySteamDownloads();

        const isDownloading = Boolean(
          sharedDownloadInfo.is_downloading && !sharedDownloadInfo.is_paused
        );

        if (!isDownloading && sharedSettings.standby_on_power_off) {
          console.log("[DownloadInBackground] Sleep requested with standby enabled -> splash, then standby.");
          call("log_debug", {
            kind: "suspend_request",
            source: "RegisterForOnSuspendRequest",
            standby: true,
            download_info: sharedDownloadInfo,
          }).catch(() => {});
          startStandbySplash(sharedSettings.hud_timeout_seconds ?? 5, "standby_sleep_request");
          return false;
        }

        if (isDownloading) {
          console.log("[DownloadInBackground] Active download running -> Intercepting suspend and showing HUD");
          try {
            const res: any = await call("trigger_suspend_intercept");
            if (String(res?.verdict ?? "") === "allow") {
              // The backend re-read the state and found nothing running after all.
              console.log("[DownloadInBackground] Backend says idle -> allowing stock suspend.");
              return true;
            }
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

  /**
   * Writes the Steam client's own API surface into the plugin log, once.
   *
   * Blocking input and pacing a download would both be far cleaner done through Steam
   * itself than through the kernel, but which methods exist varies by Steam build, and
   * there is no documentation for them. This records what this console actually offers
   * (look for anything about controllers/input, or a download rate limit) so the next
   * version can call it directly instead of working around it.
   */
  const dumpSteamApiSurface = () => {
    const sc: any = (window as any).SteamClient;
    const keysOf = (obj: any): string[] | null => {
      if (!obj) return null;
      try {
        const proto = Object.getPrototypeOf(obj);
        const names = new Set<string>([
          ...Object.keys(obj),
          ...(proto ? Object.getOwnPropertyNames(proto) : []),
        ]);
        return Array.from(names).sort().slice(0, 400);
      } catch (e) {
        return ["<unreadable>"];
      }
    };
    const safeCall = (fn?: () => any) => {
      try {
        return fn ? fn() : null;
      } catch (e) {
        return null;
      }
    };

    call("log_debug", {
      kind: "steamclient_api_surface",
      top_level: keysOf(sc),
      Downloads: keysOf(sc?.Downloads),
      Settings: keysOf(sc?.Settings),
      Input: keysOf(sc?.Input),
      System: keysOf(sc?.System),
      download_overview: safeCall(sc?.Downloads?.GetDownloadOverview?.bind(sc?.Downloads)),
    }).catch(() => {});
  };

  const apiDumpTimer = setTimeout(() => {
    if (sharedSettings.debug_logging !== false) {
      dumpSteamApiSurface();
    }
  }, 8000);

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
      clearTimeout(apiDumpTimer);
      if (suspendHookTimer) {
        clearTimeout(suspendHookTimer);
        suspendHookTimer = null;
      }
      removeSuspendMethodHooks();
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
      if (standbyRequestUnregister) {
        try {
          removeEventListener("on_standby_requested", standbyRequestUnregister);
        } catch (e) {}
      }
      clearStandbySplash();
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
