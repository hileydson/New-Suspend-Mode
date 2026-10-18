const manifest = {"name":"Download in Background"};
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
    // If neither HUD nor blackout is active, do not render anything
    if (!showHud && !isBackgroundMode) {
        return null;
    }
    // Pure black screen mode. With nothing downloading there is no HUD to show, so the
    // plugin mark appears for a moment to say which standby this is, then fades to black.
    if (isBackgroundMode) {
        return (SP_JSX.jsx("div", { className: "dib-overlay-container dib-overlay-blackout", tabIndex: -1, "aria-hidden": "true", children: showSplash && (SP_JSX.jsxs("div", { className: "dib-splash", children: [SP_JSX.jsx(FaDownload, { className: "dib-splash-icon" }), SP_JSX.jsx("div", { className: "dib-splash-title", children: "Download in Background" }), SP_JSX.jsx("div", { className: "dib-splash-subtitle", children: "Standby \u00B7 press POWER or use a controller to wake" })] })) }));
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
    return (SP_JSX.jsx("div", { className: "dib-overlay-container dib-overlay-hud", children: SP_JSX.jsxs("div", { className: "dib-hud-card", children: [SP_JSX.jsxs("div", { className: "dib-hud-header", children: [SP_JSX.jsxs("div", { className: "dib-hud-title-box", children: [SP_JSX.jsx(FaDownload, { className: "dib-hud-icon" }), SP_JSX.jsxs("div", { children: [SP_JSX.jsx("div", { className: "dib-hud-title", children: "Download in Background" }), SP_JSX.jsx("div", { className: "dib-hud-subtitle", children: "System entering low-power mode to continue downloads" })] })] }), SP_JSX.jsxs("div", { className: "dib-countdown-badge", children: [SP_JSX.jsx(FaMoon, {}), "Screen off in ", countdown, "s"] })] }), SP_JSX.jsxs("div", { className: "dib-game-info", children: [SP_JSX.jsx("div", { className: "dib-game-title", children: gameTitle }), SP_JSX.jsx("div", { className: "dib-progress-container", children: SP_JSX.jsx("div", { className: "dib-progress-bar", style: { width: `${percent > 0 ? percent : 2}%` } }) }), SP_JSX.jsxs("div", { className: "dib-metrics-row", children: [SP_JSX.jsxs("div", { className: "dib-metric-item", children: [SP_JSX.jsx("span", { children: "Speed:" }), SP_JSX.jsx("span", { className: "dib-metric-value", children: formatSpeed(downloadInfo.bytes_per_second) })] }), SP_JSX.jsxs("div", { className: "dib-metric-item", children: [SP_JSX.jsx("span", { children: "Progress:" }), SP_JSX.jsxs("span", { className: "dib-metric-value", children: [percent.toFixed(1), "% (", formatSize(downloadInfo.completed_bytes), " / ", formatSize(downloadInfo.total_bytes), ")"] })] }), SP_JSX.jsxs("div", { className: "dib-metric-item", children: [SP_JSX.jsx("span", { children: "Time Left:" }), SP_JSX.jsx("span", { className: "dib-metric-value", children: formatTime(downloadInfo.estimated_seconds_remaining) })] })] })] }), SP_JSX.jsxs("div", { className: "dib-status-badges", children: [SP_JSX.jsxs("div", { className: "dib-badge", children: [SP_JSX.jsx(FaBatteryThreeQuarters, { className: `dib-badge-icon ${batteryCapacity <= 20 ? "warning" : ""}` }), SP_JSX.jsxs("div", { children: [SP_JSX.jsx("div", { className: "dib-badge-title", children: "Battery Level" }), SP_JSX.jsxs("div", { className: "dib-badge-val", children: [batteryCapacity, "% ", isCharging ? "(Charging)" : ""] })] })] }), SP_JSX.jsxs("div", { className: "dib-badge", children: [SP_JSX.jsx(FaBolt, { className: "dib-badge-icon" }), SP_JSX.jsxs("div", { children: [SP_JSX.jsx("div", { className: "dib-badge-title", children: "Auto-Suspend Threshold" }), SP_JSX.jsxs("div", { className: "dib-badge-val", children: ["At \u2264 ", settings.min_battery_threshold, "% or on finish"] })] })] })] }), SP_JSX.jsxs("div", { className: "dib-hud-actions", children: [SP_JSX.jsx("button", { className: "dib-btn-primary", onClick: onEnterBlackout, children: "Turn Off Screen Now" }), SP_JSX.jsxs("button", { className: "dib-btn-secondary", onClick: onWake, children: [SP_JSX.jsx(FaTimes, { style: { marginRight: 6 } }), " Cancel & Keep Awake"] })] }), SP_JSX.jsx("div", { className: "dib-hud-footer", children: "Screen turns off automatically. Press the POWER button at any time to wake console back to normal." })] }) }));
};

