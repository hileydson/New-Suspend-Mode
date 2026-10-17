export interface PluginSettings {
  enabled: boolean;
  min_battery_threshold: number; // default 15
  hud_timeout_seconds: number; // default 5
  auto_suspend_delay_seconds: number; // default 15
  throttle_cpu: boolean; // default true
  throttle_gpu: boolean; // default true
  mute_audio: boolean; // default true
  turn_off_backlight: boolean; // default true
  oled_black_screen: boolean; // default true
}

export interface DownloadInfo {
  is_downloading: boolean;
  is_paused?: boolean;
  app_id?: number | string;
  game_title?: string;
  bytes_per_second: number;
  total_bytes: number;
  completed_bytes: number;
  progress_percent: number;
  estimated_seconds_remaining?: number;
}

export interface SystemStatus {
  is_background_mode: boolean;
  battery_capacity: number;
  is_charging: boolean;
  power_plugged: boolean;
  inhibitor_active: boolean;
  backlight_saved: number | null;
  settings: PluginSettings;
  download_info: DownloadInfo;
}
