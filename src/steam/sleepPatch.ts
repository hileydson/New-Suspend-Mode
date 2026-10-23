import { call } from "@decky/api";
import { Patch, callOriginal, findModuleExport, replacePatch } from "@decky/ui";
import { debugLog, getState, runtime } from "../state";
import { closeSteamSideMenus, startHudCountdown, wakeIfSettled } from "../flows";

/**
 * Takes over Sleep inside the Steam client's own suspend store.
 *
 * Steam runs every sleep through one store (window.SuspendResumeStore):
 *
 *   power menu "Sleep" -> RequestSleep() -> SleepManager -> OnRequestSuspend()
 *     -> InitiateSleep() -> OnSuspendRequest(): sets `suspending`, then
 *        PrepareForSystemSuspend(), then SuspendPC()
 *
 * The moment `suspending` is set, Steam mounts its suspend dialog over the whole
 * interface, and only a real resume takes it down again. So the sleep is taken over
 * before that point: RequestSleep is the power menu's own entry, and InitiateSleep is
 * where every other sleep request (idle timer, Steam's own dialogs) arrives. Neither is
 * a MobX action, so they can be replaced on the instance.
 *
 * When the plugin has no business with a sleep, the original method runs and SteamOS
 * sleeps exactly as it does without this plugin. When the store cannot be found (a
 * Steam build that reorganised it), nothing is patched and Sleep stays stock; the
 * physical power button is handled by the backend either way.
 */

const isSuspendStore = (candidate: any): boolean =>
  typeof candidate?.RequestSleep === "function" &&
  typeof candidate?.InitiateSleep === "function" &&
  typeof candidate?.OnSuspendRequest === "function";

const findSuspendStore = (): any => {
  const global = (window as any).SuspendResumeStore;
  if (isSuspendStore(global)) return global;
  try {
    return findModuleExport((e: any) => isSuspendStore(e)) ?? null;
  } catch (e) {
    return null;
  }
};

let patches: Patch[] = [];

/** One sleep the backend is still deciding on, so a repeat of it is not decided twice. */
let decidingUntil = 0;
/** The last sleep taken over, so the repeats of that same sleep are swallowed. */
let lastTakeover = 0;

const isDownloading = (): boolean => {
  const info = getState().downloadInfo;
  return Boolean(info.is_downloading && !info.is_paused);
};

/** Whether the plugin would turn this sleep into its own mode at all. */
const pluginWantsSleep = (): boolean =>
  isDownloading() || getState().settings.standby_on_power_off === true;

/**
 * What every request does before anything is decided: get out of the way, be the way
 * out of our own mode, or be swallowed because a takeover is already under way.
 * Returns undefined when the request still has to be decided on.
 */
const preflight = (via: string): "original" | "handled" | undefined => {
  const s = getState();
  // AC may have changed since the last status poll. Let the backend decide
  // AC-only requests using a fresh power reading, even if the cached state is off.
  if (Date.now() < runtime.realSuspendUntil ||
      (!s.settings.enabled && !s.settings.enable_plugin_when_plugged_in)) {
    return "original";
  }
  if (s.isBackgroundMode) {
    wakeIfSettled(`${via}_wake`);
    return "handled";
  }
  const now = Date.now();
  if (
    s.showSplash ||
    s.showHud ||
    Boolean(s.wakePhase) ||
    now < runtime.wakeCooldownUntil ||
    now < decidingUntil ||
    now - lastTakeover < 2000
  ) {
    return "handled";
  }
  if (!pluginWantsSleep()) {
    return "original";
  }
  return undefined;
};

/**
 * Sleep chosen in the power menu: does exactly what the physical power button does,
 * through the same backend call.
 */
const runOriginalSleep = (store: any, method: string, args: any[]) => {
  try {
    const original = patches.find((p) => p.property === method)?.original ?? store[method];
    original.apply(store, args);
  } catch (e) {
    console.error("[NewSuspendMode] Could not hand the sleep back to Steam:", e);
  }
};

