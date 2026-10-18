export const PLUGIN_STYLES = `
/* Download in Background - Styles */

.dib-overlay-container {
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
.dib-overlay-blackout {
  background-color: #000000 !important;
  cursor: none;
  pointer-events: all;
  touch-action: none;
}

/* Standby splash: just the plugin mark, shown over the black screen when the console
   goes into standby with nothing downloading, then it fades out into pure black. */
.dib-splash {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  animation: dibSplash 2.5s ease-in-out forwards;
}

.dib-splash-icon {
  font-size: 60px;
  color: #4aa3ff;
  filter: drop-shadow(0 0 22px rgba(74, 163, 255, 0.45));
}

.dib-splash-title {
  font-size: 19px;
  font-weight: 600;
  letter-spacing: 0.3px;
  color: #e8eefc;
}

.dib-splash-subtitle {
  font-size: 13px;
  color: #93a4c4;
}

@keyframes dibSplash {
  0% { opacity: 0; transform: scale(0.96); }
  12% { opacity: 1; transform: scale(1); }
  78% { opacity: 1; }
  100% { opacity: 0; }
}

/* HUD Mode: Dark glassmorphic overlay */
.dib-overlay-hud {
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

.dib-hud-card {
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

.dib-hud-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dib-hud-title-box {
  display: flex;
  align-items: center;
  gap: 14px;
}

.dib-hud-icon {
  font-size: 32px;
  color: #38bdf8;
  filter: drop-shadow(0 0 8px rgba(56, 189, 248, 0.5));
}

.dib-hud-title {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: #f8fafc;
}

.dib-hud-subtitle {
  font-size: 13px;
  color: #94a3b8;
  margin-top: 2px;
}

.dib-countdown-badge {
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

.dib-game-info {
  background: rgba(15, 23, 42, 0.6);
  border-radius: 12px;
  padding: 16px 20px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.dib-game-title {
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dib-progress-container {
  width: 100%;
  height: 12px;
  background: rgba(51, 65, 85, 0.6);
  border-radius: 6px;
  overflow: hidden;
  position: relative;
}

.dib-progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #0284c7 0%, #38bdf8 50%, #818cf8 100%);
  border-radius: 6px;
  transition: width 0.3s ease;
  box-shadow: 0 0 12px rgba(56, 189, 248, 0.6);
}

.dib-metrics-row {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
  font-size: 13px;
  color: #cbd5e1;
}

.dib-metric-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dib-metric-value {
  font-weight: 600;
  color: #38bdf8;
}

.dib-status-badges {
  display: flex;
  gap: 12px;
}

.dib-badge {
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

.dib-badge-icon {
  font-size: 18px;
  color: #10b981;
}

.dib-badge-icon.warning {
  color: #f59e0b;
}

.dib-badge-title {
  font-size: 11px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.dib-badge-val {
  font-size: 14px;
  font-weight: 600;
  color: #f1f5f9;
}

.dib-hud-actions {
  display: flex;
  gap: 12px;
  margin-top: 4px;
}

.dib-btn-primary {
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

.dib-btn-primary:hover {
  background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%);
  transform: translateY(-1px);
}

.dib-btn-secondary {
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

.dib-btn-secondary:hover {
  background: rgba(71, 85, 105, 0.8);
  color: #ffffff;
}

.dib-hud-footer {
  text-align: center;
  font-size: 12px;
  color: #64748b;
  margin-top: -6px;
}

/* QAM Panel Styles */
.dib-panel-status-card {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.dib-status-tag {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: bold;
  text-transform: uppercase;
}

.dib-status-tag.active {
  background: rgba(16, 185, 129, 0.2);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.4);
}

.dib-status-tag.downloading {
  background: rgba(56, 189, 248, 0.2);
  color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.4);
}

.dib-status-tag.paused {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.4);
}

.dib-status-tag.idle {
  background: rgba(148, 163, 184, 0.15);
  color: #94a3b8;
  border: 1px solid rgba(148, 163, 184, 0.3);
}
`;
