import { call, toaster } from "@decky/api";
import { Navigation } from "@decky/ui";
import {
  WAKE_COOLDOWN_MS,
  WAKE_FADE_MS,
  WAKE_PRESENTATION_MS,
  getState,
  refreshSubscribers,
  runtime,
  setState,
} from "./state";
import { WakePhase } from "./types";

let hudTimer: ReturnType<typeof setInterval> | null = null;
let splashTimer: ReturnType<typeof setTimeout> | null = null;
let wakePresentationTimer: ReturnType<typeof setTimeout> | null = null;
let wakeFadeTimer: ReturnType<typeof setTimeout> | null = null;

const stopHudTimer = () => {
  if (hudTimer) {
    clearInterval(hudTimer);
    hudTimer = null;
  }
};

const stopSplashTimer = () => {
  if (splashTimer) {
    clearTimeout(splashTimer);
    splashTimer = null;
  }
};

export const stopWakeTimers = () => {
  if (wakePresentationTimer) {
    clearTimeout(wakePresentationTimer);
    wakePresentationTimer = null;
  }
  if (wakeFadeTimer) {
    clearTimeout(wakeFadeTimer);
    wakeFadeTimer = null;
  }
};

/** Stops every countdown this module started. Called when the plugin unloads. */
export const stopFlowTimers = () => {
  stopHudTimer();
  stopSplashTimer();
  stopWakeTimers();
};

/** Drops the download card's countdown, leaving everything else as it is. */
export const cancelHudCountdown = () => {
  stopHudTimer();
};

/** Drops the standby splash and its pending entry into standby. */
export const clearStandbySplash = () => {
  stopSplashTimer();
  setState({ showSplash: false });
};

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
export const closeSteamSideMenus = () => {
  const close = () => {
    try {
      Navigation.CloseSideMenus?.();
    } catch (e) {}
  };
  close();
  [150, 400, 800, 1400, 2000, 2800, 3600].forEach((delay) => setTimeout(close, delay));
};

/**
 * Starts the 3-second wake splash presentation while the backend restores hardware
 * and runs the post-wake hard reset with controls still locked out.
 */
export const startWakePresentation = (reason: string) => {
  console.log(`[NewSuspendMode] Starting wake presentation (${reason}).`);
  runtime.wakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;
  stopSplashTimer();
  stopHudTimer();
  stopWakeTimers();
  setState({
    isBackgroundMode: false,
    showHud: false,
    standbyMode: false,
    showSplash: false,
    wakePhase: "restoring",
  });
  closeSteamSideMenus();

  // Safety fallback so a dropped backend event can never leave the splash up.
  wakePresentationTimer = setTimeout(() => {
    wakePresentationTimer = null;
    startWakeFadeOut(`${reason}_fallback`);
  }, WAKE_PRESENTATION_MS + 3500);
};

/**
 * Fades out the wake presentation just before native controls are handed back.
 */
export const startWakeFadeOut = (reason: string) => {
  runtime.wakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;
  stopSplashTimer();
  stopHudTimer();
  stopWakeTimers();
  setState({
    isBackgroundMode: false,
    showHud: false,
    standbyMode: false,
    showSplash: false,
    wakePhase: "fading",
  });

  wakeFadeTimer = setTimeout(() => {
    wakeFadeTimer = null;
    finishWakeUi(reason);
  }, WAKE_FADE_MS + 250);
};

/**
 * Everything the interface has to undo on wake, shared by both ways a wake arrives:
 * this side asking for it, and the backend announcing it already happened.
 */
export const finishWakeUi = (reason: string) => {
  console.log(`[NewSuspendMode] Waking the interface (${reason}).`);
  runtime.wakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;
  stopSplashTimer();
  stopHudTimer();
  stopWakeTimers();
  setState({
    isBackgroundMode: false,
    showHud: false,
    standbyMode: false,
    showSplash: false,
    wakePhase: "",
  });

  // Waking up is not left to a single render: the overlay is asked to check its state
  // again a moment later, so a late mount can never keep the black screen up.
  [120, 400, 1200].forEach((delay) => setTimeout(refreshSubscribers, delay));
  closeSteamSideMenus();
};

/**
 * Routes backend wake announcements through restoring -> fading -> ready.
 */
export const handleBackendWakeEvent = (reason: string, wakePhase?: WakePhase) => {
  if (wakePhase === "restoring") {
    startWakePresentation(reason);
  } else if (wakePhase === "fading") {
    startWakeFadeOut(reason);
  } else {
    finishWakeUi(reason);
  }
};