const onRequestSleep = (store: any, args: any[]): any => {
  const pre = preflight("menu_suspend");
  debugLog({ kind: "sleep_request", via: "RequestSleep", decision: pre ?? "takeover" });
  if (pre === "original") return callOriginal;
  if (pre === "handled") return undefined;

  decidingUntil = Date.now() + 15000;
  closeSteamSideMenus();
  call("request_menu_sleep")
    .then((res: any) => {
      decidingUntil = 0;
      if (res?.verdict === "allow") {
        runOriginalSleep(store, "RequestSleep", args);
        return;
      }
      lastTakeover = Date.now();
      if (res?.verdict === "hud") {
        startHudCountdown(getState().settings.hud_timeout_seconds ?? 5);
      }
    })
    .catch((e) => {
      decidingUntil = 0;
      console.error("[NewSuspendMode] request_menu_sleep failed:", e);
      runOriginalSleep(store, "RequestSleep", args);
    });
  return undefined;
};

/**
 * Every other sleep request. The backend decides on the state it re-reads right now:
 * 'allow' hands the sleep back to Steam, 'hud' shows the download card, and for
 * 'standby' the backend starts the splash itself.
 */
const onInitiateSleep = (store: any, args: any[]): any => {
  // suppress_actual_suspend: Steam is only preparing for a suspend that the system is
  // already carrying out, and will not suspend anything itself.
  if (args[0] === true) return callOriginal;

  const pre = preflight("initiate_sleep");
  debugLog({ kind: "sleep_request", via: "InitiateSleep", decision: pre ?? "takeover" });
  if (pre === "original") return callOriginal;
  if (pre === "handled") return undefined;

  // The patch's original when it is still in place; the store's own method once the
  // plugin has been unloaded and the patch taken off.
  const runOriginal = () => runOriginalSleep(store, "InitiateSleep", args);

  decidingUntil = Date.now() + 15000;
  closeSteamSideMenus();
  call("trigger_suspend_intercept")
    .then((res: any) => {
      decidingUntil = 0;
      const verdict = String(res?.verdict ?? "");
      console.log(`[NewSuspendMode] Sleep verdict: ${verdict}`);
      if (verdict === "allow") {
        runOriginal();
        return;
      }
      lastTakeover = Date.now();
      if (verdict === "hud") {
        startHudCountdown(getState().settings.hud_timeout_seconds ?? 5);
      }
    })
    .catch((e) => {
      decidingUntil = 0;
      console.error("[NewSuspendMode] trigger_suspend_intercept failed:", e);
      runOriginal();
    });
  return undefined;
};

const tryInstall = (): boolean => {
  const store = findSuspendStore();
  if (!store) return false;

  // Whatever goes wrong in here, the console must still be able to sleep.
  const guarded = (handler: (args: any[]) => any) => (args: any[]) => {
    try {
      return handler(args);
    } catch (e) {
      console.error("[NewSuspendMode] Sleep patch failed, falling back to SteamOS:", e);
      return callOriginal;
    }
  };

  patches = [
    replacePatch(store, "RequestSleep", guarded((args) => onRequestSleep(store, args))),
    replacePatch(store, "InitiateSleep", guarded((args) => onInitiateSleep(store, args))),
  ];
  console.log("[NewSuspendMode] Sleep patched on the Steam suspend store.");
  return true;
};

/**
 * Patches the suspend store, retrying for a while in case it is not there yet.
 * Returns the function that takes the patches off again.
 */
export const installSleepPatch = (): (() => void) => {
  let attempts = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const attempt = () => {
    timer = null;
    let installed = false;
    try {
      installed = tryInstall();
    } catch (e) {
      console.warn("[NewSuspendMode] Could not patch the Steam suspend store:", e);
    }
    if (installed) {
      debugLog({ kind: "sleep_patch", installed: true, attempts: attempts + 1 });
      return;
    }
    if (++attempts < 6) {
      timer = setTimeout(attempt, 3000);
    } else {
      console.warn("[NewSuspendMode] Steam suspend store not found; Sleep stays stock.");
      debugLog({ kind: "sleep_patch", installed: false, attempts });
    }
  };
  attempt();

  return () => {
    if (timer) clearTimeout(timer);
    for (const patch of patches) {
      try {
        patch.unpatch();
      } catch (e) {}
    }
    patches = [];
  };
};
