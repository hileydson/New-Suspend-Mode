import React, { FC, useState, useEffect, useRef, useCallback } from "react";
import { call, addEventListener, removeEventListener, toaster } from "@decky/api";
import { FaDownload, FaMoon, FaBatteryThreeQuarters, FaTimes, FaBolt } from "react-icons/fa";
import { DownloadInfo, PluginSettings } from "../types";

interface OverlayProps {
  downloadInfo: DownloadInfo;
  settings: PluginSettings;
  batteryCapacity: number;
  isCharging: boolean;
  onRequestManualExit?: () => void;
}

export const Overlay: FC<OverlayProps> = ({
  downloadInfo,
  settings,
  batteryCapacity,
  isCharging,
}) => {
  const [showHud, setShowHud] = useState<boolean>(false);
  const [isBlackout, setIsBlackout] = useState<boolean>(false);
  const [countdown, setCountdown] = useState<number>(5);

  const countdownTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Full System Wake (triggered via Power Button or manual cancel button)
  const fullWakeUp = useCallback(async (reason: string = "user_input") => {
    if (countdownTimerRef.current) {
      clearInterval(countdownTimerRef.current);
      countdownTimerRef.current = null;
    }

    setShowHud(false);
    setIsBlackout(false);

    try {
      await call("exit_background_mode", reason);
    } catch (e) {
      console.error("[DownloadInBackground] Error exiting background mode:", e);
    }

    // Safely request Steam to open main screen (NEVER use window.location.href)
    try {
      const steamClient = (window as any).SteamClient;
      if (steamClient?.URL?.ExecuteSteamURL) {
        steamClient.URL.ExecuteSteamURL("steam://open/main");
      }
    } catch (e) {
      console.error("[DownloadInBackground] Error navigating to Steam home:", e);
    }

    toaster.toast({
      title: "Download in Background",
      body: "Console awakened! Returning to normal operation.",
      duration: 2500,
    });
  }, []);

  // Enter Pitch Black Mode
  const enterBlackout = useCallback(async (reason: string = "countdown_completed") => {
    if (countdownTimerRef.current) {
      clearInterval(countdownTimerRef.current);
      countdownTimerRef.current = null;
    }

    setShowHud(false);
    setIsBlackout(true);

    try {
      await call("enter_background_mode", reason);
    } catch (e) {
      console.error("[DownloadInBackground] Error entering background mode:", e);
    }
  }, []);

  // Initial HUD Sequence before going to sleep (on suspend intercept)
  const startInitialHudSequence = useCallback((customTimeout?: number) => {
    const timeoutSec = customTimeout ?? settings.hud_timeout_seconds ?? 5;

    if (timeoutSec <= 0) {
      enterBlackout("immediate");
      return;
    }

    setCountdown(timeoutSec);
    setShowHud(true);
    setIsBlackout(false);

    if (countdownTimerRef.current) {
      clearInterval(countdownTimerRef.current);
    }

    let remaining = timeoutSec;
    countdownTimerRef.current = setInterval(() => {
      remaining -= 1;
      setCountdown(remaining);
      if (remaining <= 0) {
        if (countdownTimerRef.current) {
          clearInterval(countdownTimerRef.current);
          countdownTimerRef.current = null;
        }
        enterBlackout("countdown_completed");
      }
    }, 1000);
  }, [settings.hud_timeout_seconds, enterBlackout]);

  // Listen to Backend events
  useEffect(() => {
    const handleSuspendIntercepted = (data?: any) => {
      console.log("[DownloadInBackground] Suspend intercepted!", data);
      const customTimeout = data?.hud_timeout ?? settings.hud_timeout_seconds ?? 5;
      startInitialHudSequence(customTimeout);
    };

    const handleBackgroundModeChanged = (data?: any) => {
      if (data && typeof data.is_background_mode === "boolean") {
        if (data.is_background_mode) {
          setIsBlackout(true);
          setShowHud(false);
        } else {
          // Full system wake up
          if (countdownTimerRef.current) {
            clearInterval(countdownTimerRef.current);
            countdownTimerRef.current = null;
          }
          setIsBlackout(false);
          setShowHud(false);

          // Force SteamOS to the Home Screen SAFELY (only via official API)
          try {
            const sc = (window as any).SteamClient;
            if (sc?.URL?.ExecuteSteamURL) {
              sc.URL.ExecuteSteamURL("steam://open/main");
            }
          } catch (e) {}
        }
      }
    };

    const handleBatteryCritical = (data?: any) => {
      toaster.toast({
        title: "Download in Background",
        body: `Battery reached ${data?.capacity ?? 15}%. Entering sleep now.`,
        duration: 4000,
        critical: true,
      });
    };

    const handleDownloadsCompleted = () => {
      toaster.toast({
        title: "Download in Background",
        body: "All downloads completed! Suspending console.",
        duration: 3500,
      });
    };

    const unsubSuspend = addEventListener("on_suspend_intercepted", handleSuspendIntercepted);
    const unsubMode = addEventListener("background_mode_changed", handleBackgroundModeChanged);
    const unsubBat = addEventListener("battery_critical_suspend", handleBatteryCritical);
    const unsubDone = addEventListener("downloads_completed_suspend", handleDownloadsCompleted);

    return () => {
      removeEventListener("on_suspend_intercepted", unsubSuspend);
      removeEventListener("background_mode_changed", unsubMode);
      removeEventListener("battery_critical_suspend", unsubBat);
      removeEventListener("downloads_completed_suspend", unsubDone);

      if (countdownTimerRef.current) {
        clearInterval(countdownTimerRef.current);
      }
    };
  }, [settings.hud_timeout_seconds, startInitialHudSequence]);

  // Format Helpers
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

  // If neither HUD nor blackout is active, do not render anything
  if (!showHud && !isBlackout) {
    return null;
  }

  // Pure black screen mode
  if (isBlackout) {
    return (
      <div
        className="dib-overlay-container dib-overlay-blackout"
        tabIndex={0}
        aria-hidden="true"
      />
    );
  }

  // Download HUD Mode (Initial Suspend Countdown)
  const percent = Math.min(100, Math.max(0, downloadInfo.progress_percent || 0));
  const gameTitle = downloadInfo.game_title || "Steam Game Download";

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
            onClick={() => enterBlackout("button_clicked")}
          >
            Turn Off Screen Now
          </button>
          <button
            className="dib-btn-secondary"
            onClick={() => fullWakeUp("cancel_clicked")}
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
