export const PLUGIN_STYLES = `
/* New Suspend Mode - Styles */

.nsm-overlay-container {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 9999999;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: #ffffff;
  user-select: none;
  overflow: hidden;
}

/* Blackout mode: 100% pitch black for OLED and LCD */
.nsm-overlay-blackout {
  background-color: #000000 !important;
  cursor: none;
  pointer-events: all;
  touch-action: none;
}

/* Standby splash: the plugin mark on a black screen, shown while the panel is still lit,
   just before the console goes dark. Takes the place of the download card. */
.nsm-overlay-splash {
  background-color: #000000;
  animation: dibFadeIn 0.25s ease-out;
}

/* Wake presentation: keeps the black backdrop opaque while the splash mark fades in,
   then fades the whole overlay out once hardware and controls are ready. */
.nsm-overlay-wake {
  background-color: #000000;
  cursor: none;
  pointer-events: all;
  touch-action: none;
  animation: none;
}

.nsm-overlay-splash-out {
  animation: dibFadeOut 0.3s ease-out forwards;
}

@keyframes dibFadeOut {
  from {
    opacity: 1;
  }
  to {
    opacity: 0;
  }
}

.nsm-splash {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  animation: dibSplashIn 0.5s ease-out;
}

.nsm-splash-icon {
  font-size: 60px;
  color: #4aa3ff;
  filter: drop-shadow(0 0 22px rgba(74, 163, 255, 0.45));
}

.nsm-splash-title {
  font-size: 19px;
  font-weight: 600;
  letter-spacing: 0.3px;
  color: #e8eefc;
}

.nsm-splash-subtitle {
  font-size: 13px;
  color: #93a4c4;
}

@keyframes dibSplashIn {
  from { opacity: 0; transform: scale(0.94); }
  to { opacity: 1; transform: scale(1); }
}

/* HUD Mode: Dark glassmorphic overlay */
.nsm-overlay-hud {
  background: radial-gradient(circle at center, rgba(16, 24, 40, 0.94) 0%, rgba(10, 14, 23, 0.98) 100%);
  backdrop-filter: blur(16px);
  animation: dibFadeIn 0.3s ease-out;
}

@keyframes dibFadeIn {
  from {
    opacity: 0;
    transform: scale(0.98);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.nsm-hud-card {
  width: 600px;
  max-width: 90vw;
  background: rgba(30, 41, 59, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.7), inset 0 1px 0 rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: relative;
}

.nsm-hud-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.nsm-hud-title-box {
  display: flex;
  align-items: center;
  gap: 14px;
}

.nsm-hud-icon {
  font-size: 32px;
  color: #38bdf8;
  filter: drop-shadow(0 0 8px rgba(56, 189, 248, 0.5));
}

.nsm-hud-title {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: #f8fafc;
}

.nsm-hud-subtitle {
  font-size: 13px;
  color: #94a3b8;
  margin-top: 2px;
}

.nsm-countdown-badge {
  background: rgba(56, 189, 248, 0.15);
  border: 1px solid rgba(56, 189, 248, 0.4);
  color: #38bdf8;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}

.nsm-game-info {
  background: rgba(15, 23, 42, 0.6);
  border-radius: 12px;
  padding: 16px 20px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.nsm-game-title {
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nsm-progress-container {
  width: 100%;
  height: 12px;
  background: rgba(51, 65, 85, 0.6);
  border-radius: 6px;
  overflow: hidden;
  position: relative;
}

.nsm-progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #0284c7 0%, #38bdf8 50%, #818cf8 100%);
  border-radius: 6px;
  transition: width 0.3s ease;
  box-shadow: 0 0 12px rgba(56, 189, 248, 0.6);
}

.nsm-metrics-row {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
  font-size: 13px;
  color: #cbd5e1;
}

.nsm-metric-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.nsm-metric-value {
  font-weight: 600;
  color: #38bdf8;
}

.nsm-status-badges {
  display: flex;
  gap: 12px;
}

.nsm-badge {
  flex: 1;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  padding: 10px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.nsm-badge-icon {
  font-size: 18px;
  color: #10b981;
}

.nsm-badge-icon.warning {
  color: #f59e0b;
}

.nsm-badge-title {
  font-size: 11px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.nsm-badge-val {
  font-size: 14px;
  font-weight: 600;
  color: #f1f5f9;
}

.nsm-hud-actions {
  display: flex;
  gap: 12px;
  margin-top: 4px;
}

.nsm-btn-primary {
  flex: 1;
  background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
  color: #ffffff;
  border: none;
  padding: 12px 18px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3);
}

.nsm-btn-primary:hover {
  background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%);
  transform: translateY(-1px);
}

.nsm-btn-secondary {
  flex: 1;
  background: rgba(51, 65, 85, 0.6);
  color: #e2e8f0;
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 12px 18px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.nsm-btn-secondary:hover {
  background: rgba(71, 85, 105, 0.8);
  color: #ffffff;
}

.nsm-hud-footer {
  text-align: center;
  font-size: 12px;
  color: #64748b;
  margin-top: -6px;
}

/* QAM Panel Styles */
.nsm-panel-status-card {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.nsm-status-tag {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: bold;
  text-transform: uppercase;
}

.nsm-status-tag.active {
  background: rgba(16, 185, 129, 0.2);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.4);
}

.nsm-status-tag.downloading {
  background: rgba(56, 189, 248, 0.2);
  color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.4);
}

.nsm-status-tag.paused {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.4);
}

.nsm-status-tag.idle {
  background: rgba(148, 163, 184, 0.15);
  color: #94a3b8;
  border: 1px solid rgba(148, 163, 184, 0.3);
}
`;
