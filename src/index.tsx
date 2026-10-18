import React, { FC, useState, useEffect, useRef } from "react";
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
  ui_recovery_on_wake: true,
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

/**
 * True when the sleep came from the Steam interface (the power menu) rather than from
 * the physical power button. The button path is invisible to Steam and comes back clean;
 * the menu path is the one where Steam's own click handler has already touched the
 * interface before the plugin is consulted, so only it needs recovering afterwards.
 */
let sharedUiInitiatedSleep = false;
let sharedRecoveryTimers: NodeJS.Timeout[] = [];

const clearRecoveryTimers = () => {
  sharedRecoveryTimers.forEach((t) => clearTimeout(t));
  sharedRecoveryTimers = [];
};

/**
 * The window the interface is actually drawn in.
 *
 * A plugin's own module scope lives in Steam's SharedJSContext, which is a hidden 1x1
 * window - measuring `window` from here reports a viewport of 1x1 and a 2x2 document,
 * which is what the console's log finally showed. The global component Decky mounts is
 * rendered into the real interface window, so that is where a DOM reference to it points,
 * and that is the only window worth looking at.
 */
let sharedUiWindow: any = null;

const uiWindow = (): any => sharedUiWindow ?? window;
const uiDocument = (): any => (sharedUiWindow ? sharedUiWindow.document : document);

/**
 * What is in the middle of the screen, as a comparable string.
 *
 * Recorded before the sleep and again after the wake. Comparing the two is a far better
 * signal than trying to decide whether a colour counts as "black": if the middle of the
 * screen is the same thing it was before, the interface is where it was and nothing
 * needs recovering, whatever it looks like.
 */
const centerSignature = (): string => {
  try {
    const win = uiWindow();
    const el = uiDocument().elementFromPoint(
      Math.round(win.innerWidth / 2),
      Math.round(win.innerHeight / 2)
    ) as HTMLElement | null;
    if (!el) return "none";
    if (typeof el.closest === "function" && el.closest(".dib-overlay-container")) return "ours";
    const parent = el.parentElement;
    return [
      el.tagName,
      String((el as any).className ?? "").slice(0, 80),
      parent ? String((parent as any).className ?? "").slice(0, 80) : "",
    ].join("|");
  } catch (e) {
    return "error";
  }
};

/** Whether anything at all is readable in the middle of the screen. */
const centerHasContent = (): boolean => {
  try {
    const win = uiWindow();
    const el = uiDocument().elementFromPoint(
      Math.round(win.innerWidth / 2),
      Math.round(win.innerHeight / 2)
    ) as HTMLElement | null;
    let node: HTMLElement | null = el;
    for (let depth = 0; node && depth < 4; depth++) {
      if ((node.textContent ?? "").trim().length > 0) return true;
      node = node.parentElement;
    }
    return false;
  } catch (e) {
    return true; // Unreadable means "do not touch anything"
  }
};

/**
 * The last signature taken while the interface was known to be healthy.
 *
 * Sampled by the status poll rather than at the moment the sleep is taken over: by then
 * Steam's own click handler may already have blanked its interface, and comparing the
 * broken state against itself would find nothing wrong.
 */
let sharedCenterBeforeSleep: string | null = null;

/**
 * Takes the plugin's own black overlay off the screen, without going through React.
 *
 * This is what the console's log finally caught: after waking, the element covering the
 * middle of the screen was `dib-overlay-container dib-overlay-blackout` - the plugin's
 * own blackout, still in the document, at z-index 9999999, while the plugin's state said
 * it had woken up. The state is what React renders from, so if that component does not
 * re-render, the black stays on screen for good. The side menus still worked because
 * Steam drives them with its own input handling, not with DOM events, so they drew on
 * top of a screen the plugin was blacking out.
 *
 * Waking up is not something to leave to a re-render that may never come, so the node is
 * hidden directly as well. Hidden rather than removed: removing a node React still owns
 * makes React throw the next time it touches it.
 */
