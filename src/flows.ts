import { call, toaster } from "@decky/api";
import { Navigation } from "@decky/ui";
import { WAKE_COOLDOWN_MS, getState, refreshSubscribers, runtime, setState } from "./state";

let hudTimer: ReturnType<typeof setInterval> | null = null;
let splashTimer: ReturnType<typeof setTimeout> | null = null;

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

/** Stops every countdown this module started. Called when the plugin unloads. */
export const stopFlowTimers = () => {
  stopHudTimer();
  stopSplashTimer();
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
 * Everything the interface has to undo on wake, shared by both ways a wake arrives:
 * this side asking for it, and the backend announcing it already happened.
 */
export const finishWakeUi = (reason: string) => {
  console.log(`[NewSuspendMode] Waking the interface (${reason}).`);
  runtime.wakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;
  stopSplashTimer();
  stopHudTimer();
  setState({ isBackgroundMode: false, showHud: false, standbyMode: false, showSplash: false });

  // Waking up is not left to a single render: the overlay is asked to check its state
  // again a moment later, so a late mount can never keep the black screen up.
  [120, 400, 1200].forEach((delay) => setTimeout(refreshSubscribers, delay));
  closeSteamSideMenus();
};

/**
 * Enters standby, replacing the HUD with nothing: the splash has already been shown.
 */
export const triggerEnterStandby = async (reason: string) => {
  if (Date.now() < runtime.wakeCooldownUntil) {
    console.log("[NewSuspendMode] Wake cooldown active, not entering standby.");
    return;
  }
  stopHudTimer();
  stopSplashTimer();
  runtime.backgroundModeEnteredTime = Date.now();
  setState({ showSplash: false, showHud: false, isBackgroundMode: true, standbyMode: true });

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
  if (getState().isBackgroundMode || Date.now() < runtime.wakeCooldownUntil) {
    return;
  }
  if (seconds <= 0) {
    triggerEnterStandby(reason);
    return;
  }
  stopHudTimer();
  stopSplashTimer();
  setState({ showHud: false, showSplash: true });

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
  finishWakeUi(reason);

  try {
    await call("exit_background_mode", reason);
  } catch (e) {
    console.error("[NewSuspendMode] Error calling exit_background_mode:", e);
  }

  toaster.toast({
    title: "New Suspend Mode",
    body: "Console awakened!",
    duration: 2000,
  });
};

/** Enters the black screen with the download carrying on in the background. */
export const triggerEnterBlackout = async (reason: string = "countdown_completed") => {
  if (Date.now() < runtime.wakeCooldownUntil) {
    console.log("[NewSuspendMode] Wake cooldown active, blocking enter blackout.");
    return;
  }
  stopHudTimer();
  runtime.backgroundModeEnteredTime = Date.now();
  setState({ showHud: false, isBackgroundMode: true });

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
  if (getState().isBackgroundMode || Date.now() < runtime.wakeCooldownUntil) {
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
