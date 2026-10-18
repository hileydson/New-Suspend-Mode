import React, { FC } from "react";
import { FaDownload, FaMoon, FaBatteryThreeQuarters, FaTimes, FaBolt } from "react-icons/fa";
import { DownloadInfo, PluginSettings } from "../types";

export interface OverlayProps {
  isBackgroundMode: boolean;
  showHud: boolean;
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
  countdown,
  downloadInfo,
  settings,
  batteryCapacity,
  isCharging,
  onWake,
  onEnterBlackout,
}) => {
  // If neither HUD nor blackout is active, do not render anything
  if (!showHud && !isBackgroundMode) {
    return null;
  }

  // Pure black screen mode (hardware power button is the sole wake trigger)
  if (isBackgroundMode) {
    return (
      <div
        className="dib-overlay-container dib-overlay-blackout"
        tabIndex={-1}
        aria-hidden="true"
      />
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
    <div className="dib-overlay-container dib-overlay-hud">
      <div className="dib-hud-card">
        {/* Header */}
        <div className="dib-hud-header">
          <div className="dib-hud-title-box">
            <FaDownload className="dib-hud-icon" />
            <div>
              <div className="dib-hud-title">Download in Background</div>
              <div className="dib-hud-subtitle">
                System entering low-power mode to continue downloads
              </div>
            </div>
          </div>
          <div className="dib-countdown-badge">
            <FaMoon />
            Screen off in {countdown}s
          </div>
        </div>

        {/* Game Progress */}
        <div className="dib-game-info">
          <div className="dib-game-title">{gameTitle}</div>
          <div className="dib-progress-container">
            <div
              className="dib-progress-bar"
              style={{ width: `${percent > 0 ? percent : 2}%` }}
            />
          </div>
          <div className="dib-metrics-row">
            <div className="dib-metric-item">
              <span>Speed:</span>
              <span className="dib-metric-value">
                {formatSpeed(downloadInfo.bytes_per_second)}
              </span>
            </div>
            <div className="dib-metric-item">
              <span>Progress:</span>
              <span className="dib-metric-value">
                {percent.toFixed(1)}% (
                {formatSize(downloadInfo.completed_bytes)} / {formatSize(downloadInfo.total_bytes)})
              </span>
            </div>
            <div className="dib-metric-item">
              <span>Time Left:</span>
              <span className="dib-metric-value">
                {formatTime(downloadInfo.estimated_seconds_remaining)}
              </span>
            </div>
          </div>
        </div>

        {/* Status Badges */}
        <div className="dib-status-badges">
          <div className="dib-badge">
            <FaBatteryThreeQuarters
              className={`dib-badge-icon ${batteryCapacity <= 20 ? "warning" : ""}`}
            />
            <div>
              <div className="dib-badge-title">Battery Level</div>
              <div className="dib-badge-val">
                {batteryCapacity}% {isCharging ? "(Charging)" : ""}
              </div>
            </div>
          </div>
          <div className="dib-badge">
            <FaBolt className="dib-badge-icon" />
            <div>
              <div className="dib-badge-title">Auto-Suspend Threshold</div>
              <div className="dib-badge-val">
                At &le; {settings.min_battery_threshold}% or on finish
              </div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="dib-hud-actions">
          <button
            className="dib-btn-primary"
            onClick={onEnterBlackout}
          >
            Turn Off Screen Now
          </button>
          <button
            className="dib-btn-secondary"
            onClick={onWake}
          >
            <FaTimes style={{ marginRight: 6 }} /> Cancel & Keep Awake
          </button>
        </div>

        <div className="dib-hud-footer">
          Screen turns off automatically. Press the POWER button at any time to wake console back to normal.
        </div>
      </div>
    </div>
  );
};
