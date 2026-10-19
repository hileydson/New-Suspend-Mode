import React, { FC } from "react";
import { FaDownload, FaMoon, FaBatteryThreeQuarters, FaTimes, FaBolt } from "react-icons/fa";
import { DownloadInfo, PluginSettings } from "../types";

export interface OverlayProps {
  isBackgroundMode: boolean;
  showHud: boolean;
  showSplash?: boolean;
  countdown: number;
  downloadInfo: DownloadInfo;
  settings: PluginSettings;
  batteryCapacity: number;
  isCharging: boolean;
  onWake: () => void;
  onEnterBlackout: () => void;
}

export const Overlay: FC<OverlayProps> = ({
  isBackgroundMode,
  showHud,
  showSplash,
  countdown,
  downloadInfo,
  settings,
  batteryCapacity,
  isCharging,
  onWake,
  onEnterBlackout,
}) => {
  // If nothing is active, do not render anything
  if (!showHud && !isBackgroundMode && !showSplash) {
    return null;
  }

  // Pure black screen mode (hardware power button, or a controller, is the wake trigger)
  if (isBackgroundMode) {
    return (
      <div
        className="nsm-overlay-container nsm-overlay-blackout"
        tabIndex={-1}
        aria-hidden="true"
      />
    );
  }

  // Standby splash: shown while the panel is still lit, just before the screen goes
  // dark. Takes the place of the download card when there is no download to report.
  if (showSplash) {
    return (
      <div className="nsm-overlay-container nsm-overlay-splash" tabIndex={-1} aria-hidden="true">
        <div className="nsm-splash">
          <FaDownload className="nsm-splash-icon" />
          <div className="nsm-splash-title">New Suspend Mode</div>
          <div className="nsm-splash-subtitle">
            Press POWER or use a controller to wake
          </div>
        </div>
      </div>
    );
  }

  // Download HUD Mode (Countdown before screen off)
  const percent = Math.min(100, Math.max(0, downloadInfo.progress_percent || 0));
  const gameTitle = downloadInfo.game_title || "Steam Game Download";

  const formatSpeed = (bytesPerSec: number): string => {
    if (!bytesPerSec || bytesPerSec <= 0) return "0 KB/s";
    const mb = bytesPerSec / (1024 * 1024);
    if (mb >= 1) return `${mb.toFixed(1)} MB/s`;
    return `${(bytesPerSec / 1024).toFixed(0)} KB/s`;
  };

  const formatSize = (bytes: number): string => {
    if (!bytes || bytes <= 0) return "0 MB";
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb >= 1) return `${gb.toFixed(2)} GB`;
    return `${(bytes / (1024 * 1024)).toFixed(0)} MB`;
  };

  const formatTime = (seconds?: number): string => {
    if (!seconds || seconds <= 0 || !isFinite(seconds)) return "--";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    if (m >= 60) {
      const h = Math.floor(m / 60);
      return `${h}h ${m % 60}m`;
    }
    return `${m}m ${s}s`;
  };

  return (
    <div className="nsm-overlay-container nsm-overlay-hud">
      <div className="nsm-hud-card">
        {/* Header */}
        <div className="nsm-hud-header">
          <div className="nsm-hud-title-box">
            <FaDownload className="nsm-hud-icon" />
            <div>
              <div className="nsm-hud-title">New Suspend Mode</div>
              <div className="nsm-hud-subtitle">
                System entering low-power mode to continue downloads
              </div>
            </div>
          </div>
          <div className="nsm-countdown-badge">
            <FaMoon />
            Screen off in {countdown}s
          </div>
        </div>

        {/* Game Progress */}
        <div className="nsm-game-info">
          <div className="nsm-game-title">{gameTitle}</div>
          <div className="nsm-progress-container">
            <div
              className="nsm-progress-bar"
              style={{ width: `${percent > 0 ? percent : 2}%` }}
            />
          </div>
          <div className="nsm-metrics-row">
            <div className="nsm-metric-item">
              <span>Speed:</span>
              <span className="nsm-metric-value">
                {formatSpeed(downloadInfo.bytes_per_second)}
              </span>
            </div>
            <div className="nsm-metric-item">
              <span>Progress:</span>
              <span className="nsm-metric-value">
                {percent.toFixed(1)}% (
                {formatSize(downloadInfo.completed_bytes)} / {formatSize(downloadInfo.total_bytes)})
              </span>
            </div>
            <div className="nsm-metric-item">
              <span>Time Left:</span>
              <span className="nsm-metric-value">
                {formatTime(downloadInfo.estimated_seconds_remaining)}
              </span>
            </div>
          </div>
        </div>

        {/* Status Badges */}
        <div className="nsm-status-badges">
          <div className="nsm-badge">
            <FaBatteryThreeQuarters
              className={`nsm-badge-icon ${batteryCapacity <= 20 ? "warning" : ""}`}
            />
            <div>
              <div className="nsm-badge-title">Battery Level</div>
              <div className="nsm-badge-val">
                {batteryCapacity}% {isCharging ? "(Charging)" : ""}
              </div>
            </div>
          </div>
          <div className="nsm-badge">
            <FaBolt className="nsm-badge-icon" />
            <div>
              <div className="nsm-badge-title">Auto-Suspend Threshold</div>
              <div className="nsm-badge-val">
                At &le; {settings.min_battery_threshold}% or on finish
              </div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="nsm-hud-actions">
          <button
            className="nsm-btn-primary"
            onClick={onEnterBlackout}
          >
            Turn Off Screen Now
          </button>
          <button
            className="nsm-btn-secondary"
            onClick={onWake}
          >
            <FaTimes style={{ marginRight: 6 }} /> Cancel & Keep Awake
          </button>
        </div>

        <div className="nsm-hud-footer">
          Screen turns off automatically. Press the POWER button at any time to wake console back to normal.
        </div>
      </div>
    </div>
  );
};
