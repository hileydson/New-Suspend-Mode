export interface PluginSettings {
  enabled: boolean;
  min_battery_threshold: number; // default 15
  hud_timeout_seconds: number; // default 5
  auto_suspend_delay_seconds: number; // default 120
  throttle_cpu: boolean; // default true
  throttle_gpu: boolean; // default true
  mute_audio: boolean; // default true
  turn_off_backlight: boolean; // default true
  oled_black_screen: boolean; // default true
  deep_input_lockout: boolean; // default true
  block_controller_hidraw: boolean; // default false (experimental escalation)
  limit_download_speed: boolean; // default true
  download_speed_limit_mbps: number; // MB/s, default 6
  download_cpu_percent: number; // % of one CPU core, default 30
  debug_logging: boolean; // default true
  standby_on_power_off: boolean; // default false
  wake_on_bluetooth_connect: boolean; // default true
  wake_on_controller_button: boolean; // default true
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
  standby_mode?: boolean;
  battery_capacity: number;
  is_charging: boolean;
  power_plugged: boolean;
  inhibitor_active: boolean;
  plugin_active?: boolean;
  backlight_saved?: number | null;
  settings: PluginSettings;
  download_info: DownloadInfo;
}