const forceHideOverlayDom = (): number => {
  let hidden = 0;
  const docs: any[] = [];
  try {
    docs.push(uiDocument());
  } catch (e) {}
  try {
    if (!docs.includes(document)) docs.push(document);
  } catch (e) {}

  for (const doc of docs) {
    try {
      const nodes = doc?.querySelectorAll?.(".dib-overlay-container");
      if (!nodes) continue;
      Array.prototype.forEach.call(nodes, (node: any) => {
        node.style.display = "none";
        node.style.pointerEvents = "none";
        hidden += 1;
      });
    } catch (e) {}
  }
  if (hidden) {
    console.warn(`[DownloadInBackground] Overlay was still in the DOM on wake; hid ${hidden} node(s).`);
  }
  return hidden;
};

/** Undoes the above, so the overlay can be shown again next time. */
const clearOverlayDomOverrides = () => {
  const docs: any[] = [];
  try {
    docs.push(uiDocument());
  } catch (e) {}
  try {
    if (!docs.includes(document)) docs.push(document);
  } catch (e) {}
  for (const doc of docs) {
    try {
      const nodes = doc?.querySelectorAll?.(".dib-overlay-container");
      if (!nodes) continue;
      Array.prototype.forEach.call(nodes, (node: any) => {
        node.style.display = "";
        node.style.pointerEvents = "";
      });
    } catch (e) {}
  }
};

/**
 * Catches "Sleep" in the SteamOS power menu before Steam's own handler runs.
 *
 * This is the whole point: the power button works because Steam never finds out about
 * it, so there is nothing for Steam to do to its interface and nothing to put back.
 * Catching the methods Steam calls at the END of its sleep handler is too late - by then
 * it has already done whatever leaves the screen black. Catching the activation of the
 * menu item itself, in the capture phase, means Steam's handler never runs at all and
 * the two paths become the same path.
 *
 * Identified by the item's own text, so it works whatever Steam calls its internals this
 * week. Only ever armed when the plugin would take the sleep over anyway, so when it is
 * off or idle the menu behaves exactly as it always has.
 */
const SLEEP_LABELS = new Set([
  "sleep", "suspend", "suspender", "suspensao", "modo de suspensao", "dormir",
  "reposo", "suspender equipo", "ruhezustand", "energie sparen", "standby",
  "veille", "mettre en veille", "mise en veille", "sospendi", "sospensione",
  "slaapstand", "vilolage", "vilolage", "hvile", "dvale", "lepotila", "viloläge",
  "uyku", "uspij", "uspienie", "spiaci rezim", "rezim spanku",
  "спящий режим", "сон", "スリープ", "睡眠", "절전", "휴면",
]);

const normalizeLabel = (text: string): string =>
  text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();

let menuGuardWindow: any = null;
let menuGuardHandler: ((e: any) => void) | null = null;
let lastMenuInterception = 0;
let activationsLogged = 0;

/**
 * The menu row under this event, if its text says it is the sleep entry.
 *
 * Runs on every click and key press while the plugin is armed, so it has to stay cheap:
 * reading `textContent` serializes an element's whole subtree, and `getBoundingClientRect`
 * forces the browser to lay the page out. Both are skipped unless the node is small
 * enough to be a menu row in the first place, and the rectangle is only measured once the
 * text has already matched.
 */
const sleepItemFromEvent = (target: any): { el: any; label: string } | null => {
  let node: any = target;
  for (let depth = 0; node && depth < 5; depth++) {
    try {
      // A menu row holds a label, not a page. Anything bigger is not worth reading.
      if ((node.childElementCount ?? 0) <= 4) {
        const raw = String(node.textContent ?? "");
        if (raw.length > 0 && raw.length <= 40) {
          const label = normalizeLabel(raw);
          if (SLEEP_LABELS.has(label)) {
            const rect = node.getBoundingClientRect?.();
            const win = uiWindow();
            if (!rect || (rect.height <= 200 && rect.width <= win.innerWidth * 0.7)) {
              return { el: node, label };
            }
          }
        }
      }
    } catch (e) {}
    node = node.parentElement;
  }
  return null;
};