const SettingsPanel = ({ settings, setSettings, downloadInfo, isBackgroundMode, standbyMode, batteryCapacity, isCharging, powerPlugged, }) => {
    const updateSetting = async (key, val) => {
        const updated = { ...settings, [key]: val };
        setSettings(updated);
        try {
            await call("save_settings", updated);
        }
        catch (e) {
            console.error("[DownloadInBackground] Error saving settings:", e);
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
    return (SP_JSX.jsxs("div", { children: [SP_JSX.jsxs(DFL.PanelSection, { title: "Download & System Status", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.Field, { label: "Download Status", description: isDownloading
                                ? `${downloadInfo.game_title || "Steam Download"} (${formatSpeed(downloadInfo.bytes_per_second)})`
                                : isPaused
                                    ? `${downloadInfo.game_title ? downloadInfo.game_title + " (Paused)" : "Downloads paused"}`
                                    : "No active downloads", children: SP_JSX.jsx("span", { className: `dib-status-tag ${isDownloading ? "downloading" : isPaused ? "paused" : "idle"}`, children: isDownloading ? "DOWNLOADING" : isPaused ? "PAUSED" : "IDLE" }) }) }), (isDownloading || (isPaused && downloadInfo.total_bytes > 0)) && (SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsxs("div", { style: { width: "100%", margin: "4px 0" }, children: [SP_JSX.jsxs("div", { style: {
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
                                    : "Inactive (Normal operation)", children: SP_JSX.jsx("span", { className: `dib-status-tag ${isBackgroundMode ? "active" : "idle"}`, children: standbyMode ? "STANDBY" : isBackgroundMode ? "ACTIVE" : "IDLE" }) }) })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Behavior Settings", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Enable Plugin", description: "Intercepts suspend when downloading, turns off screen, and saves power.", checked: settings.enabled, onChange: (checked) => updateSetting("enabled", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Auto-Suspend Battery Threshold", description: "Console suspends automatically if battery drops below this limit during download.", value: settings.min_battery_threshold, min: 5, max: 30, step: 1, showValue: true, valueSuffix: "%", onChange: (val) => updateSetting("min_battery_threshold", val) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "HUD Display Countdown", description: "Seconds the download card shows on screen before turning display off.", value: settings.hud_timeout_seconds, min: 0, max: 15, step: 1, showValue: true, valueSuffix: "s", onChange: (val) => updateSetting("hud_timeout_seconds", val) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Completion Suspend Delay", description: "Seconds to wait after all downloads complete before automatically sleeping.", value: settings.auto_suspend_delay_seconds, min: 30, max: 600, step: 30, showValue: true, valueSuffix: "s", onChange: (val) => updateSetting("auto_suspend_delay_seconds", val) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Block All Input While Screen Is Off", description: "Freezes button mapping and disconnects external controllers so only the power button responds. Turn off if a controller misbehaves after waking.", checked: settings.deep_input_lockout, onChange: (checked) => updateSetting("deep_input_lockout", checked) }) })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Power Saving & Screen Options", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Turn Off Display Backlight", description: "Physically drops LCD/OLED panel backlight brightness to 0.", checked: settings.turn_off_backlight, onChange: (checked) => updateSetting("turn_off_backlight", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Pitch Black OLED Mode", description: "Presents a pure black overlay, shutting off individual OLED pixels.", checked: settings.oled_black_screen, onChange: (checked) => updateSetting("oled_black_screen", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Throttle CPU to Powersave", description: "Switches power profile to power-saver and lowers CPU clock frequencies.", checked: settings.throttle_cpu, onChange: (checked) => updateSetting("throttle_cpu", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Throttle GPU to 200MHz", description: "Sets AMD GPU performance level to low, minimizing GPU power draw.", checked: settings.throttle_gpu, onChange: (checked) => updateSetting("throttle_gpu", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Mute Audio While Screen Off", description: "Silences audio output during background download to prevent disturbance.", checked: settings.mute_audio, onChange: (checked) => updateSetting("mute_audio", checked) }) })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Standby & Controller Wake", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Replace Sleep With Standby", description: "The power button AND the Sleep option in the SteamOS power menu both enter the plugin's standby instead of suspending: screen black, downloads carry on, a controller brings it back. Shut Down still powers off for real.", checked: settings.standby_on_power_off, onChange: (checked) => updateSetting("standby_on_power_off", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.Field, { label: "What You Will See", description: settings.standby_on_power_off
                                ? "Downloading: the download card, then black. Nothing downloading: just the plugin logo, then black."
                                : "Standby off: sleep is intercepted only while a download is active, and the download card is shown." }) }), settings.standby_on_power_off && (SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Wake When A Bluetooth Pad Connects", description: "Bluetooth stays on in standby. Turning a paired controller on is enough to wake the console, no button needed.", checked: settings.wake_on_bluetooth_connect, onChange: (checked) => updateSetting("wake_on_bluetooth_connect", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Wake On Controller Button", description: "For USB and dongle controllers, connecting is not enough: press Guide/Home, Select or Start to wake. The console's own buttons stay dead - only power works there.", checked: settings.wake_on_controller_button, onChange: (checked) => updateSetting("wake_on_controller_button", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.Field, { label: "Battery In Standby", description: `Standby keeps the console powered, so it does use battery. It drops to a real suspend at ${settings.min_battery_threshold}% to protect it.` }) })] }))] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Download Pace (Fan & Heat)", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Slow Down Download", description: "Caps incoming speed so there is far less to decompress and write. Downloads take longer, the console stays cold and the fans stay off.", checked: settings.limit_download_speed, onChange: (checked) => updateSetting("limit_download_speed", checked) }) }), settings.limit_download_speed && (SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Download Speed Cap", description: "Lower is quieter and cooler. 6 MB/s still downloads about 21 GB per hour.", value: settings.download_speed_limit_mbps, min: 1, max: 30, step: 1, showValue: true, valueSuffix: " MB/s", onChange: (val) => updateSetting("download_speed_limit_mbps", val) }) })), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Steam CPU Budget", description: "Hard limit on the CPU Steam may use while the screen is off, as a share of one core. This is what keeps the chip cool enough for the fans to idle.", value: settings.download_cpu_percent, min: 0, max: 100, step: 5, showValue: true, valueSuffix: "%", onChange: (val) => updateSetting("download_cpu_percent", val) }) })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Troubleshooting", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Also Disconnect Built-In Controller", description: "EXPERIMENTAL. Only enable if buttons still act while the screen is off. Detaches the built-in pad's raw HID interface, which crashed the session on some consoles.", checked: settings.block_controller_hidraw, onChange: (checked) => updateSetting("block_controller_hidraw", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Write Diagnostic Logs", description: "Records the full input and thermal picture to the plugin log on every screen-off. Leave on while tuning.", checked: settings.debug_logging, onChange: (checked) => updateSetting("debug_logging", checked) }) })] })] }));
};