/**
 * Enters standby, replacing the HUD with nothing: the splash has already been shown.
 */
export const triggerEnterStandby = async (reason: string) => {
  if (getState().wakePhase || Date.now() < runtime.wakeCooldownUntil) {
    console.log("[NewSuspendMode] Wake cooldown active, not entering standby.");
    return;
  }
  stopHudTimer();
  stopSplashTimer();
  stopWakeTimers();
  runtime.backgroundModeEnteredTime = Date.now();
  setState({ showSplash: false, showHud: false, isBackgroundMode: true, standbyMode: true, wakePhase: "" });

  try {
    const success: any = await call("enter_background_mode", reason);
    if (success === false) {
      setState({ isBackgroundMode: false });
    }
  } catch (e) {
    console.error("[NewSuspendMode] Error entering standby:", e);
  }
};

/**
 * Shows the plugin mark, THEN enters standby a few seconds later.
 *
 * The order matters: the backlight is driven to zero as part of entering, so anything
 * drawn after that is invisible.
 */
export const startStandbySplash = (seconds: number, reason: string = "standby_splash") => {
  if (getState().isBackgroundMode || getState().wakePhase || Date.now() < runtime.wakeCooldownUntil) {
    return;
  }
  if (seconds <= 0) {
    triggerEnterStandby(reason);
    return;
  }
  stopHudTimer();
  stopSplashTimer();
  stopWakeTimers();
  setState({ showHud: false, showSplash: true, wakePhase: "" });

  splashTimer = setTimeout(() => {
    splashTimer = null;
    triggerEnterStandby(reason);
  }, seconds * 1000);
};

/**
 * A complete wake: drops the black screen or HUD, starts the cooldown against an
 * immediate re-sleep, then has the backend restore the hardware.
 */
export const triggerFullWake = async (reason: string = "wake") => {
  const wasInBackground = getState().isBackgroundMode;
  if (wasInBackground) {
    startWakePresentation(reason);
  } else {
    finishWakeUi(reason);
  }

  try {
    const exited: any = await call("exit_background_mode", reason);
    if (exited === false && wasInBackground) {
      finishWakeUi(reason);
    }
  } catch (e) {
    console.error("[NewSuspendMode] Error calling exit_background_mode:", e);
    finishWakeUi(reason);
  }

  toaster.toast({
    title: "New Suspend Mode",
    body: "Console awakened!",
    duration: 2000,
  });
};

/** Enters the black screen with the download carrying on in the background. */
export const triggerEnterBlackout = async (reason: string = "countdown_completed") => {
  if (getState().wakePhase || Date.now() < runtime.wakeCooldownUntil) {
    console.log("[NewSuspendMode] Wake cooldown active, blocking enter blackout.");
    return;
  }
  stopHudTimer();
  stopWakeTimers();
  runtime.backgroundModeEnteredTime = Date.now();
  setState({ showHud: false, isBackgroundMode: true, wakePhase: "" });

  try {
    const success: any = await call("enter_background_mode", reason);
    if (success === false) {
      // Backend rejected entry -> restore to normal
      setState({ isBackgroundMode: false });
    }
  } catch (e) {
    console.error("[NewSuspendMode] Error entering background mode:", e);
  }
};

/** Shows the download card with a countdown, then turns the screen black. */
export const startHudCountdown = (customTimeout?: number) => {
  if (getState().isBackgroundMode || getState().wakePhase || Date.now() < runtime.wakeCooldownUntil) {
    return;
  }

  const timeoutSec = customTimeout ?? getState().settings.hud_timeout_seconds ?? 5;
  if (timeoutSec <= 0) {
    triggerEnterBlackout("immediate");
    return;
  }

  stopHudTimer();
  setState({ countdown: timeoutSec, showHud: true, isBackgroundMode: false });

  let remaining = timeoutSec;
  hudTimer = setInterval(() => {
    remaining -= 1;
    setState({ countdown: remaining });

    if (remaining <= 0) {
      stopHudTimer();
      triggerEnterBlackout("countdown_completed");
    }
  }, 1000);
};

/** Our own black screen is up and a sleep is requested: that request is the way out. */
export const wakeIfSettled = (reason: string) => {
  if (Date.now() - runtime.backgroundModeEnteredTime >= 2000) {
    console.log(`[NewSuspendMode] Sleep requested while in our mode -> waking up (${reason}).`);
    triggerFullWake(reason);
  }
};