/** Does exactly what the physical power button does, through the same backend call. */
const takeOverSleepFromMenu = (label: string) => {
  lastMenuInterception = Date.now();
  // Steam's handler never ran, so its interface was never touched and there is nothing
  // to recover afterwards - the same situation as a press of the power button.
  sharedUiInitiatedSleep = false;
  sharedRouteBeforeTakeover = null;
  clearTakeover();
  closeSteamSideMenus();
  call("log_debug", { kind: "menu_sleep_intercepted", label }).catch(() => {});
  call("request_standby", "standby_power_menu").catch((e) =>
    console.error("[DownloadInBackground] request_standby failed:", e)
  );
};

const installMenuItemGuard = (win: any) => {
  if (!win || win === menuGuardWindow) return;
  removeMenuItemGuard();

  menuGuardHandler = (e: any) => {
    try {
      if (e.type === "keydown" && (e.repeat || (e.key !== "Enter" && e.key !== " "))) return;
      if (!sharedSettings.enabled) return;
      if (sharedIsBackgroundMode || sharedShowSplash || sharedShowHud) return;
      if (Date.now() < sharedWakeCooldownUntil) return;
      if (Date.now() - lastMenuInterception < 2000) return;
      if (Date.now() < sharedRealSuspendUntil) return;

      // Only when the plugin would take this sleep over anyway.
      const downloading = sharedDownloadInfo.is_downloading && !sharedDownloadInfo.is_paused;
      if (!downloading && !sharedSettings.standby_on_power_off) return;

      const hit = sleepItemFromEvent(e.target);
      if (!hit) {
        if (activationsLogged < 8 && sharedSettings.debug_logging !== false) {
          activationsLogged += 1;
          const t = String(e.target?.textContent ?? "").slice(0, 60);
          call("log_debug", {
            kind: "activation_seen",
            event: e.type,
            text: t,
            cls: String(e.target?.className ?? "").slice(0, 80),
          }).catch(() => {});
        }
        return;
      }

      console.log(`[DownloadInBackground] Power menu "${hit.label}" caught before Steam saw it.`);
      e.stopImmediatePropagation();
      e.preventDefault();
      takeOverSleepFromMenu(hit.label);
    } catch (err) {
      console.error("[DownloadInBackground] Menu guard failed:", err);
    }
  };

  ["click", "keydown"].forEach((type) => {
    try {
      win.addEventListener(type, menuGuardHandler, true);
    } catch (e) {}
  });
  menuGuardWindow = win;
  console.log("[DownloadInBackground] Power menu guard installed on the interface window.");
};

const removeMenuItemGuard = () => {
  if (!menuGuardWindow || !menuGuardHandler) return;
  ["click", "keydown"].forEach((type) => {
    try {
      menuGuardWindow.removeEventListener(type, menuGuardHandler, true);
    } catch (e) {}
  });
  menuGuardWindow = null;
  menuGuardHandler = null;
};

/** How many of the plugin's overlay nodes are in the document right now. */
const overlayNodesInDom = (): number => {
  try {
    return uiDocument()?.querySelectorAll?.(".dib-overlay-container")?.length ?? 0;
  } catch (e) {
    return 0;
  }
};

let lastCenterSample = 0;

const sampleHealthyCenter = () => {
  if (sharedIsBackgroundMode || sharedShowSplash || sharedShowHud) return;
  // elementFromPoint forces a layout, so this is kept well away from the poll cadence.
  if (Date.now() - lastCenterSample < 10000) return;
  lastCenterSample = Date.now();
  const sig = centerSignature();
  if (sig === "ours" || sig === "none" || sig === "error") return;
  sharedCenterBeforeSleep = sig;
};

/**
 * Tells the Steam client its suspend was called off, if it has a way to be told.
 *
 * Returning false from the suspend-request callback stops the suspend, but it does not
 * appear to walk Steam's own interface back out of the state it entered when it decided
 * to sleep - which is why a sleep started from the power menu comes back to a blank
 * screen while the power button, which Steam never hears about, comes back clean.
 *
 * Which method does that is not documented and differs between Steam builds, so this
 * looks for one whose name can only mean that, calls it, and records what it found. A
 * name has to mention cancelling or aborting AND suspending or sleeping to be called.
 */
