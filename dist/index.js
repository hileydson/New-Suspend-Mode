const manifest = {"name":"New Suspend Mode"};
const API_VERSION = 2;
const internalAPIConnection = window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
if (!internalAPIConnection) {
    throw new Error('[@decky/api]: Failed to connect to the loader as as the loader API was not initialized. This is likely a bug in Decky Loader.');
}
let api;
try {
    api = internalAPIConnection.connect(API_VERSION, manifest.name);
}
catch {
    api = internalAPIConnection.connect(1, manifest.name);
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version 1. Some features may not work.`);
}
if (api._version != API_VERSION) {
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version ${api._version}. Some features may not work.`);
}
const call = api.call;
const addEventListener = api.addEventListener;
const removeEventListener = api.removeEventListener;
const routerHook = api.routerHook;
const toaster = api.toaster;
const definePlugin = (fn) => {
    return (...args) => {
        return fn(...args);
    };
};

var DefaultContext = {
  color: undefined,
  size: undefined,
  className: undefined,
  style: undefined,
  attr: undefined
};
var IconContext = SP_REACT.createContext && /*#__PURE__*/SP_REACT.createContext(DefaultContext);

var _excluded = ["attr", "size", "title"];
function _objectWithoutProperties(e, t) { if (null == e) return {}; var o, r, i = _objectWithoutPropertiesLoose(e, t); if (Object.getOwnPropertySymbols) { var n = Object.getOwnPropertySymbols(e); for (r = 0; r < n.length; r++) o = n[r], -1 === t.indexOf(o) && {}.propertyIsEnumerable.call(e, o) && (i[o] = e[o]); } return i; }
function _objectWithoutPropertiesLoose(r, e) { if (null == r) return {}; var t = {}; for (var n in r) if ({}.hasOwnProperty.call(r, n)) { if (-1 !== e.indexOf(n)) continue; t[n] = r[n]; } return t; }
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function ownKeys(e, r) { var t = Object.keys(e); if (Object.getOwnPropertySymbols) { var o = Object.getOwnPropertySymbols(e); r && (o = o.filter(function (r) { return Object.getOwnPropertyDescriptor(e, r).enumerable; })), t.push.apply(t, o); } return t; }
function _objectSpread(e) { for (var r = 1; r < arguments.length; r++) { var t = null != arguments[r] ? arguments[r] : {}; r % 2 ? ownKeys(Object(t), true).forEach(function (r) { _defineProperty(e, r, t[r]); }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function (r) { Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r)); }); } return e; }
function _defineProperty(e, r, t) { return (r = _toPropertyKey(r)) in e ? Object.defineProperty(e, r, { value: t, enumerable: true, configurable: true, writable: true }) : e[r] = t, e; }
function _toPropertyKey(t) { var i = _toPrimitive(t, "string"); return "symbol" == typeof i ? i : i + ""; }
function _toPrimitive(t, r) { if ("object" != typeof t || !t) return t; var e = t[Symbol.toPrimitive]; if (void 0 !== e) { var i = e.call(t, r); if ("object" != typeof i) return i; throw new TypeError("@@toPrimitive must return a primitive value."); } return ("string" === r ? String : Number)(t); }
function Tree2Element(tree) {
  return tree && tree.map((node, i) => /*#__PURE__*/SP_REACT.createElement(node.tag, _objectSpread({
    key: i
  }, node.attr), Tree2Element(node.child)));
}
function GenIcon(data) {
  return props => /*#__PURE__*/SP_REACT.createElement(IconBase, _extends({
    attr: _objectSpread({}, data.attr)
  }, props), Tree2Element(data.child));
}
function IconBase(props) {
  var elem = conf => {
    var attr = props.attr,
      size = props.size,
      title = props.title,
      svgProps = _objectWithoutProperties(props, _excluded);
    var computedSize = size || conf.size || "1em";
    var className;
    if (conf.className) className = conf.className;
    if (props.className) className = (className ? className + " " : "") + props.className;
    return /*#__PURE__*/SP_REACT.createElement("svg", _extends({
      stroke: "currentColor",
      fill: "currentColor",
      strokeWidth: "0"
    }, conf.attr, attr, svgProps, {
      className: className,
      style: _objectSpread(_objectSpread({
        color: props.color || conf.color
      }, conf.style), props.style),
      height: computedSize,
      width: computedSize,
      xmlns: "http://www.w3.org/2000/svg"
    }), title && /*#__PURE__*/SP_REACT.createElement("title", null, title), props.children);
  };
  return IconContext !== undefined ? /*#__PURE__*/SP_REACT.createElement(IconContext.Consumer, null, conf => elem(conf)) : elem(DefaultContext);
}

// THIS FILE IS AUTO GENERATED
function FaTimes (props) {
  return GenIcon({"attr":{"viewBox":"0 0 352 512"},"child":[{"tag":"path","attr":{"d":"M242.72 256l100.07-100.07c12.28-12.28 12.28-32.19 0-44.48l-22.24-22.24c-12.28-12.28-32.19-12.28-44.48 0L176 189.28 75.93 89.21c-12.28-12.28-32.19-12.28-44.48 0L9.21 111.45c-12.28 12.28-12.28 32.19 0 44.48L109.28 256 9.21 356.07c-12.28 12.28-12.28 32.19 0 44.48l22.24 22.24c12.28 12.28 32.2 12.28 44.48 0L176 322.72l100.07 100.07c12.28 12.28 32.2 12.28 44.48 0l22.24-22.24c12.28-12.28 12.28-32.19 0-44.48L242.72 256z"},"child":[]}]})(props);
}function FaMoon (props) {
  return GenIcon({"attr":{"viewBox":"0 0 512 512"},"child":[{"tag":"path","attr":{"d":"M283.211 512c78.962 0 151.079-35.925 198.857-94.792 7.068-8.708-.639-21.43-11.562-19.35-124.203 23.654-238.262-71.576-238.262-196.954 0-72.222 38.662-138.635 101.498-174.394 9.686-5.512 7.25-20.197-3.756-22.23A258.156 258.156 0 0 0 283.211 0c-141.309 0-256 114.511-256 256 0 141.309 114.511 256 256 256z"},"child":[]}]})(props);
}function FaDownload (props) {
  return GenIcon({"attr":{"viewBox":"0 0 512 512"},"child":[{"tag":"path","attr":{"d":"M216 0h80c13.3 0 24 10.7 24 24v168h87.7c17.8 0 26.7 21.5 14.1 34.1L269.7 378.3c-7.5 7.5-19.8 7.5-27.3 0L90.1 226.1c-12.6-12.6-3.7-34.1 14.1-34.1H192V24c0-13.3 10.7-24 24-24zm296 376v112c0 13.3-10.7 24-24 24H24c-13.3 0-24-10.7-24-24V376c0-13.3 10.7-24 24-24h146.7l49 49c20.1 20.1 52.5 20.1 72.6 0l49-49H488c13.3 0 24 10.7 24 24zm-124 88c0-11-9-20-20-20s-20 9-20 20 9 20 20 20 20-9 20-20zm64 0c0-11-9-20-20-20s-20 9-20 20 9 20 20 20 20-9 20-20z"},"child":[]}]})(props);
}function FaBolt (props) {
  return GenIcon({"attr":{"viewBox":"0 0 320 512"},"child":[{"tag":"path","attr":{"d":"M296 160H180.6l42.6-129.8C227.2 15 215.7 0 200 0H56C44 0 33.8 8.9 32.2 20.8l-32 240C-1.7 275.2 9.5 288 24 288h118.7L96.6 482.5c-3.6 15.2 8 29.5 23.3 29.5 8.4 0 16.4-4.4 20.8-12l176-304c9.3-15.9-2.2-36-20.7-36z"},"child":[]}]})(props);
}function FaBatteryThreeQuarters (props) {
  return GenIcon({"attr":{"viewBox":"0 0 640 512"},"child":[{"tag":"path","attr":{"d":"M544 160v64h32v64h-32v64H64V160h480m16-64H48c-26.51 0-48 21.49-48 48v224c0 26.51 21.49 48 48 48h512c26.51 0 48-21.49 48-48v-16h8c13.255 0 24-10.745 24-24V184c0-13.255-10.745-24-24-24h-8v-16c0-26.51-21.49-48-48-48zm-144 96H96v128h320V192z"},"child":[]}]})(props);
}