const PLUGIN_STYLES = `
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

const DEFAULT_SETTINGS = {
    enabled: true,
    min_battery_threshold: 15,
    hud_timeout_seconds: 5,
    auto_suspend_delay_seconds: 120,
    throttle_cpu: true,
    throttle_gpu: true,
    mute_audio: true,
    turn_off_backlight: true,
    oled_black_screen: true,
    deep_input_lockout: true,
    block_controller_hidraw: false,
    limit_download_speed: true,
    download_speed_limit_mbps: 6,
    download_cpu_percent: 30,
    debug_logging: true,
    standby_on_power_off: false,
    wake_on_bluetooth_connect: true,
    wake_on_controller_button: true,
};
// Must match WAKE_COOLDOWN_SECONDS in main.py: the window after a wake in which
// suspend requests are ignored, so the press that woke the console cannot re-sleep it.
const WAKE_COOLDOWN_MS = 5000;
// Backend round-trip cadence. While nothing is downloading the plugin polls slowly and
// sends nothing, so an enabled plugin with no download costs SteamOS nothing.
const POLL_ACTIVE_MS = 2000;
const POLL_IDLE_MS = 5000;
const POLL_DISABLED_MS = 10000;
const DEFAULT_DOWNLOAD_INFO = {
    is_downloading: false,
    bytes_per_second: 0,
    total_bytes: 0,
    completed_bytes: 0,
    progress_percent: 0,
    game_title: "Steam Game Download",
    estimated_seconds_remaining: 0,
};
// Global shared state for communication between QAM panel and Global Overlay
let sharedDownloadInfo = { ...DEFAULT_DOWNLOAD_INFO };
let sharedSettings = { ...DEFAULT_SETTINGS };
let sharedBatteryCapacity = 100;
let sharedIsCharging = false;
let sharedPowerPlugged = false;
let sharedIsBackgroundMode = false;
let sharedStandbyMode = false;
let sharedBackgroundModeEnteredTime = 0;
let sharedShowHud = false;
let sharedShowSplash = false;
let sharedSplashTimer = null;
let sharedCountdown = 5;
let sharedWakeCooldownUntil = 0;
let sharedHudTimer = null;
const stateListeners = new Set();
function notifyStateListeners() {
    stateListeners.forEach((cb) => cb());
}
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
 * Shows the plugin mark over the black screen for a moment.
 *
 * Used when standby replaces the system's own sleep and there is no download to put in
 * the HUD: something has to say which standby this is, since it looks identical to the
 * console being off.
 */
const showStandbySplash = (durationMs = 2500) => {
    sharedShowSplash = true;
    if (sharedSplashTimer) {
        clearTimeout(sharedSplashTimer);
    }
    sharedSplashTimer = setTimeout(() => {
        sharedShowSplash = false;
        sharedSplashTimer = null;
        notifyStateListeners();
    }, durationMs);
};
const clearStandbySplash = () => {
    if (sharedSplashTimer) {
        clearTimeout(sharedSplashTimer);
        sharedSplashTimer = null;
    }
    sharedShowSplash = false;
};
/**
 * Enters standby straight away, with the logo instead of the download HUD.
 *
 * This is the path taken when the user picks Sleep from the SteamOS power menu (or
 * presses power) with standby enabled and nothing downloading: there is no countdown to
 * show, the console is simply going off.
 */
const triggerEnterStandby = async (reason) => {
    if (Date.now() < sharedWakeCooldownUntil) {
        console.log("[DownloadInBackground] Wake cooldown active, not entering standby.");
        return;
    }
    if (sharedHudTimer) {
        clearInterval(sharedHudTimer);
        sharedHudTimer = null;
    }
    sharedShowHud = false;
    sharedIsBackgroundMode = true;
    sharedStandbyMode = true;
    sharedBackgroundModeEnteredTime = Date.now();
    showStandbySplash();
    notifyStateListeners();
    try {
        const success = await call("enter_background_mode", reason);
        if (success === false) {
            sharedIsBackgroundMode = false;
            clearStandbySplash();
            notifyStateListeners();
        }
    }
    catch (e) {
        console.error("[DownloadInBackground] Error entering standby:", e);
    }
};
/**
 * Triggers a complete system wake:
 * 1. Synchronously drops any black screen or HUD from the DOM
 * 2. Activates the cooldown against re-sleep
 * 3. Calls backend exit_background_mode to restore hardware/backlight
 * 4. Keeps dismissing any menu a stray button press may have opened
 */
const triggerFullWake = async (reason = "wake") => {
    console.log("[DownloadInBackground] triggerFullWake called! Reason:", reason);
    sharedIsBackgroundMode = false;
    sharedShowHud = false;
    sharedStandbyMode = false;
    sharedWakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;
    clearStandbySplash();
    if (sharedHudTimer) {
        clearInterval(sharedHudTimer);
        sharedHudTimer = null;
    }
    // Instantly unmounts overlay from the DOM
    notifyStateListeners();
    closeSteamSideMenus();
    try {
        await call("exit_background_mode", reason);
    }
    catch (e) {
        console.error("[DownloadInBackground] Error calling exit_background_mode:", e);
    }
    toaster.toast({
        title: "Download in Background",
        body: "Console awakened!",
        duration: 2000,
    });
};
/**
 * Enters Pitch Black mode (download continuing in background)
 */
const triggerEnterBlackout = async (reason = "countdown_completed") => {
    if (Date.now() < sharedWakeCooldownUntil) {
        console.log("[DownloadInBackground] Wake cooldown active, blocking enter blackout.");
        return;
    }
    if (sharedHudTimer) {
        clearInterval(sharedHudTimer);
        sharedHudTimer = null;
    }
    sharedShowHud = false;
    sharedIsBackgroundMode = true;
    sharedBackgroundModeEnteredTime = Date.now();
    notifyStateListeners();
    try {
        const success = await call("enter_background_mode", reason);
        if (success === false) {
            // Backend rejected entry -> restore to normal
            sharedIsBackgroundMode = false;
            notifyStateListeners();
        }
    }
    catch (e) {
        console.error("[DownloadInBackground] Error entering background mode:", e);
    }
};
/**
 * Starts initial HUD Countdown before turning screen black
 */
const startHudCountdown = (customTimeout) => {
    if (sharedIsBackgroundMode || Date.now() < sharedWakeCooldownUntil) {
        return;
    }
    const timeoutSec = customTimeout ?? sharedSettings.hud_timeout_seconds ?? 5;
    if (timeoutSec <= 0) {
        triggerEnterBlackout("immediate");
        return;
    }
    if (sharedHudTimer) {
        clearInterval(sharedHudTimer);
    }
    sharedCountdown = timeoutSec;
    sharedShowHud = true;
    sharedIsBackgroundMode = false;
    notifyStateListeners();
    let remaining = timeoutSec;
    sharedHudTimer = setInterval(() => {
        remaining -= 1;
        sharedCountdown = remaining;
        notifyStateListeners();
        if (remaining <= 0) {
            if (sharedHudTimer) {
                clearInterval(sharedHudTimer);
                sharedHudTimer = null;
            }
            triggerEnterBlackout("countdown_completed");
        }
    }, 1000);
};
// Global Overlay Container Component registered in routerHook
const GlobalOverlayContainer = () => {
    const [, setTick] = SP_REACT.useState(0);
    SP_REACT.useEffect(() => {
        const update = () => setTick((t) => t + 1);
        stateListeners.add(update);
        return () => {
            stateListeners.delete(update);
        };
    }, []);
    // Intercept and swallow keyboard/gamepad navigation while in background mode
    SP_REACT.useEffect(() => {
        if (!sharedIsBackgroundMode)
            return;
        const blockInput = (e) => {
            e.stopPropagation();
            e.stopImmediatePropagation();
            e.preventDefault();
        };
        const events = [
            "keydown", "keyup", "keypress",
            "pointerdown", "pointerup", "pointermove",
            "touchstart", "touchend", "touchmove",
            "mousedown", "mouseup", "click", "contextmenu"
        ];
        events.forEach((ev) => window.addEventListener(ev, blockInput, true));
        return () => {
            events.forEach((ev) => window.removeEventListener(ev, blockInput, true));
        };
    }, [sharedIsBackgroundMode]);
    // CRITICAL: If NOT in background mode and NOT showing HUD: DO NOT RENDER ANYTHING!
    // This guarantees that once awakened, the black div is 100% UNMOUNTED from the DOM.
    if (!sharedIsBackgroundMode && !sharedShowHud && !sharedShowSplash) {
        return null;
    }
    return (SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsx("style", { children: PLUGIN_STYLES }), SP_JSX.jsx(Overlay, { isBackgroundMode: sharedIsBackgroundMode, showHud: sharedShowHud, showSplash: sharedShowSplash, countdown: sharedCountdown, downloadInfo: sharedDownloadInfo, settings: sharedSettings, batteryCapacity: sharedBatteryCapacity, isCharging: sharedIsCharging, onWake: () => triggerFullWake("overlay_wake"), onEnterBlackout: () => triggerEnterBlackout("manual_screen_off") })] }));
};
// Plugin Quick Access Menu Content
const PluginContent = () => {
    const [settings, setSettings] = SP_REACT.useState(sharedSettings);
    const [downloadInfo, setDownloadInfo] = SP_REACT.useState(sharedDownloadInfo);
    const [isBackgroundMode, setIsBackgroundMode] = SP_REACT.useState(sharedIsBackgroundMode);
    const [standbyMode, setStandbyMode] = SP_REACT.useState(sharedStandbyMode);
    const [batteryCapacity, setBatteryCapacity] = SP_REACT.useState(sharedBatteryCapacity);
    const [isCharging, setIsCharging] = SP_REACT.useState(sharedIsCharging);
    const [powerPlugged, setPowerPlugged] = SP_REACT.useState(sharedPowerPlugged);
    SP_REACT.useEffect(() => {
        const update = () => {
            setSettings(sharedSettings);
            setDownloadInfo(sharedDownloadInfo);
            setIsBackgroundMode(sharedIsBackgroundMode);
            setStandbyMode(sharedStandbyMode);
            setBatteryCapacity(sharedBatteryCapacity);
            setIsCharging(sharedIsCharging);
            setPowerPlugged(sharedPowerPlugged);
        };
        stateListeners.add(update);
        return () => {
            stateListeners.delete(update);
        };
    }, []);
    const handleUpdateSettings = (newSettings) => {
        sharedSettings = newSettings;
        setSettings(newSettings);
        notifyStateListeners();
    };
    return (SP_JSX.jsx(SettingsPanel, { settings: settings, setSettings: handleUpdateSettings, downloadInfo: downloadInfo, isBackgroundMode: isBackgroundMode, standbyMode: standbyMode, batteryCapacity: batteryCapacity, isCharging: isCharging, powerPlugged: powerPlugged }));
};
var index = definePlugin(() => {
    // Register global overlay in SteamOS DOM
    routerHook.addGlobalComponent("DownloadInBackgroundOverlay", GlobalOverlayContainer);
    let pollTimer = null;
    let pollStopped = false;
    let dlUnregister = null;
    let suspendUnregister = null;
    let modeUnregister = null;
    let suspendEventUnregister = null;
    let batteryCriticalUnregister = null;
    let downloadsCompletedUnregister = null;
    // Listen directly for background mode changes from Python backend
    try {
        modeUnregister = addEventListener("background_mode_changed", (data) => {
            console.log("[DownloadInBackground] background_mode_changed event received:", data);
            const isBg = typeof data === "boolean" ? data : Boolean(data?.is_background_mode);
            if (!isBg) {
                // System awakened from backend!
                sharedIsBackgroundMode = false;
                sharedShowHud = false;
                sharedWakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;
                if (sharedHudTimer) {
                    clearInterval(sharedHudTimer);
                    sharedHudTimer = null;
                }
                notifyStateListeners();
                closeSteamSideMenus();
            }
            else {
                sharedIsBackgroundMode = true;
                sharedBackgroundModeEnteredTime = Date.now();
                sharedShowHud = false;
                // Entered from the backend (power key, or Sleep caught by logind). With standby
                // on and nothing downloading there is no HUD to show, so show the logo instead.
                if (Boolean(data?.standby)) {
                    sharedStandbyMode = true;
                    if (!data?.has_download) {
                        showStandbySplash();
                    }
                }
                notifyStateListeners();
            }
        });
    }
    catch (e) {
        console.warn("[DownloadInBackground] Could not register background_mode_changed listener:", e);
    }
    // Listen for suspend intercepted events from backend
    try {
        suspendEventUnregister = addEventListener("on_suspend_intercepted", (data) => {
            console.log("[DownloadInBackground] on_suspend_intercepted event received:", data);
            const now = Date.now();
            if (sharedIsBackgroundMode) {
                // If already in background mode, this is a wake action!
                triggerFullWake("suspend_event_during_bg");
                return;
            }
            if (now < sharedWakeCooldownUntil) {
                console.log("[DownloadInBackground] Ignoring on_suspend_intercepted during wake cooldown.");
                return;
            }
            const timeoutSec = data?.hud_timeout ?? sharedSettings.hud_timeout_seconds ?? 5;
            startHudCountdown(timeoutSec);
        });
    }
    catch (e) {
        console.warn("[DownloadInBackground] Could not register on_suspend_intercepted listener:", e);
    }
    // Critical battery auto-suspend notification
    try {
        batteryCriticalUnregister = addEventListener("battery_critical_suspend", (data) => {
            toaster.toast({
                title: "Download in Background",
                body: `Battery reached ${data?.capacity ?? 15}%. Entering sleep now.`,
                duration: 4000,
                critical: true,
            });
        });
    }
    catch (e) { }
    // Downloads completed notification
    try {
        downloadsCompletedUnregister = addEventListener("downloads_completed_suspend", () => {
            toaster.toast({
                title: "Download in Background",
                body: "All downloads completed! Suspending console.",
                duration: 3500,
            });
        });
    }
    catch (e) { }
    // Last snapshot read straight from the Steam client, and when it was taken.
    // It is more accurate than the backend's own detection, but only while it is fresh.
    let lastFrontendInfo = null;
    let lastFrontendInfoTime = 0;
    // Sync state with Python backend
    const syncBackendStatus = async () => {
        try {
            const status = await call("get_status");
            if (status) {
                const backendIsBg = Boolean(status.is_background_mode);
                if (sharedIsBackgroundMode && !backendIsBg) {
                    console.log("[DownloadInBackground] Backend woke up -> Synchronizing frontend!");
                    sharedIsBackgroundMode = false;
                    sharedShowHud = false;
                    sharedWakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;
                    if (sharedHudTimer) {
                        clearInterval(sharedHudTimer);
                        sharedHudTimer = null;
                    }
                    notifyStateListeners();
                    closeSteamSideMenus();
                }
                else {
                    sharedIsBackgroundMode = backendIsBg;
                }
                sharedStandbyMode = Boolean(status.standby_mode);
                sharedBatteryCapacity = Number(status.battery_capacity ?? 100);
                sharedIsCharging = Boolean(status.is_charging);
                sharedPowerPlugged = Boolean(status.power_plugged);
                if (status.settings) {
                    sharedSettings = { ...sharedSettings, ...status.settings };
                }
                if (status.download_info) {
                    const frontendIsFresh = Date.now() - lastFrontendInfoTime < 6000;
                    sharedDownloadInfo =
                        frontendIsFresh && lastFrontendInfo
                            ? { ...status.download_info, ...lastFrontendInfo }
                            : { ...sharedDownloadInfo, ...status.download_info };
                }
                notifyStateListeners();
            }
        }
        catch (e) {
            console.error("[DownloadInBackground] Error polling backend status:", e);
        }
    };
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
    // Poll / Query SteamClient Downloads API
    const querySteamDownloads = async () => {
        if (sharedSettings.enabled === false) {
            return;
        }
        try {
            if (window.SteamClient?.Downloads?.GetDownloadOverview) {
                const overview = window.SteamClient.Downloads.GetDownloadOverview();
                if (overview) {
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
                    let gameTitle = overview.game_name ?? overview.app_name ?? overview.title;
                    if (!gameTitle && window.SteamClient?.Downloads?.GetQueue) {
                        const queue = window.SteamClient.Downloads.GetQueue();
                        if (Array.isArray(queue) && queue.length > 0) {
                            gameTitle = queue[0]?.display_name ?? queue[0]?.app_name ?? queue[0]?.name;
                        }
                    }
                    const isPaused = Boolean(overview.bIsPaused ||
                        overview.paused ||
                        overview.bPaused ||
                        overview.bQueuePaused ||
                        overview.is_paused ||
                        overview.m_bPaused);
                    let queuePaused = false;
                    if (window.SteamClient?.Downloads?.GetQueue) {
                        const queue = window.SteamClient.Downloads.GetQueue();
                        if (Array.isArray(queue)) {
                            if (queue.length === 0) {
                                queuePaused = true;
                            }
                            else {
                                const hasActiveUnpaused = queue.some((item) => (item.bDownloading || item.bIsDownloading || item.active) &&
                                    !item.bPaused &&
                                    !item.bIsPaused &&
                                    !item.paused);
                                if (!hasActiveUnpaused) {
                                    queuePaused = true;
                                }
                            }
                        }
                    }
                    const isDl = !isPaused &&
                        !queuePaused &&
                        (bps > 10000 || (overview.bIsDownloading === true && bps > 0));
                    const updatedInfo = {
                        is_downloading: isDl,
                        is_paused: isPaused || queuePaused,
                        bytes_per_second: isDl ? bps : 0,
                        total_bytes: totalBytes,
                        completed_bytes: completedBytes,
                        progress_percent: percent,
                        game_title: gameTitle || "Steam Download",
                        estimated_seconds_remaining: isDl ? etaSeconds : 0,
                    };
                    sharedDownloadInfo = updatedInfo;
                    lastFrontendInfo = updatedInfo;
                    lastFrontendInfoTime = Date.now();
                    notifyStateListeners();
                    // Sync download metrics to backend
                    pushDownloadStatus(updatedInfo);
                }
            }
        }
        catch (e) {
            // Quietly ignore if SteamClient isn't ready
        }
    };
    // Initialize SteamClient listeners if available
    try {
        if (window.SteamClient?.Downloads?.RegisterForDownloadOverviewChanges) {
            const reg = window.SteamClient.Downloads.RegisterForDownloadOverviewChanges((data) => {
                if (data) {
                    querySteamDownloads();
                }
            });
            if (reg && typeof reg.unregister === "function") {
                dlUnregister = reg.unregister;
            }
        }
    }
    catch (e) {
        console.warn("[DownloadInBackground] Could not register for download overview changes:", e);
    }
    // Hook Steam Client Suspend Request if available
    try {
        if (window.SteamClient?.System?.RegisterForOnSuspendRequest) {
            const reg = window.SteamClient.System.RegisterForOnSuspendRequest(async () => {
                console.log("[DownloadInBackground] SteamClient Suspend Request event received!");
                const now = Date.now();
                // 1. If currently in background mode, this suspend request is actually a WAKE request from the Power Button!
                if (sharedIsBackgroundMode) {
                    const timeInBg = Date.now() - sharedBackgroundModeEnteredTime;
                    if (timeInBg < 2000) {
                        console.log(`[DownloadInBackground] Ignoring suspend request in initial transition grace period (${timeInBg}ms).`);
                        return false;
                    }
                    console.log("[DownloadInBackground] Power button pressed while in background mode -> WAKING UP!");
                    await triggerFullWake("power_button_wake");
                    return false; // Prevent Steam from suspending
                }
                // 2. Cooldown check: ignore suspend request if the system just woke up
                if (now < sharedWakeCooldownUntil) {
                    console.log("[DownloadInBackground] Ignoring suspend request: within wake cooldown period.");
                    return false;
                }
                // 3. Plugin off: get out of the way immediately, no backend round-trip, so
                // SteamOS suspends with its own animation exactly as without this plugin.
                if (!sharedSettings.enabled) {
                    return true;
                }
                // 4. This is also the hook for Sleep chosen from the SteamOS power menu, not
                // just the physical button. With standby on, that sleep becomes our mode.
                const looksIdle = !sharedDownloadInfo.is_downloading || sharedDownloadInfo.is_paused;
                if (looksIdle && !sharedSettings.standby_on_power_off) {
                    console.log("[DownloadInBackground] No active download and standby off -> Allowing stock SteamOS suspend.");
                    return true;
                }
                // 5. Confirm against the Steam client before taking the suspend over
                await querySteamDownloads();
                const isDownloading = Boolean(sharedDownloadInfo.is_downloading && !sharedDownloadInfo.is_paused);
                if (!isDownloading && sharedSettings.standby_on_power_off) {
                    console.log("[DownloadInBackground] Sleep requested with standby enabled -> entering standby with logo.");
                    await triggerEnterStandby("standby_sleep_request");
                    return false;
                }
                if (isDownloading) {
                    console.log("[DownloadInBackground] Active download running -> Intercepting suspend and showing HUD");
                    try {
                        await call("trigger_suspend_intercept");
                    }
                    catch (e) {
                        console.error("[DownloadInBackground] Error calling trigger_suspend_intercept:", e);
                    }
                    startHudCountdown(sharedSettings.hud_timeout_seconds ?? 5);
                    return false; // Prevent suspend in SteamClient
                }
                console.log("[DownloadInBackground] Download is paused or idle -> Allowing normal Steam suspend without intercepting.");
                return true; // Allow suspend immediately
            });
            if (reg && typeof reg.unregister === "function") {
                suspendUnregister = reg.unregister;
            }
        }
    }
    catch (e) {
        console.warn("[DownloadInBackground] Could not hook SteamClient.System.RegisterForOnSuspendRequest:", e);
    }
    // Poll the backend on an adaptive schedule instead of a fixed 1.5s interval
    const scheduleNextPoll = () => {
        const isActive = sharedIsBackgroundMode ||
            sharedShowHud ||
            Boolean(sharedDownloadInfo.is_downloading && !sharedDownloadInfo.is_paused);
        const delay = !sharedSettings.enabled
            ? POLL_DISABLED_MS
            : isActive
                ? POLL_ACTIVE_MS
                : POLL_IDLE_MS;
        pollTimer = setTimeout(runPoll, delay);
    };
    const runPoll = async () => {
        try {
            await syncBackendStatus();
            await querySteamDownloads();
        }
        finally {
            if (!pollStopped) {
                scheduleNextPoll();
            }
        }
    };
    // Initial fetch, then keep polling
    runPoll();
    /**
     * Writes the Steam client's own API surface into the plugin log, once.
     *
     * Blocking input and pacing a download would both be far cleaner done through Steam
     * itself than through the kernel, but which methods exist varies by Steam build, and
     * there is no documentation for them. This records what this console actually offers
     * (look for anything about controllers/input, or a download rate limit) so the next
     * version can call it directly instead of working around it.
     */
    const dumpSteamApiSurface = () => {
        const sc = window.SteamClient;
        const keysOf = (obj) => {
            if (!obj)
                return null;
            try {
                const proto = Object.getPrototypeOf(obj);
                const names = new Set([
                    ...Object.keys(obj),
                    ...(proto ? Object.getOwnPropertyNames(proto) : []),
                ]);
                return Array.from(names).sort().slice(0, 400);
            }
            catch (e) {
                return ["<unreadable>"];
            }
        };
        const safeCall = (fn) => {
            try {
                return fn ? fn() : null;
            }
            catch (e) {
                return null;
            }
        };
        call("log_debug", {
            kind: "steamclient_api_surface",
            top_level: keysOf(sc),
            Downloads: keysOf(sc?.Downloads),
            Settings: keysOf(sc?.Settings),
            Input: keysOf(sc?.Input),
            System: keysOf(sc?.System),
            download_overview: safeCall(sc?.Downloads?.GetDownloadOverview?.bind(sc?.Downloads)),
        }).catch(() => { });
    };
    const apiDumpTimer = setTimeout(() => {
        if (sharedSettings.debug_logging !== false) {
            dumpSteamApiSurface();
        }
    }, 8000);
    // Kernel sleep resume detection via clock-jump heartbeat
    let lastHeartbeat = Date.now();
    const heartbeatInterval = setInterval(() => {
        const now = Date.now();
        const delta = now - lastHeartbeat;
        lastHeartbeat = now;
        // CRITICAL: Do NOT trigger clock jump wake if we are intentionally in background mode!
        // Background mode intentionally throttles CPU and browser threads, causing setInterval delays.
        // Clock-jump detection is ONLY meant to wake up from actual Linux kernel sleep.
        if (sharedIsBackgroundMode) {
            return;
        }
        if (delta > 15000) {
            console.log(`[DownloadInBackground] Kernel resume detected (delta=${delta}ms)! Enforcing wake state.`);
            sharedWakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;
            if (sharedHudTimer) {
                clearInterval(sharedHudTimer);
                sharedHudTimer = null;
            }
            sharedShowHud = false;
            sharedIsBackgroundMode = false;
            notifyStateListeners();
            call("exit_background_mode", "kernel_resume_clock_jump").catch(() => { });
        }
    }, 2000);
    return {
        name: "Download in Background",
        icon: SP_JSX.jsx(FaDownload, {}),
        content: SP_JSX.jsx(PluginContent, {}),
        onDismount() {
            routerHook.removeGlobalComponent("DownloadInBackgroundOverlay");
            pollStopped = true;
            if (pollTimer) {
                clearTimeout(pollTimer);
                pollTimer = null;
            }
            clearTimeout(apiDumpTimer);
            if (heartbeatInterval) {
                clearInterval(heartbeatInterval);
            }
            if (sharedHudTimer) {
                clearInterval(sharedHudTimer);
                sharedHudTimer = null;
            }
            if (dlUnregister) {
                try {
                    dlUnregister();
                }
                catch (e) { }
            }
            if (suspendUnregister) {
                try {
                    suspendUnregister();
                }
                catch (e) { }
            }
            if (modeUnregister) {
                try {
                    removeEventListener("background_mode_changed", modeUnregister);
                }
                catch (e) { }
            }
            if (suspendEventUnregister) {
                try {
                    removeEventListener("on_suspend_intercepted", suspendEventUnregister);
                }
                catch (e) { }
            }
            if (batteryCriticalUnregister) {
                try {
                    removeEventListener("battery_critical_suspend", batteryCriticalUnregister);
                }
                catch (e) { }
            }
            if (downloadsCompletedUnregister) {
                try {
                    removeEventListener("downloads_completed_suspend", downloadsCompletedUnregister);
                }
                catch (e) { }
            }
        },
    };
});

export { index as default };
//# sourceMappingURL=index.js.map