const cancelSteamSuspendFlow = (request?: any): string[] => {
  const called: string[] = [];
  const tried: string[] = [];
  const wanted = /^(?=.*(cancel|abort))(?=.*(suspend|sleep)).*$/i;

  const methodNames = (obj: any): string[] => {
    if (!obj) return [];
    try {
      const proto = Object.getPrototypeOf(obj);
      return Array.from(
        new Set([...Object.keys(obj), ...(proto ? Object.getOwnPropertyNames(proto) : [])])
      );
    } catch (e) {
      return [];
    }
  };

  // 1. The request object the callback is handed, if this build hands one over. A
  // cancel on the request itself is the most likely intended way to refuse.
  if (request && typeof request === "object") {
    for (const name of methodNames(request)) {
      if (typeof request[name] !== "function") continue;
      tried.push(`request.${name}`);
      if (!/^(cancel|abort|block|deny|reject|veto)/i.test(name)) continue;
      try {
        request[name]();
        called.push(`request.${name}`);
      } catch (e) {}
    }
  }

  // 2. A client-level "the suspend was cancelled" call.
  const sc: any = (window as any).SteamClient;
  for (const group of ["System", "User", "UI"]) {
    for (const name of methodNames(sc?.[group])) {
      if (!wanted.test(name) || typeof sc[group][name] !== "function") continue;
      try {
        sc[group][name]();
        called.push(`${group}.${name}`);
      } catch (e) {}
    }
  }

  call("log_debug", {
    kind: "suspend_cancel_attempt",
    called,
    request_type: typeof request,
    request_members: request && typeof request === "object" ? tried : null,
    system: methodNames(sc?.System).filter((n) => /susp|sleep|resume|power/i.test(n)),
    user: methodNames(sc?.User).filter((n) => /susp|sleep|resume|power/i.test(n)),
    ui: methodNames(sc?.UI).filter((n) => /susp|sleep|resume|power|mode/i.test(n)),
  }).catch(() => {});

  if (called.length) {
    console.log(`[DownloadInBackground] Told Steam its suspend was cancelled via: ${called.join(", ")}`);
  }
  return called;
};

/**
 * Gets the Steam interface back after a sleep it started itself.
 *
 * Three steps, each only taken if the one before it did not help, because the screen
 * being black is the only evidence available and every step costs the user something:
 *   1. nothing (the ordinary wake already closed the menus and put the route back)
 *   2. navigate home, which remounts the main view
 *   3. reload the Steam interface, the last resort, and still far better than the reboot
 *      that is otherwise the only way out.
 */