const Overlay = ({ isBackgroundMode, showHud, showSplash, countdown, downloadInfo, settings, batteryCapacity, isCharging, onWake, onEnterBlackout, }) => {
    // If nothing is active, do not render anything
    if (!showHud && !isBackgroundMode && !showSplash) {
        return null;
    }
    // Pure black screen mode (hardware power button, or a controller, is the wake trigger)
    if (isBackgroundMode) {
        return (SP_JSX.jsx("div", { className: "nsm-overlay-container nsm-overlay-blackout", tabIndex: -1, "aria-hidden": "true" }));
    }
    // Standby splash: shown while the panel is still lit, just before the screen goes
    // dark. Takes the place of the download card when there is no download to report.
    if (showSplash) {
        return (SP_JSX.jsx("div", { className: "nsm-overlay-container nsm-overlay-splash", tabIndex: -1, "aria-hidden": "true", children: SP_JSX.jsxs("div", { className: "nsm-splash", children: [SP_JSX.jsx(FaDownload, { className: "nsm-splash-icon" }), SP_JSX.jsx("div", { className: "nsm-splash-title", children: "New Suspend Mode" }), SP_JSX.jsx("div", { className: "nsm-splash-subtitle", children: "Press POWER or use a controller to wake" })] }) }));
    }
    // Download HUD Mode (Countdown before screen off)
    const percent = Math.min(100, Math.max(0, downloadInfo.progress_percent || 0));
    const gameTitle = downloadInfo.game_title || "Steam Game Download";
    const formatSpeed = (bytesPerSec) => {
        if (!bytesPerSec || bytesPerSec <= 0)
            return "0 KB/s";
        const mb = bytesPerSec / (1024 * 1024);
        if (mb >= 1)
            return `${mb.toFixed(1)} MB/s`;
        return `${(bytesPerSec / 1024).toFixed(0)} KB/s`;
    };
    const formatSize = (bytes) => {
        if (!bytes || bytes <= 0)
            return "0 MB";
        const gb = bytes / (1024 * 1024 * 1024);
        if (gb >= 1)
            return `${gb.toFixed(2)} GB`;
        return `${(bytes / (1024 * 1024)).toFixed(0)} MB`;
    };
    const formatTime = (seconds) => {
        if (!seconds || seconds <= 0 || !isFinite(seconds))
            return "--";
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        if (m >= 60) {
            const h = Math.floor(m / 60);
            return `${h}h ${m % 60}m`;
        }
        return `${m}m ${s}s`;
    };
    return (SP_JSX.jsx("div", { className: "nsm-overlay-container nsm-overlay-hud", children: SP_JSX.jsxs("div", { className: "nsm-hud-card", children: [SP_JSX.jsxs("div", { className: "nsm-hud-header", children: [SP_JSX.jsxs("div", { className: "nsm-hud-title-box", children: [SP_JSX.jsx(FaDownload, { className: "nsm-hud-icon" }), SP_JSX.jsxs("div", { children: [SP_JSX.jsx("div", { className: "nsm-hud-title", children: "New Suspend Mode" }), SP_JSX.jsx("div", { className: "nsm-hud-subtitle", children: "System entering low-power mode to continue downloads" })] })] }), SP_JSX.jsxs("div", { className: "nsm-countdown-badge", children: [SP_JSX.jsx(FaMoon, {}), "Screen off in ", countdown, "s"] })] }), SP_JSX.jsxs("div", { className: "nsm-game-info", children: [SP_JSX.jsx("div", { className: "nsm-game-title", children: gameTitle }), SP_JSX.jsx("div", { className: "nsm-progress-container", children: SP_JSX.jsx("div", { className: "nsm-progress-bar", style: { width: `${percent > 0 ? percent : 2}%` } }) }), SP_JSX.jsxs("div", { className: "nsm-metrics-row", children: [SP_JSX.jsxs("div", { className: "nsm-metric-item", children: [SP_JSX.jsx("span", { children: "Speed:" }), SP_JSX.jsx("span", { className: "nsm-metric-value", children: formatSpeed(downloadInfo.bytes_per_second) })] }), SP_JSX.jsxs("div", { className: "nsm-metric-item", children: [SP_JSX.jsx("span", { children: "Progress:" }), SP_JSX.jsxs("span", { className: "nsm-metric-value", children: [percent.toFixed(1), "% (", formatSize(downloadInfo.completed_bytes), " / ", formatSize(downloadInfo.total_bytes), ")"] })] }), SP_JSX.jsxs("div", { className: "nsm-metric-item", children: [SP_JSX.jsx("span", { children: "Time Left:" }), SP_JSX.jsx("span", { className: "nsm-metric-value", children: formatTime(downloadInfo.estimated_seconds_remaining) })] })] })] }), SP_JSX.jsxs("div", { className: "nsm-status-badges", children: [SP_JSX.jsxs("div", { className: "nsm-badge", children: [SP_JSX.jsx(FaBatteryThreeQuarters, { className: `nsm-badge-icon ${batteryCapacity <= 20 ? "warning" : ""}` }), SP_JSX.jsxs("div", { children: [SP_JSX.jsx("div", { className: "nsm-badge-title", children: "Battery Level" }), SP_JSX.jsxs("div", { className: "nsm-badge-val", children: [batteryCapacity, "% ", isCharging ? "(Charging)" : ""] })] })] }), SP_JSX.jsxs("div", { className: "nsm-badge", children: [SP_JSX.jsx(FaBolt, { className: "nsm-badge-icon" }), SP_JSX.jsxs("div", { children: [SP_JSX.jsx("div", { className: "nsm-badge-title", children: "Auto-Suspend Threshold" }), SP_JSX.jsxs("div", { className: "nsm-badge-val", children: ["At \u2264 ", settings.min_battery_threshold, "% or on finish"] })] })] })] }), SP_JSX.jsxs("div", { className: "nsm-hud-actions", children: [SP_JSX.jsx("button", { className: "nsm-btn-primary", onClick: onEnterBlackout, children: "Turn Off Screen Now" }), SP_JSX.jsxs("button", { className: "nsm-btn-secondary", onClick: onWake, children: [SP_JSX.jsx(FaTimes, { style: { marginRight: 6 } }), " Cancel & Keep Awake"] })] }), SP_JSX.jsx("div", { className: "nsm-hud-footer", children: "Screen turns off automatically. Press the POWER button at any time to wake console back to normal." })] }) }));
};

