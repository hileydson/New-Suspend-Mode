import { useSyncExternalStore } from "react";
import { call } from "@decky/api";
import { DownloadInfo, PluginSettings, WakePhase } from "./types";

export const DEFAULT_SETTINGS: PluginSettings = {
  enabled: false,
  enable_plugin_when_plugged_in: true,
  min_battery_threshold: 15,
  hud_timeout_seconds: 5,
  auto_suspend_delay_seconds: 120,
  pause_running_games: true,
  throttle_cpu: true,
  throttle_gpu: true,
  mute_audio: true,
  turn_off_backlight: true,
  oled_black_screen: true,
  tv_force_connector_off: false,
  deep_input_lockout: true,
  block_controller_hidraw: false,
  limit_download_speed: true,
  download_speed_limit_mbps: 6,
  download_cpu_percent: 30,
  debug_logging: true,
  auto_hard_reset_after_wake: true,
  enter_real_sleep_after_time: true,
  real_sleep_start_minutes: 0,     // 00:00
  real_sleep_end_minutes: 420,     // 07:00
  wake_at_period_end: true,
  standby_on_power_off: true,
  wake_on_bluetooth_connect: true,
  wake_on_controller_button: true,
  advanced_mode: false,
};

export const DEFAULT_DOWNLOAD_INFO: DownloadInfo = {
  is_downloading: false,
  bytes_per_second: 0,
  total_bytes: 0,
  completed_bytes: 0,
  progress_percent: 0,
  game_title: "Steam Game Download",
  estimated_seconds_remaining: 0,
};

// Must match WAKE_COOLDOWN_SECONDS in main.py: the window after a wake in which
// suspend requests are ignored, so the press that woke the console cannot re-sleep it.
export const WAKE_COOLDOWN_MS = 5000;
export const WAKE_PRESENTATION_MS = 3000;
export const WAKE_FADE_MS = 300;

/** Everything the overlay and the Quick Access panel are drawn from. */
export interface UiState {
  settings: PluginSettings;
  downloadInfo: DownloadInfo;
  batteryCapacity: number;
  isCharging: boolean;
  powerPlugged: boolean;
  isBackgroundMode: boolean;
  standbyMode: boolean;
  wakePhase: WakePhase;
  showHud: boolean;
  showSplash: boolean;
  countdown: number;
}

let state: UiState = {
  settings: { ...DEFAULT_SETTINGS },
  downloadInfo: { ...DEFAULT_DOWNLOAD_INFO },
  batteryCapacity: 100,
  isCharging: false,
  powerPlugged: false,
  isBackgroundMode: false,
  standbyMode: false,
  wakePhase: "",
  showHud: false,
  showSplash: false,
  countdown: 5,
};

const listeners = new Set<() => void>();

export const getState = (): UiState => state;

export const setState = (patch: Partial<UiState>) => {
  state = { ...state, ...patch };
  listeners.forEach((listener) => listener());
};

/**
 * Asks every component to check its state again without changing it.
 *
 * A component that already drew the current state does nothing. One that missed an
 * update - the overlay, say, if a wake landed while it was being mounted - redraws.
 */
export const refreshSubscribers = () => listeners.forEach((listener) => listener());

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};

/**
 * The state, for a component.
 *
 * useSyncExternalStore re-reads the state when it subscribes, so an update that arrives
 * between a component's first render and its subscription is never lost.
 */
export const useUiState = (): UiState => useSyncExternalStore(subscribe, getState);

/**
 * Timing state that nothing is drawn from, so changing it never re-renders anything.
 */
export const runtime = {
  backgroundModeEnteredTime: 0,
  wakeCooldownUntil: 0,
  /** A real suspend the plugin itself asked for: the sleep patches get out of the way. */
  realSuspendUntil: 0,
};

/**
 * Mirrors the backend's exclusive AC-only / always-on activation modes.
 */
export const isPluginEnabled = (s: UiState = state): boolean =>
  s.settings.enable_plugin_when_plugged_in === true
    ? s.powerPlugged
    : s.settings.enabled === true;

/** Writes a diagnostic entry into the plugin's own log file, when debug logging is on. */
export const debugLog = (payload: Record<string, unknown>) => {
  if (state.settings.debug_logging === false) return;
  call("log_debug", payload).catch(() => {});
};