const recoverSteamUi = () => {
  clearRecoveryTimers();
  if (!sharedUiInitiatedSleep || sharedSettings.ui_recovery_on_wake === false) {
    sharedUiInitiatedSleep = false;
    return;
  }

  const before = sharedCenterBeforeSleep;
  sharedRecoveryTimers.push(
    setTimeout(() => {
      // Our own overlay first: it is the cheapest and most precise thing to rule out,
      // and it was the actual cause of the black screen all along.
      if (overlayNodesInDom() > 0 && forceHideOverlayDom() > 0) {
        call("log_debug", { kind: "ui_recovery", step: "hid_stale_overlay" }).catch(() => {});
      }
      const after = centerSignature();
      // Unchanged middle of the screen means the interface is where it was.
      if (sharedIsBackgroundMode || (before && after === before)) {
        sharedUiInitiatedSleep = false;
        return;
      }
      console.warn(
        `[DownloadInBackground] Screen changed across the sleep (${before} -> ${after}) -> navigating home.`
      );
      call("log_debug", {
        kind: "ui_recovery", step: "navigate_home", before, after,
        has_content: centerHasContent(),
      }).catch(() => {});
      try {
        const nav: any = Navigation as any;
        if (typeof nav.NavigateToLibraryTab === "function") nav.NavigateToLibraryTab();
        else nav.Navigate?.("/library/home");
      } catch (e) {
        console.warn("[DownloadInBackground] Could not navigate home:", e);
      }

      sharedRecoveryTimers.push(
        setTimeout(() => {
          sharedUiInitiatedSleep = false;
          sharedCenterBeforeSleep = null;
          // The last resort needs two independent reasons to believe the interface is
          // broken: the middle of the screen is not what it was, AND there is nothing
          // readable there. A view that merely moved on still has content in it.
          if (sharedIsBackgroundMode) return;
          const after = centerSignature();
          if (before && after === before) return;
          if (centerHasContent()) {
            call("log_debug", {
              kind: "ui_recovery", step: "skipped_reload", before, after, reason: "screen has content",
            }).catch(() => {});
            return;
          }
          const restart = (window as any).SteamClient?.Browser?.RestartJSContext;
          console.warn("[DownloadInBackground] Screen STILL empty -> reloading the Steam UI.");
          call("log_debug", {
            kind: "ui_recovery",
            step: "restart_js_context",
            before,
            after,
            available: typeof restart === "function",
          }).catch(() => {});
          if (typeof restart !== "function") return;
          toaster.toast({
            title: "Download in Background",
            body: "Reloading the Steam interface to finish waking up",
            duration: 3000,
          });
          try {
            restart();
          } catch (e) {
            console.error("[DownloadInBackground] Could not reload the Steam UI:", e);
          }
        }, 2500)
      );
    }, 1500)
  );
};

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
    const win = uiWindow();
    const doc = uiDocument();
    const samples = points.map(([fx, fy]) => {
      const x = Math.round(win.innerWidth * fx);
      const y = Math.round(win.innerHeight * fy);
      const chain: any[] = [];
      let node = doc.elementFromPoint(x, y) as HTMLElement | null;
      for (let depth = 0; node && depth < 5; depth++) {
        const cs = win.getComputedStyle(node);
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
      visibility: doc.visibilityState,
      hidden: doc.hidden,
      viewport: [win.innerWidth, win.innerHeight],
      ui_window: sharedUiWindow ? "interface" : "shared_context_fallback",
      overlay_in_dom: overlayNodesInDom(),
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
  const steamWasInvolved = sharedUiInitiatedSleep;
  sharedIsBackgroundMode = false;
  sharedShowHud = false;
  sharedStandbyMode = false;
  sharedWakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;
  clearStandbySplash();
  clearTakeover();

  // If this sleep came from the Steam interface, Steam prepared for a suspend that never
  // happened. This is the call it would have made itself on a real resume.
  if (steamWasInvolved) {
    resumeSteamFromPreparedSuspend();
  }
  if (sharedHudTimer) {
    clearInterval(sharedHudTimer);
    sharedHudTimer = null;
  }

  // Unmounts the overlay from the DOM before anything else is attempted...
  notifyStateListeners();
  // ...and then makes sure it is actually gone, whether or not React obliged. Repeated,
  // because a component that re-renders late can put it back on screen.
  forceHideOverlayDom();
  // Not tracked with the recovery timers on purpose: those are cleared further down.
  [120, 400, 1200].forEach((delay) =>
    setTimeout(() => {
      if (!sharedIsBackgroundMode && !sharedShowHud && !sharedShowSplash) {
        forceHideOverlayDom();
      }
    }, delay)
  );
  closeSteamSideMenus();

  // Records what is on screen while it is still wrong, then puts the interface back
  // where it was if Steam's own sleep handler moved it.
  probeWakeScreen(reason);
  restoreUiRoute();

  // A nudge for anything that stopped repainting while the screen was off.
  try {
    uiWindow().dispatchEvent(new Event("resize"));
  } catch (e) {}

  // Only for a sleep the Steam interface started itself, and only if it is still blank.
  recoverSteamUi();
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
  clearOverlayDomOverrides();  // The wake hides the overlay node by hand; undo that first
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
  clearOverlayDomOverrides();
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
  clearOverlayDomOverrides();
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
  clearOverlayDomOverrides();
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
  // The one that actually puts the console to sleep.
  ["System", "SuspendPC"],
  ["System", "Suspend"],
  // And the one that runs FIRST. This is what the console's log finally showed: the
  // power menu calls User.PrepareForSystemSuspend() before SuspendPC(), and that call is
  // where Steam suspends the running games and moves its interface into its sleeping
  // state. Swallowing only SuspendPC stopped the suspend but left Steam prepared for one
  // that never happened, with nothing to undo it - the interface came back half dead.
  // The power button never goes through any of this, which is why it always came back clean.
  ["User", "PrepareForSystemSuspend"],
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
 * The sleep currently being decided on.
 *
 * One sleep arrives as several calls (prepare, then suspend), so the decision is made
 * once and the rest of the calls follow it. While the backend is being asked, the calls
 * are held: if the answer turns out to be "not ours", every held call is let through in
 * the order Steam made it, so SteamOS sleeps exactly as it would have.
 */
interface SleepTakeover {
  state: "deciding" | "ours" | "none";
  held: Array<{ hook: SuspendHook; args: any[] }>;
  expires: number;
}
let sharedTakeover: SleepTakeover | null = null;

/** A real suspend the plugin itself asked for: every hook gets out of the way. */
let sharedRealSuspendUntil = 0;

const clearTakeover = () => {
  sharedTakeover = null;
};

const activeTakeover = (): SleepTakeover | null => {
  if (sharedTakeover && Date.now() > sharedTakeover.expires) {
    // A decision that never came back must never swallow sleeps forever.
    console.warn("[DownloadInBackground] Sleep decision timed out; forgetting it.");
    sharedTakeover = null;
  }
  return sharedTakeover;
};

/**
 * Undoes Steam's own preparation for a sleep that is not going to happen.
 *
 * ResumeSuspendedGames is the exact counterpart of PrepareForSystemSuspend, and it is
 * what Steam itself calls on a real resume. Harmless when nothing was suspended.
 */
const resumeSteamFromPreparedSuspend = () => {
  const user: any = (window as any).SteamClient?.User;
  if (typeof user?.ResumeSuspendedGames !== "function") return false;
  try {
    user.ResumeSuspendedGames();
    console.log("[DownloadInBackground] Called User.ResumeSuspendedGames() to undo Steam's sleep preparation.");
    return true;
  } catch (e) {
    console.warn("[DownloadInBackground] ResumeSuspendedGames failed:", e);
    return false;
  }
};

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
  // Logged on every single call, before any decision. Whether these hooks fire at all
  // for a sleep chosen in the power menu is the one thing the log could never answer,
  // and it decides where the fix has to go: if nothing appears here, the sleep is not
  // going through the Steam client methods this plugin wraps.
  call("log_debug", {
    kind: "sleep_hook_fired",
    method: hook.name,
    pass_through: suspendPassThrough,
    enabled: sharedSettings.enabled,
    in_background: sharedIsBackgroundMode,
    takeover: sharedTakeover?.state ?? null,
    standby: sharedSettings.standby_on_power_off,
    downloading: sharedDownloadInfo.is_downloading,
    paused: sharedDownloadInfo.is_paused,
  }).catch(() => {});

  // Our own pass-through, a real suspend the plugin asked for, or the plugin is off.
  if (suspendPassThrough || !sharedSettings.enabled || Date.now() < sharedRealSuspendUntil) {
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

  // One sleep, several calls: prepare and suspend both land here, and they must not be
  // decided on separately.
  const pending = activeTakeover();
  if (pending) {
    if (pending.state === "deciding") {
      pending.held.push({ hook, args });
      return Promise.resolve();
    }
    if (pending.state === "ours") {
      return Promise.resolve();
    }
    return callOriginalSuspend(hook, args);
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

  // Taking this sleep over. Everything Steam asks for from here on is held until the
  // answer comes back, so the preparation never runs behind our back.
  sharedTakeover = { state: "deciding", held: [{ hook, args }], expires: Date.now() + 15000 };

  // Remember where the interface was, and dismiss the power menu that is still open.
  // Steam's own suspend flow would have taken it down; the power-button path, which
  // comes back clean, never has a menu open in the first place.
  sharedRouteBeforeTakeover = currentUiRoute();
  sharedUiInitiatedSleep = true;
  closeSteamSideMenus();
  // If Steam already prepared for the sleep before calling us, undo that preparation:
  // nothing else ever will, because the suspend it was preparing for is not happening.
  cancelSteamSuspendFlow();
  resumeSteamFromPreparedSuspend();

  // The backend decides, on state it re-reads right now rather than on the last poll,
  // and starts the standby splash itself when standby is what takes over.
  console.log(`[DownloadInBackground] Power menu sleep (${hook.name}) -> asking the backend.`);
  call("trigger_suspend_intercept")
    .then((res: any) => {
      const verdict = String(res?.verdict ?? "");
      console.log(`[DownloadInBackground] Power menu sleep verdict: ${verdict}`);
      if (verdict === "allow") {
        releaseHeldSleep();
      } else {
        // Only long enough to cover the follow-up calls of this same sleep. Any longer
        // and a second attempt - after cancelling the countdown, say - would be
        // swallowed in silence instead of being decided on again.
        if (sharedTakeover) {
          sharedTakeover.state = "ours";
          sharedTakeover.expires = Date.now() + 3000;
        }
        if (verdict === "hud") {
          startHudCountdown(sharedSettings.hud_timeout_seconds ?? 5);
        }
      }
    })
    .catch((e) => {
      console.error("[DownloadInBackground] trigger_suspend_intercept failed:", e);
      releaseHeldSleep();
    });
  return Promise.resolve();
};

/**
 * Not ours after all: let SteamOS have the whole sleep, in the order Steam asked for it,
 * so the preparation still happens before the suspend.
 */
const releaseHeldSleep = () => {
  const held = sharedTakeover?.held ?? [];
  sharedTakeover = { state: "none", held: [], expires: Date.now() + 3000 };
  sharedRouteBeforeTakeover = null;
  sharedUiInitiatedSleep = false;
  held.forEach(({ hook, args }) => callOriginalSuspend(hook, args));
  setTimeout(clearTakeover, 2000);
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
  const probeRef = useRef<HTMLDivElement | null>(null);

  // Rendered in every state, including idle, so the plugin always has a reference into
  // the window the interface is really drawn in. Without it everything this plugin
  // measures about the screen describes Steam's hidden 1x1 scratch window instead.
  useEffect(() => {
    const win: any = probeRef.current?.ownerDocument?.defaultView;
    if (!win) return;
    if (!sharedUiWindow || (win.innerWidth ?? 0) > (sharedUiWindow.innerWidth ?? 0)) {
      sharedUiWindow = win;
    }
    installMenuItemGuard(sharedUiWindow);
  });

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
    return <div ref={probeRef} style={{ display: "none" }} />;
  }

  return (
    <>
      <div ref={probeRef} style={{ display: "none" }} />
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
      // A suspend the plugin itself asked for: Steam must be allowed to prepare for it.
      sharedRealSuspendUntil = Date.now() + 60000;
      clearTakeover();
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
      // Also a real suspend: let Steam suspend its games properly on the way down.
      sharedRealSuspendUntil = Date.now() + 60000;
      clearTakeover();
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

        // Keep a picture of the interface while it is still working, for the recovery
        // check after a wake.
        sampleHealthyCenter();

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
      const reg = window.SteamClient.System.RegisterForOnSuspendRequest(async (request?: any) => {
        console.log("[DownloadInBackground] SteamClient Suspend Request event received!", request);
        call("log_debug", {
          kind: "suspend_request_fired",
          in_background: sharedIsBackgroundMode,
          enabled: sharedSettings.enabled,
          standby: sharedSettings.standby_on_power_off,
          request_type: typeof request,
        }).catch(() => {});
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
          // Steam asked, so Steam may already have touched its own interface.
          sharedRouteBeforeTakeover = currentUiRoute();
          sharedUiInitiatedSleep = true;
          cancelSteamSuspendFlow(request);
          resumeSteamFromPreparedSuspend();
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
          sharedRouteBeforeTakeover = currentUiRoute();
          sharedUiInitiatedSleep = true;
          cancelSteamSuspendFlow(request);
          resumeSteamFromPreparedSuspend();
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

    // Every namespace, not a filtered slice: the one call that puts Steam's interface
    // back on screen has to be in here somewhere, and guessing at names has not worked.
    const namespaces: Record<string, string[] | null> = {};
    for (const name of keysOf(sc) ?? []) {
      try {
        const value = (sc as any)[name];
        if (value && typeof value === "object") {
          namespaces[name] = keysOf(value);
        }
      } catch (e) {}
    }

    call("log_debug", {
      kind: "steamclient_api_surface",
      top_level: keysOf(sc),
      namespaces,
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
      removeMenuItemGuard();
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