const PLUGIN_STYLES = `
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

const DEFAULT_SETTINGS = {
    enabled: true,
    enable_plugin_when_plugged_in: false,
    min_battery_threshold: 15,
    hud_timeout_seconds: 5,
    auto_suspend_delay_seconds: 120,
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
    real_sleep_start_minutes: 0, // 00:00
    real_sleep_end_minutes: 420, // 07:00
    wake_at_period_end: true,
    standby_on_power_off: true,
    wake_on_bluetooth_connect: true,
    wake_on_controller_button: true,
    advanced_mode: false,
};
const DEFAULT_DOWNLOAD_INFO = {
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
const WAKE_COOLDOWN_MS = 5000;
let state = {
    settings: { ...DEFAULT_SETTINGS },
    downloadInfo: { ...DEFAULT_DOWNLOAD_INFO },
    batteryCapacity: 100,
    isCharging: false,
    powerPlugged: false,
    isBackgroundMode: false,
    standbyMode: false,
    showHud: false,
    showSplash: false,
    countdown: 5,
};
const listeners = new Set();
const getState = () => state;
const setState = (patch) => {
    state = { ...state, ...patch };
    listeners.forEach((listener) => listener());
};
/**
 * Asks every component to check its state again without changing it.
 *
 * A component that already drew the current state does nothing. One that missed an
 * update - the overlay, say, if a wake landed while it was being mounted - redraws.
 */
const refreshSubscribers = () => listeners.forEach((listener) => listener());
const subscribe = (listener) => {
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
const useUiState = () => SP_REACT.useSyncExternalStore(subscribe, getState);
/**
 * Timing state that nothing is drawn from, so changing it never re-renders anything.
 */
const runtime = {
    backgroundModeEnteredTime: 0,
    wakeCooldownUntil: 0,
    /** A real suspend the plugin itself asked for: the sleep patches get out of the way. */
    realSuspendUntil: 0,
};
/**
 * Mirrors _effective_enabled() in main.py: 'Enable Plugin', or 'Enable Plugin When
 * Plugged In' while on AC.
 */
const isPluginEnabled = (s = state) => s.settings.enabled !== false ||
    (s.settings.enable_plugin_when_plugged_in === true && s.powerPlugged);
/** Writes a diagnostic entry into the plugin's own log file, when debug logging is on. */
const debugLog = (payload) => {
    if (state.settings.debug_logging === false)
        return;
    call("log_debug", payload).catch(() => { });
};

let hudTimer = null;
let splashTimer = null;
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
const stopFlowTimers = () => {
    stopHudTimer();
    stopSplashTimer();
};
/** Drops the download card's countdown, leaving everything else as it is. */
const cancelHudCountdown = () => {
    stopHudTimer();
};
/** Drops the standby splash and its pending entry into standby. */
const clearStandbySplash = () => {
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
const closeSteamSideMenus = () => {
    const close = () => {
        try {
            DFL.Navigation.CloseSideMenus?.();
        }
        catch (e) { }
    };
    close();
    [150, 400, 800, 1400, 2000, 2800, 3600].forEach((delay) => setTimeout(close, delay));
};
/**
 * Everything the interface has to undo on wake, shared by both ways a wake arrives:
 * this side asking for it, and the backend announcing it already happened.
 */
const finishWakeUi = (reason) => {
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
const triggerEnterStandby = async (reason) => {
    if (Date.now() < runtime.wakeCooldownUntil) {
        console.log("[NewSuspendMode] Wake cooldown active, not entering standby.");
        return;
    }
    stopHudTimer();
    stopSplashTimer();
    runtime.backgroundModeEnteredTime = Date.now();
    setState({ showSplash: false, showHud: false, isBackgroundMode: true, standbyMode: true });
    try {
        const success = await call("enter_background_mode", reason);
        if (success === false) {
            setState({ isBackgroundMode: false });
        }
    }
    catch (e) {
        console.error("[NewSuspendMode] Error entering standby:", e);
    }
};
/**
 * Shows the plugin mark, THEN enters standby a few seconds later.
 *
 * The order matters: the backlight is driven to zero as part of entering, so anything
 * drawn after that is invisible.
 */
const startStandbySplash = (seconds, reason = "standby_splash") => {
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
const triggerFullWake = async (reason = "wake") => {
    finishWakeUi(reason);
    try {
        await call("exit_background_mode", reason);
    }
    catch (e) {
        console.error("[NewSuspendMode] Error calling exit_background_mode:", e);
    }
    toaster.toast({
        title: "New Suspend Mode",
        body: "Console awakened!",
        duration: 2000,
    });
};
/** Enters the black screen with the download carrying on in the background. */
const triggerEnterBlackout = async (reason = "countdown_completed") => {
    if (Date.now() < runtime.wakeCooldownUntil) {
        console.log("[NewSuspendMode] Wake cooldown active, blocking enter blackout.");
        return;
    }
    stopHudTimer();
    runtime.backgroundModeEnteredTime = Date.now();
    setState({ showHud: false, isBackgroundMode: true });
    try {
        const success = await call("enter_background_mode", reason);
        if (success === false) {
            // Backend rejected entry -> restore to normal
            setState({ isBackgroundMode: false });
        }
    }
    catch (e) {
        console.error("[NewSuspendMode] Error entering background mode:", e);
    }
};
/** Shows the download card with a countdown, then turns the screen black. */
const startHudCountdown = (customTimeout) => {
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
const wakeIfSettled = (reason) => {
    if (Date.now() - runtime.backgroundModeEnteredTime >= 2000) {
        console.log(`[NewSuspendMode] Sleep requested while in our mode -> waking up (${reason}).`);
        triggerFullWake(reason);
    }
};

/**
 * The plugin's full-screen layer, mounted over the whole Steam interface through
 * routerHook.addGlobalComponent.
 *
 * Renders nothing at all unless the HUD, the splash or the black screen is up, so once
 * the console is awake there is nothing of the plugin left on screen.
 */
const GlobalOverlay = () => {
    const s = useUiState();
    if (!s.isBackgroundMode && !s.showHud && !s.showSplash) {
        return null;
    }
    return (SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsx("style", { children: PLUGIN_STYLES }), SP_JSX.jsx(Overlay, { isBackgroundMode: s.isBackgroundMode, showHud: s.showHud, showSplash: s.showSplash, countdown: s.countdown, downloadInfo: s.downloadInfo, settings: s.settings, batteryCapacity: s.batteryCapacity, isCharging: s.isCharging, onWake: () => triggerFullWake("overlay_wake"), onEnterBlackout: () => triggerEnterBlackout("manual_screen_off") })] }));
};

/** The sections revealed by "Advanced Features". */
const AdvancedSettings = ({ settings, updateSetting }) => (SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsxs(DFL.PanelSection, { title: "Behavior", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Auto-Suspend Battery Threshold", description: "Console suspends automatically if battery drops below this limit during download.", value: settings.min_battery_threshold, min: 5, max: 30, step: 1, showValue: true, valueSuffix: "%", onChange: (val) => updateSetting("min_battery_threshold", val) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "HUD Display Countdown", description: "Seconds the download card shows on screen before turning display off.", value: settings.hud_timeout_seconds, min: 0, max: 15, step: 1, showValue: true, valueSuffix: "s", onChange: (val) => updateSetting("hud_timeout_seconds", val) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Completion Suspend Delay", description: "Seconds to wait after all downloads complete before automatically sleeping.", value: settings.auto_suspend_delay_seconds, min: 30, max: 600, step: 30, showValue: true, valueSuffix: "s", onChange: (val) => updateSetting("auto_suspend_delay_seconds", val) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Block All Input While Screen Is Off", description: "Freezes button mapping and disconnects external controllers so only the power button responds. Turn off if a controller misbehaves after waking.", checked: settings.deep_input_lockout, onChange: (checked) => updateSetting("deep_input_lockout", checked) }) })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Power Saving & Screen Options", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Turn Off Display Backlight", description: "Physically drops LCD/OLED panel backlight brightness to 0.", checked: settings.turn_off_backlight, onChange: (checked) => updateSetting("turn_off_backlight", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Pitch Black OLED Mode", description: "Presents a pure black overlay, shutting off individual OLED pixels.", checked: settings.oled_black_screen, onChange: (checked) => updateSetting("oled_black_screen", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Force TV Off (real no-signal)", description: "Desktop with a TV only. A black screen is still a valid HDMI signal, so the TV stays lit. This stops the video signal entirely by disabling the HDMI/DP connector, so the TV reports no signal and reaches its own standby. The built-in panel of a handheld is never touched. EXPERIMENTAL: on a single-display desktop the session becomes headless while in the mode \u2014 the same as unplugging the cable \u2014 so test it before relying on it.", checked: settings.tv_force_connector_off === true, onChange: (checked) => updateSetting("tv_force_connector_off", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Throttle CPU to Powersave", description: "Switches power profile to power-saver and lowers CPU clock frequencies.", checked: settings.throttle_cpu, onChange: (checked) => updateSetting("throttle_cpu", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Throttle GPU to 200MHz", description: "Sets AMD GPU performance level to low, minimizing GPU power draw.", checked: settings.throttle_gpu, onChange: (checked) => updateSetting("throttle_gpu", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Mute Audio While Screen Off", description: "Silences audio output during background download to prevent disturbance.", checked: settings.mute_audio, onChange: (checked) => updateSetting("mute_audio", checked) }) })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Standby Wake Sources", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.Field, { label: "What You Will See", description: settings.standby_on_power_off
                            ? "Downloading: the download card, then black. Nothing downloading: just the plugin logo, then black."
                            : "Standby off: sleep is intercepted only while a download is active, and the download card is shown." }) }), settings.standby_on_power_off && (SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Wake When A Bluetooth Pad Connects", description: "Bluetooth stays on in standby. Turning a paired controller on is enough to wake the console, no button needed.", checked: settings.wake_on_bluetooth_connect, onChange: (checked) => updateSetting("wake_on_bluetooth_connect", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Wake On Controller Button", description: "For USB and dongle controllers, connecting is not enough: press Guide/Home, Select or Start to wake. The console's own buttons stay dead - only power works there.", checked: settings.wake_on_controller_button, onChange: (checked) => updateSetting("wake_on_controller_button", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.Field, { label: "Battery In Standby", description: `Standby keeps the console powered, so it does use battery. It drops to a real suspend at ${settings.min_battery_threshold}% to protect it.` }) })] }))] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Download Pace (Fan & Heat)", children: [settings.limit_download_speed && (SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Download Speed Cap", description: "Lower is quieter and cooler. 6 MB/s still downloads about 21 GB per hour.", value: settings.download_speed_limit_mbps, min: 1, max: 30, step: 1, showValue: true, valueSuffix: " MB/s", onChange: (val) => updateSetting("download_speed_limit_mbps", val) }) })), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Steam CPU Budget", description: "Hard limit on the CPU Steam may use while the screen is off, as a share of one core. This is what keeps the chip cool enough for the fans to idle.", value: settings.download_cpu_percent, min: 0, max: 100, step: 5, showValue: true, valueSuffix: "%", onChange: (val) => updateSetting("download_cpu_percent", val) }) })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Troubleshooting", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Also Disconnect Built-In Controller", description: "EXPERIMENTAL. Only enable if buttons still act while the screen is off. Detaches the built-in pad's raw HID interface, which crashed the session on some consoles.", checked: settings.block_controller_hidraw, onChange: (checked) => updateSetting("block_controller_hidraw", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Auto Restore Hardware After Wake", description: "Ten seconds after waking, if anything still looks capped at the plugin's own values (frequency, turbo, ryzenadj, platform profile), runs the same hard reset the button above does. Turn off if another tool manages your TDP and you prefer the button.", checked: settings.auto_hard_reset_after_wake !== false, onChange: (checked) => updateSetting("auto_hard_reset_after_wake", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Write Diagnostic Logs", description: "Records the full input and thermal picture to the plugin log on every screen-off. Leave on while tuning.", checked: settings.debug_logging, onChange: (checked) => updateSetting("debug_logging", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.Field, { label: "Restore Hardware Now \u2014 When to use it", description: "The button above puts every clock, power limit and speed cap back without rebooting, even ones left behind by a crash. It also re-enables turbo boost, makes the firmware re-apply the current power profile, and raises any CPU ceiling still below what the chip reports \u2014 so it will overrule another tool's TDP settings while it runs.", bottomSeparator: "none" }) })] })] }));

const formatHM = (minutes) => {
    const safe = Math.max(0, Math.min(1430, Math.round(minutes / 10) * 10));
    const h = Math.floor(safe / 60);
    const m = safe % 60;
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
};
const SettingsPanel = ({ settings, setSettings, downloadInfo, isBackgroundMode, standbyMode, batteryCapacity, isCharging, powerPlugged, }) => {
    const updateSetting = async (key, val) => {
        const updated = { ...settings, [key]: val };
        setSettings(updated);
        try {
            await call("save_settings", updated);
        }
        catch (e) {
            console.error("[NewSuspendMode] Error saving settings:", e);
        }
    };
    const formatSpeed = (bytesPerSec) => {
        if (!bytesPerSec || bytesPerSec <= 0)
            return "0 KB/s";
        const mb = bytesPerSec / (1024 * 1024);
        if (mb >= 1)
            return `${mb.toFixed(1)} MB/s`;
        return `${(bytesPerSec / 1024).toFixed(0)} KB/s`;
    };
    const isPaused = Boolean(downloadInfo.is_paused);
    const isDownloading = !isPaused &&
        Boolean(downloadInfo.is_downloading ||
            (downloadInfo.bytes_per_second || 0) > 10000);
    const advanced = settings.advanced_mode === true;
    const startMin = settings.real_sleep_start_minutes ?? 0;
    const endMin = settings.real_sleep_end_minutes ?? 420;
    return (SP_JSX.jsxs("div", { children: [SP_JSX.jsxs(DFL.PanelSection, { title: "Plugin", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Enable Plugin", description: "Intercepts suspend when downloading, turns off screen, and saves power.", checked: settings.enabled, onChange: (checked) => updateSetting("enabled", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Enable Plugin When Plugged In", description: "Force-enables the plugin whenever the device is on AC power, regardless of the toggle above. Handy for a desktop PC that is always plugged in, or a handheld where you only want the plugin active while charging.", checked: settings.enable_plugin_when_plugged_in === true, onChange: (checked) => updateSetting("enable_plugin_when_plugged_in", checked) }) })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Download & System Status", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.Field, { label: "Download Status", description: isDownloading
                                ? `${downloadInfo.game_title || "Steam Download"} (${formatSpeed(downloadInfo.bytes_per_second)})`
                                : isPaused
                                    ? `${downloadInfo.game_title ? downloadInfo.game_title + " (Paused)" : "Downloads paused"}`
                                    : "No active downloads", children: SP_JSX.jsx("span", { className: `nsm-status-tag ${isDownloading ? "downloading" : isPaused ? "paused" : "idle"}`, children: isDownloading ? "DOWNLOADING" : isPaused ? "PAUSED" : "IDLE" }) }) }), (isDownloading || (isPaused && downloadInfo.total_bytes > 0)) && (SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsxs("div", { style: { width: "100%", margin: "4px 0" }, children: [SP_JSX.jsxs("div", { style: {
                                        display: "flex",
                                        justifyContent: "space-between",
                                        fontSize: "12px",
                                        color: "#cbd5e1",
                                        marginBottom: "4px",
                                    }, children: [SP_JSX.jsxs("span", { children: ["Progress: ", downloadInfo.progress_percent.toFixed(1), "%"] }), SP_JSX.jsx("span", { children: isDownloading
                                                ? `Speed: ${formatSpeed(downloadInfo.bytes_per_second)}`
                                                : "Paused" })] }), SP_JSX.jsx(DFL.ProgressBar, { nProgress: downloadInfo.progress_percent || 0 })] }) })), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.Field, { label: "Battery Level", description: `Auto-sleep threshold: ${settings.min_battery_threshold}%`, children: SP_JSX.jsxs("span", { style: { fontWeight: "bold" }, children: [batteryCapacity, "% ", isCharging ? "⚡ (Charging)" : "🔋"] }) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.Field, { label: standbyMode ? "Standby Mode" : "Background Download Mode", description: standbyMode
                                ? "Console off, waiting for a controller"
                                : isBackgroundMode
                                    ? "Active (Screen off & power saving enabled)"
                                    : "Inactive (Normal operation)", children: SP_JSX.jsx("span", { className: `nsm-status-tag ${isBackgroundMode ? "active" : "idle"}`, children: standbyMode ? "STANDBY" : isBackgroundMode ? "ACTIVE" : "IDLE" }) }) })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Essentials", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Replace Sleep With New Suspend Mode", description: "The power button AND the Sleep option in the SteamOS power menu both enter the plugin's new suspend mode instead of the stock one: screen black, downloads carry on, a controller brings it back. Shut Down still powers off for real.", checked: settings.standby_on_power_off, onChange: (checked) => updateSetting("standby_on_power_off", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Real Sleep During A Time Period", description: "Inside the period below, with no download running, a Sleep from the power menu or the power button triggers the REAL SteamOS sleep instead of our standby. The period wraps across midnight (e.g. 23:00 - 07:00 means 23:00 through 06:59).", checked: settings.enter_real_sleep_after_time === true, onChange: (checked) => updateSetting("enter_real_sleep_after_time", checked) }) }), settings.enter_real_sleep_after_time && (SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: `Period Start — ${formatHM(startMin)}`, description: `Period: ${formatHM(startMin)} - ${formatHM(endMin)}. Inside the window, real sleep. Outside, our standby as usual.`, value: startMin, min: 0, max: 1430, step: 10, onChange: (val) => updateSetting("real_sleep_start_minutes", val) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: `Period End — ${formatHM(endMin)}`, value: endMin, min: 0, max: 1430, step: 10, onChange: (val) => updateSetting("real_sleep_end_minutes", val) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Return To New Suspend Mode At Period End", description: "At the end of the period, the RTC wakes the system from the real sleep and the plugin immediately re-enters the new suspend mode, so a controller can wake it. If off, the console stays in the real sleep until you wake it manually.", checked: settings.wake_at_period_end === true, onChange: (checked) => updateSetting("wake_at_period_end", checked) }) })] })), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Slow Down Download", description: "Caps incoming speed so there is far less to decompress and write. Downloads take longer, the console stays cold and the fans stay off.", checked: settings.limit_download_speed, onChange: (checked) => updateSetting("limit_download_speed", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { layout: "below", onClick: async () => {
                                try {
                                    await call("force_restore");
                                    toaster.toast({
                                        title: "New Suspend Mode",
                                        body: "Hardware restored: clocks, power limits and speed caps are back to normal.",
                                        duration: 4000,
                                    });
                                }
                                catch (e) {
                                    toaster.toast({
                                        title: "New Suspend Mode",
                                        body: "Could not restore the hardware; see the plugin log.",
                                        duration: 4000,
                                    });
                                }
                            }, children: "Restore Hardware Now" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Advanced Features", description: "Reveals every tuning option: battery thresholds, per-component throttles, standby wake sources, download pace limits and troubleshooting toggles. Leave off for a short, friendly panel.", checked: advanced, onChange: (checked) => updateSetting("advanced_mode", checked) }) })] }), advanced && SP_JSX.jsx(AdvancedSettings, { settings: settings, updateSetting: updateSetting })] }));
};

/** The plugin's page in the Quick Access menu. */
const PluginContent = () => {
    const s = useUiState();
    return (SP_JSX.jsx(SettingsPanel, { settings: s.settings, setSettings: (settings) => setState({ settings }), downloadInfo: s.downloadInfo, isBackgroundMode: s.isBackgroundMode, standbyMode: s.standbyMode, batteryCapacity: s.batteryCapacity, isCharging: s.isCharging, powerPlugged: s.powerPlugged }));
};

const steamDownloads = () => window.SteamClient?.Downloads;
/**
 * Last snapshot read straight from the Steam client, and when it was taken. It is more
 * accurate than the backend's own detection, but only while it is fresh.
 */
let lastInfo = null;
let lastInfoTime = 0;
const freshSteamDownloadInfo = () => lastInfo && Date.now() - lastInfoTime < 6000 ? lastInfo : null;
// Hand download metrics to the backend only when they actually changed, or every 8s
// while downloading so the backend knows the frontend is still reporting.
let lastSentKey = "";
let lastSentTime = 0;
const pushDownloadStatus = (info) => {
    const key = [
        info.is_downloading,
        info.is_paused,
        info.game_title,
        Math.round(info.progress_percent),
    ].join("|");
    const now = Date.now();
    const isIdle = !info.is_downloading && !info.is_paused;
    if (key === lastSentKey && (isIdle || now - lastSentTime < 8000)) {
        // Idle and unchanged: say nothing at all, so an enabled plugin with no download
        // is completely silent instead of poking the backend twice a second.
        return;
    }
    lastSentKey = key;
    lastSentTime = now;
    call("update_download_status", info).catch(() => { });
};
const firstQueueTitle = (queue) => Array.isArray(queue) && queue.length > 0
    ? queue[0]?.display_name ?? queue[0]?.app_name ?? queue[0]?.name
    : undefined;
/** True when nothing in the queue is actively downloading. */
const queueLooksPaused = (queue) => {
    if (!Array.isArray(queue))
        return false;
    if (queue.length === 0)
        return true;
    return !queue.some((item) => (item.bDownloading || item.bIsDownloading || item.active) &&
        !item.bPaused &&
        !item.bIsPaused &&
        !item.paused);
};
/** Reads the Steam client's download overview and shares it with the backend. */
const querySteamDownloads = async () => {
    if (!isPluginEnabled()) {
        return;
    }
    try {
        const downloads = steamDownloads();
        if (!downloads?.GetDownloadOverview)
            return;
        const overview = downloads.GetDownloadOverview();
        if (!overview)
            return;
        const bps = Number(overview.bytes_per_second ?? overview.current_bytes_per_second ?? 0);
        const totalBytes = Number(overview.total_bytes ?? overview.bytes_total ?? 0);
        const completedBytes = Number(overview.completed_bytes ?? overview.bytes_downloaded ?? 0);
        const percent = totalBytes > 0
            ? (completedBytes / totalBytes) * 100
            : Number(overview.overall_percent_complete ?? 0);
        let etaSeconds = 0;
        if (bps > 0 && totalBytes > completedBytes) {
            etaSeconds = Math.round((totalBytes - completedBytes) / bps);
        }
        const queue = downloads.GetQueue ? downloads.GetQueue() : undefined;
        const gameTitle = (overview.game_name ?? overview.app_name ?? overview.title) || firstQueueTitle(queue);
        const isPaused = Boolean(overview.bIsPaused ||
            overview.paused ||
            overview.bPaused ||
            overview.bQueuePaused ||
            overview.is_paused ||
            overview.m_bPaused);
        const queuePaused = queueLooksPaused(queue);
        const isDl = !isPaused &&
            !queuePaused &&
            (bps > 10000 || (overview.bIsDownloading === true && bps > 0));
        const info = {
            is_downloading: isDl,
            is_paused: isPaused || queuePaused,
            bytes_per_second: isDl ? bps : 0,
            total_bytes: totalBytes,
            completed_bytes: completedBytes,
            progress_percent: percent,
            game_title: gameTitle || "Steam Download",
            estimated_seconds_remaining: isDl ? etaSeconds : 0,
        };
        lastInfo = info;
        lastInfoTime = Date.now();
        setState({ downloadInfo: info });
        pushDownloadStatus(info);
    }
    catch (e) {
        // Quietly ignore if SteamClient isn't ready
    }
};
/** Re-reads the downloads whenever the Steam client says they changed. */
const watchSteamDownloads = () => {
    let unregister = null;
    try {
        const reg = steamDownloads()?.RegisterForDownloadOverviewChanges?.((data) => {
            if (data) {
                querySteamDownloads();
            }
        });
        if (reg && typeof reg.unregister === "function") {
            unregister = () => reg.unregister();
        }
    }
    catch (e) {
        console.warn("[NewSuspendMode] Could not register for download overview changes:", e);
    }
    return () => {
        try {
            unregister?.();
        }
        catch (e) { }
    };
};

// Backend round-trip cadence. While nothing is downloading the plugin polls slowly and
// sends nothing, so an enabled plugin with no download costs SteamOS nothing.
const POLL_ACTIVE_MS = 2000;
const POLL_IDLE_MS = 5000;
const POLL_DISABLED_MS = 10000;
/** Subscribes to everything the Python backend announces. Returns the unsubscribe. */
const listenToBackend = () => {
    const subscriptions = [];
    const listen = (event, handler) => {
        try {
            subscriptions.push([event, addEventListener(event, handler)]);
        }
        catch (e) {
            console.warn(`[NewSuspendMode] Could not register ${event} listener:`, e);
        }
    };
    listen("background_mode_changed", (data) => {
        console.log("[NewSuspendMode] background_mode_changed event received:", data);
        const isBg = typeof data === "boolean" ? data : Boolean(data?.is_background_mode);
        if (!isBg) {
            // System awakened from the backend: same cleanup as a wake asked for here.
            finishWakeUi(String(data?.reason ?? "backend_wake"));
            return;
        }
        runtime.backgroundModeEnteredTime = Date.now();
        clearStandbySplash();
        setState({
            isBackgroundMode: true,
            showHud: false,
            ...(Boolean(data?.standby) ? { standbyMode: true } : {}),
        });
    });
    listen("on_suspend_intercepted", (data) => {
        console.log("[NewSuspendMode] on_suspend_intercepted event received:", data);
        if (getState().isBackgroundMode) {
            // If already in background mode, this is a wake action!
            triggerFullWake("suspend_event_during_bg");
            return;
        }
        if (Date.now() < runtime.wakeCooldownUntil) {
            console.log("[NewSuspendMode] Ignoring on_suspend_intercepted during wake cooldown.");
            return;
        }
        startHudCountdown(data?.hud_timeout ?? getState().settings.hud_timeout_seconds ?? 5);
    });
    // Backend asked for standby: draw the plugin mark first, then go dark
    listen("on_standby_requested", (data) => {
        console.log("[NewSuspendMode] on_standby_requested received:", data);
        if (getState().isBackgroundMode) {
            return;
        }
        const seconds = Number(data?.splash_seconds ?? getState().settings.hud_timeout_seconds ?? 5);
        startStandbySplash(seconds, String(data?.reason ?? "standby_splash"));
    });
    listen("battery_critical_suspend", (data) => {
        // A suspend the plugin itself asked for: Steam must be allowed to prepare for it.
        runtime.realSuspendUntil = Date.now() + 60000;
        toaster.toast({
            title: "New Suspend Mode",
            body: `Battery reached ${data?.capacity ?? 15}%. Entering sleep now.`,
            duration: 4000,
            critical: true,
        });
    });
    listen("downloads_completed_suspend", () => {
        // Also a real suspend: let Steam suspend its games properly on the way down.
        runtime.realSuspendUntil = Date.now() + 60000;
        toaster.toast({
            title: "New Suspend Mode",
            body: "All downloads completed! Suspending console.",
            duration: 3500,
        });
    });
    return () => {
        for (const [event, listener] of subscriptions) {
            try {
                removeEventListener(event, listener);
            }
            catch (e) { }
        }
    };
};
/** Brings the interface's state in line with the backend's. */
const syncBackendStatus = async () => {
    try {
        const status = await call("get_status");
        if (!status)
            return;
        const backendIsBg = Boolean(status.is_background_mode);
        if (getState().isBackgroundMode && !backendIsBg) {
            console.log("[NewSuspendMode] Backend woke up -> Synchronizing frontend!");
            finishWakeUi("status_poll_sync");
        }
        const current = getState();
        const fresh = freshSteamDownloadInfo();
        setState({
            isBackgroundMode: backendIsBg,
            standbyMode: Boolean(status.standby_mode),
            batteryCapacity: Number(status.battery_capacity ?? 100),
            isCharging: Boolean(status.is_charging),
            powerPlugged: Boolean(status.power_plugged),
            settings: status.settings ? { ...current.settings, ...status.settings } : current.settings,
            downloadInfo: status.download_info
                ? fresh
                    ? { ...status.download_info, ...fresh }
                    : { ...current.downloadInfo, ...status.download_info }
                : current.downloadInfo,
        });
    }
    catch (e) {
        console.error("[NewSuspendMode] Error polling backend status:", e);
    }
};
/**
 * Polls the backend on an adaptive schedule, and watches for a kernel resume.
 * Returns the function that stops both.
 */
const startBackendSync = () => {
    let stopped = false;
    let pollTimer = null;
    const scheduleNextPoll = () => {
        const s = getState();
        const isActive = s.isBackgroundMode ||
            s.showHud ||
            Boolean(s.downloadInfo.is_downloading && !s.downloadInfo.is_paused);
        const delay = !isPluginEnabled() ? POLL_DISABLED_MS : isActive ? POLL_ACTIVE_MS : POLL_IDLE_MS;
        pollTimer = setTimeout(runPoll, delay);
    };
    const runPoll = async () => {
        try {
            await syncBackendStatus();
            await querySteamDownloads();
        }
        finally {
            if (!stopped) {
                scheduleNextPoll();
            }
        }
    };
    runPoll();
    // Kernel sleep resume detection: the clock jumps forward across a real suspend.
    let lastHeartbeat = Date.now();
    const heartbeat = setInterval(() => {
        const now = Date.now();
        const delta = now - lastHeartbeat;
        lastHeartbeat = now;
        // Our own mode throttles the CPU, which delays timers on purpose; only a real
        // kernel sleep counts here.
        if (getState().isBackgroundMode) {
            return;
        }
        if (delta > 15000) {
            console.log(`[NewSuspendMode] Kernel resume detected (delta=${delta}ms)! Enforcing wake state.`);
            runtime.wakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;
            cancelHudCountdown();
            setState({ showHud: false, isBackgroundMode: false });
            call("exit_background_mode", "kernel_resume_clock_jump").catch(() => { });
        }
    }, 2000);
    return () => {
        stopped = true;
        if (pollTimer)
            clearTimeout(pollTimer);
        clearInterval(heartbeat);
    };
};

/**
 * Takes over Sleep inside the Steam client's own suspend store.
 *
 * Steam runs every sleep through one store (window.SuspendResumeStore):
 *
 *   power menu "Sleep" -> RequestSleep() -> SleepManager -> OnRequestSuspend()
 *     -> InitiateSleep() -> OnSuspendRequest(): sets `suspending`, then
 *        PrepareForSystemSuspend(), then SuspendPC()
 *
 * The moment `suspending` is set, Steam mounts its suspend dialog over the whole
 * interface, and only a real resume takes it down again. So the sleep is taken over
 * before that point: RequestSleep is the power menu's own entry, and InitiateSleep is
 * where every other sleep request (idle timer, Steam's own dialogs) arrives. Neither is
 * a MobX action, so they can be replaced on the instance.
 *
 * When the plugin has no business with a sleep, the original method runs and SteamOS
 * sleeps exactly as it does without this plugin. When the store cannot be found (a
 * Steam build that reorganised it), nothing is patched and Sleep stays stock; the
 * physical power button is handled by the backend either way.
 */
const isSuspendStore = (candidate) => typeof candidate?.RequestSleep === "function" &&
    typeof candidate?.InitiateSleep === "function" &&
    typeof candidate?.OnSuspendRequest === "function";
const findSuspendStore = () => {
    const global = window.SuspendResumeStore;
    if (isSuspendStore(global))
        return global;
    try {
        return DFL.findModuleExport((e) => isSuspendStore(e)) ?? null;
    }
    catch (e) {
        return null;
    }
};
let patches = [];
/** One sleep the backend is still deciding on, so a repeat of it is not decided twice. */
let decidingUntil = 0;
/** The last sleep taken over, so the repeats of that same sleep are swallowed. */
let lastTakeover = 0;
const isDownloading = () => {
    const info = getState().downloadInfo;
    return Boolean(info.is_downloading && !info.is_paused);
};
/** Whether the plugin would turn this sleep into its own mode at all. */
const pluginWantsSleep = () => isDownloading() || getState().settings.standby_on_power_off === true;
/**
 * What every request does before anything is decided: get out of the way, be the way
 * out of our own mode, or be swallowed because a takeover is already under way.
 * Returns undefined when the request still has to be decided on.
 */
const preflight = (via) => {
    if (Date.now() < runtime.realSuspendUntil || !isPluginEnabled()) {
        return "original";
    }
    const s = getState();
    if (s.isBackgroundMode) {
        wakeIfSettled(`${via}_wake`);
        return "handled";
    }
    const now = Date.now();
    if (s.showSplash ||
        s.showHud ||
        now < runtime.wakeCooldownUntil ||
        now < decidingUntil ||
        now - lastTakeover < 2000) {
        return "handled";
    }
    if (!pluginWantsSleep()) {
        return "original";
    }
    return undefined;
};
/**
 * Sleep chosen in the power menu: does exactly what the physical power button does,
 * through the same backend call.
 */
const onRequestSleep = () => {
    const pre = preflight("menu_suspend");
    debugLog({ kind: "sleep_request", via: "RequestSleep", decision: pre ?? "takeover" });
    if (pre === "original")
        return DFL.callOriginal;
    if (pre === "handled")
        return undefined;
    lastTakeover = Date.now();
    console.log("[NewSuspendMode] Power menu Sleep -> new suspend mode.");
    closeSteamSideMenus();
    call("request_standby", "standby_power_menu").catch((e) => console.error("[NewSuspendMode] request_standby failed:", e));
    return undefined;
};
/**
 * Every other sleep request. The backend decides on the state it re-reads right now:
 * 'allow' hands the sleep back to Steam, 'hud' shows the download card, and for
 * 'standby' the backend starts the splash itself.
 */
const onInitiateSleep = (store, args) => {
    // suppress_actual_suspend: Steam is only preparing for a suspend that the system is
    // already carrying out, and will not suspend anything itself.
    if (args[0] === true)
        return DFL.callOriginal;
    const pre = preflight("initiate_sleep");
    debugLog({ kind: "sleep_request", via: "InitiateSleep", decision: pre ?? "takeover" });
    if (pre === "original")
        return DFL.callOriginal;
    if (pre === "handled")
        return undefined;
    // The patch's original when it is still in place; the store's own method once the
    // plugin has been unloaded and the patch taken off.
    const runOriginal = () => {
        try {
            const original = patches.find((p) => p.property === "InitiateSleep")?.original ?? store.InitiateSleep;
            original.apply(store, args);
        }
        catch (e) {
            console.error("[NewSuspendMode] Could not hand the sleep back to Steam:", e);
        }
    };
    decidingUntil = Date.now() + 15000;
    closeSteamSideMenus();
    call("trigger_suspend_intercept")
        .then((res) => {
        decidingUntil = 0;
        const verdict = String(res?.verdict ?? "");
        console.log(`[NewSuspendMode] Sleep verdict: ${verdict}`);
        if (verdict === "allow") {
            runOriginal();
            return;
        }
        lastTakeover = Date.now();
        if (verdict === "hud") {
            startHudCountdown(getState().settings.hud_timeout_seconds ?? 5);
        }
    })
        .catch((e) => {
        decidingUntil = 0;
        console.error("[NewSuspendMode] trigger_suspend_intercept failed:", e);
        runOriginal();
    });
    return undefined;
};
const tryInstall = () => {
    const store = findSuspendStore();
    if (!store)
        return false;
    // Whatever goes wrong in here, the console must still be able to sleep.
    const guarded = (handler) => (args) => {
        try {
            return handler(args);
        }
        catch (e) {
            console.error("[NewSuspendMode] Sleep patch failed, falling back to SteamOS:", e);
            return DFL.callOriginal;
        }
    };
    patches = [
        DFL.replacePatch(store, "RequestSleep", guarded(() => onRequestSleep())),
        DFL.replacePatch(store, "InitiateSleep", guarded((args) => onInitiateSleep(store, args))),
    ];
    console.log("[NewSuspendMode] Sleep patched on the Steam suspend store.");
    return true;
};
/**
 * Patches the suspend store, retrying for a while in case it is not there yet.
 * Returns the function that takes the patches off again.
 */
const installSleepPatch = () => {
    let attempts = 0;
    let timer = null;
    const attempt = () => {
        timer = null;
        let installed = false;
        try {
            installed = tryInstall();
        }
        catch (e) {
            console.warn("[NewSuspendMode] Could not patch the Steam suspend store:", e);
        }
        if (installed) {
            debugLog({ kind: "sleep_patch", installed: true, attempts: attempts + 1 });
            return;
        }
        if (++attempts < 6) {
            timer = setTimeout(attempt, 3000);
        }
        else {
            console.warn("[NewSuspendMode] Steam suspend store not found; Sleep stays stock.");
            debugLog({ kind: "sleep_patch", installed: false, attempts });
        }
    };
    attempt();
    return () => {
        if (timer)
            clearTimeout(timer);
        for (const patch of patches) {
            try {
                patch.unpatch();
            }
            catch (e) { }
        }
        patches = [];
    };
};

var index = definePlugin(() => {
    // The HUD, the standby splash and the black screen, drawn over the whole interface.
    routerHook.addGlobalComponent("NewSuspendModeOverlay", GlobalOverlay);
    const stopListening = listenToBackend();
    const stopWatchingDownloads = watchSteamDownloads();
    const removeSleepPatch = installSleepPatch();
    const stopSync = startBackendSync();
    return {
        name: "New Suspend Mode",
        icon: SP_JSX.jsx(FaDownload, {}),
        content: SP_JSX.jsx(PluginContent, {}),
        onDismount() {
            routerHook.removeGlobalComponent("NewSuspendModeOverlay");
            stopSync();
            removeSleepPatch();
            stopWatchingDownloads();
            stopListening();
            stopFlowTimers();
        },
    };
});

export { index as default };
//# sourceMappingURL=index.js.map
