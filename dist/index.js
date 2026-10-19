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
                            }, children: "Restore Hardware Now" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Advanced Features", description: "Reveals every tuning option: battery thresholds, per-component throttles, standby wake sources, download pace limits and troubleshooting toggles. Leave off for a short, friendly panel.", checked: advanced, onChange: (checked) => updateSetting("advanced_mode", checked) }) })] }), advanced && (SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsxs(DFL.PanelSection, { title: "Behavior", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Auto-Suspend Battery Threshold", description: "Console suspends automatically if battery drops below this limit during download.", value: settings.min_battery_threshold, min: 5, max: 30, step: 1, showValue: true, valueSuffix: "%", onChange: (val) => updateSetting("min_battery_threshold", val) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "HUD Display Countdown", description: "Seconds the download card shows on screen before turning display off.", value: settings.hud_timeout_seconds, min: 0, max: 15, step: 1, showValue: true, valueSuffix: "s", onChange: (val) => updateSetting("hud_timeout_seconds", val) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Completion Suspend Delay", description: "Seconds to wait after all downloads complete before automatically sleeping.", value: settings.auto_suspend_delay_seconds, min: 30, max: 600, step: 30, showValue: true, valueSuffix: "s", onChange: (val) => updateSetting("auto_suspend_delay_seconds", val) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Block All Input While Screen Is Off", description: "Freezes button mapping and disconnects external controllers so only the power button responds. Turn off if a controller misbehaves after waking.", checked: settings.deep_input_lockout, onChange: (checked) => updateSetting("deep_input_lockout", checked) }) })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Power Saving & Screen Options", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Turn Off Display Backlight", description: "Physically drops LCD/OLED panel backlight brightness to 0.", checked: settings.turn_off_backlight, onChange: (checked) => updateSetting("turn_off_backlight", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Pitch Black OLED Mode", description: "Presents a pure black overlay, shutting off individual OLED pixels.", checked: settings.oled_black_screen, onChange: (checked) => updateSetting("oled_black_screen", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Force TV Off (real no-signal)", description: "Desktop with a TV only. A black screen is still a valid HDMI signal, so the TV stays lit. This stops the video signal entirely by disabling the HDMI/DP connector, so the TV reports no signal and reaches its own standby. The built-in panel of a handheld is never touched. EXPERIMENTAL: on a single-display desktop the session becomes headless while in the mode \u2014 the same as unplugging the cable \u2014 so test it before relying on it.", checked: settings.tv_force_connector_off === true, onChange: (checked) => updateSetting("tv_force_connector_off", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Throttle CPU to Powersave", description: "Switches power profile to power-saver and lowers CPU clock frequencies.", checked: settings.throttle_cpu, onChange: (checked) => updateSetting("throttle_cpu", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Throttle GPU to 200MHz", description: "Sets AMD GPU performance level to low, minimizing GPU power draw.", checked: settings.throttle_gpu, onChange: (checked) => updateSetting("throttle_gpu", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Mute Audio While Screen Off", description: "Silences audio output during background download to prevent disturbance.", checked: settings.mute_audio, onChange: (checked) => updateSetting("mute_audio", checked) }) })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Standby Wake Sources", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.Field, { label: "What You Will See", description: settings.standby_on_power_off
                                        ? "Downloading: the download card, then black. Nothing downloading: just the plugin logo, then black."
                                        : "Standby off: sleep is intercepted only while a download is active, and the download card is shown." }) }), settings.standby_on_power_off && (SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Wake When A Bluetooth Pad Connects", description: "Bluetooth stays on in standby. Turning a paired controller on is enough to wake the console, no button needed.", checked: settings.wake_on_bluetooth_connect, onChange: (checked) => updateSetting("wake_on_bluetooth_connect", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Wake On Controller Button", description: "For USB and dongle controllers, connecting is not enough: press Guide/Home, Select or Start to wake. The console's own buttons stay dead - only power works there.", checked: settings.wake_on_controller_button, onChange: (checked) => updateSetting("wake_on_controller_button", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.Field, { label: "Battery In Standby", description: `Standby keeps the console powered, so it does use battery. It drops to a real suspend at ${settings.min_battery_threshold}% to protect it.` }) })] }))] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Download Pace (Fan & Heat)", children: [settings.limit_download_speed && (SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Download Speed Cap", description: "Lower is quieter and cooler. 6 MB/s still downloads about 21 GB per hour.", value: settings.download_speed_limit_mbps, min: 1, max: 30, step: 1, showValue: true, valueSuffix: " MB/s", onChange: (val) => updateSetting("download_speed_limit_mbps", val) }) })), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Steam CPU Budget", description: "Hard limit on the CPU Steam may use while the screen is off, as a share of one core. This is what keeps the chip cool enough for the fans to idle.", value: settings.download_cpu_percent, min: 0, max: 100, step: 5, showValue: true, valueSuffix: "%", onChange: (val) => updateSetting("download_cpu_percent", val) }) })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Troubleshooting", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Also Disconnect Built-In Controller", description: "EXPERIMENTAL. Only enable if buttons still act while the screen is off. Detaches the built-in pad's raw HID interface, which crashed the session on some consoles.", checked: settings.block_controller_hidraw, onChange: (checked) => updateSetting("block_controller_hidraw", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Recover The Interface On Wake", description: "If the screen is still blank after waking from a sleep started in the SteamOS power menu, navigates home and, as a last resort, reloads the Steam interface.", checked: settings.ui_recovery_on_wake !== false, onChange: (checked) => updateSetting("ui_recovery_on_wake", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Auto Restore Hardware After Wake", description: "Ten seconds after waking, if anything still looks capped at the plugin's own values (frequency, turbo, ryzenadj, platform profile), runs the same hard reset the button above does. Turn off if another tool manages your TDP and you prefer the button.", checked: settings.auto_hard_reset_after_wake !== false, onChange: (checked) => updateSetting("auto_hard_reset_after_wake", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Write Diagnostic Logs", description: "Records the full input and thermal picture to the plugin log on every screen-off. Leave on while tuning.", checked: settings.debug_logging, onChange: (checked) => updateSetting("debug_logging", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.Field, { label: "Restore Hardware Now \u2014 When to use it", description: "The button above puts every clock, power limit and speed cap back without rebooting, even ones left behind by a crash. It also re-enables turbo boost, makes the firmware re-apply the current power profile, and raises any CPU ceiling still below what the chip reports \u2014 so it will overrule another tool's TDP settings while it runs.", bottomSeparator: "none" }) })] })] }))] }));
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
    ui_recovery_on_wake: true,
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
 * The Steam UI route at the moment the power menu's Sleep was taken over.
 *
 * Picking Sleep is a UI action, unlike the power button: the menu is open and Steam's
 * own click handler may move the interface somewhere (and dim or blank it) before the
 * suspend call it ends with ever reaches us. If it did, the route is put back on wake;
 * if it did not, nothing happens, because the route will not have changed.
 */
let sharedRouteBeforeTakeover = null;
/**
 * True when the sleep came from the Steam interface (the power menu) rather than from
 * the physical power button. The button path is invisible to Steam and comes back clean;
 * the menu path is the one where Steam's own click handler has already touched the
 * interface before the plugin is consulted, so only it needs recovering afterwards.
 */
let sharedUiInitiatedSleep = false;
let sharedRecoveryTimers = [];
const clearRecoveryTimers = () => {
    sharedRecoveryTimers.forEach((t) => clearTimeout(t));
    sharedRecoveryTimers = [];
};
/**
 * The window the interface is actually drawn in.
 *
 * A plugin's own module scope lives in Steam's SharedJSContext, which is a hidden 1x1
 * window - measuring `window` from here reports a viewport of 1x1 and a 2x2 document,
 * which is what the console's log finally showed. The global component Decky mounts is
 * rendered into the real interface window, so that is where a DOM reference to it points,
 * and that is the only window worth looking at.
 */
let sharedUiWindow = null;
const uiWindow = () => sharedUiWindow ?? window;
const uiDocument = () => (sharedUiWindow ? sharedUiWindow.document : document);
/**
 * What is in the middle of the screen, as a comparable string.
 *
 * Recorded before the sleep and again after the wake. Comparing the two is a far better
 * signal than trying to decide whether a colour counts as "black": if the middle of the
 * screen is the same thing it was before, the interface is where it was and nothing
 * needs recovering, whatever it looks like.
 */
const centerSignature = () => {
    try {
        const win = uiWindow();
        const el = uiDocument().elementFromPoint(Math.round(win.innerWidth / 2), Math.round(win.innerHeight / 2));
        if (!el)
            return "none";
        if (typeof el.closest === "function" && el.closest(".nsm-overlay-container"))
            return "ours";
        const parent = el.parentElement;
        return [
            el.tagName,
            String(el.className ?? "").slice(0, 80),
            parent ? String(parent.className ?? "").slice(0, 80) : "",
        ].join("|");
    }
    catch (e) {
        return "error";
    }
};
/** Whether anything at all is readable in the middle of the screen. */
const centerHasContent = () => {
    try {
        const win = uiWindow();
        const el = uiDocument().elementFromPoint(Math.round(win.innerWidth / 2), Math.round(win.innerHeight / 2));
        let node = el;
        for (let depth = 0; node && depth < 4; depth++) {
            if ((node.textContent ?? "").trim().length > 0)
                return true;
            node = node.parentElement;
        }
        return false;
    }
    catch (e) {
        return true; // Unreadable means "do not touch anything"
    }
};
/**
 * The last signature taken while the interface was known to be healthy.
 *
 * Sampled by the status poll rather than at the moment the sleep is taken over: by then
 * Steam's own click handler may already have blanked its interface, and comparing the
 * broken state against itself would find nothing wrong.
 */
let sharedCenterBeforeSleep = null;
/**
 * Takes the plugin's own black overlay off the screen, without going through React.
 *
 * This is what the console's log finally caught: after waking, the element covering the
 * middle of the screen was `nsm-overlay-container nsm-overlay-blackout` - the plugin's
 * own blackout, still in the document, at z-index 9999999, while the plugin's state said
 * it had woken up. The state is what React renders from, so if that component does not
 * re-render, the black stays on screen for good. The side menus still worked because
 * Steam drives them with its own input handling, not with DOM events, so they drew on
 * top of a screen the plugin was blacking out.
 *
 * Waking up is not something to leave to a re-render that may never come, so the node is
 * hidden directly as well. Hidden rather than removed: removing a node React still owns
 * makes React throw the next time it touches it.
 */
const forceHideOverlayDom = () => {
    let hidden = 0;
    const docs = [];
    try {
        docs.push(uiDocument());
    }
    catch (e) { }
    try {
        if (!docs.includes(document))
            docs.push(document);
    }
    catch (e) { }
    for (const doc of docs) {
        try {
            const nodes = doc?.querySelectorAll?.(".nsm-overlay-container");
            if (!nodes)
                continue;
            Array.prototype.forEach.call(nodes, (node) => {
                node.style.display = "none";
                node.style.pointerEvents = "none";
                hidden += 1;
            });
        }
        catch (e) { }
    }
    if (hidden) {
        console.warn(`[NewSuspendMode] Overlay was still in the DOM on wake; hid ${hidden} node(s).`);
    }
    return hidden;
};
/** Undoes the above, so the overlay can be shown again next time. */
const clearOverlayDomOverrides = () => {
    const docs = [];
    try {
        docs.push(uiDocument());
    }
    catch (e) { }
    try {
        if (!docs.includes(document))
            docs.push(document);
    }
    catch (e) { }
    for (const doc of docs) {
        try {
            const nodes = doc?.querySelectorAll?.(".nsm-overlay-container");
            if (!nodes)
                continue;
            Array.prototype.forEach.call(nodes, (node) => {
                node.style.display = "";
                node.style.pointerEvents = "";
            });
        }
        catch (e) { }
    }
};
/**
 * Catches "Sleep" in the SteamOS power menu before Steam's own handler runs.
 *
 * This is the whole point: the power button works because Steam never finds out about
 * it, so there is nothing for Steam to do to its interface and nothing to put back.
 * Catching the methods Steam calls at the END of its sleep handler is too late - by then
 * it has already done whatever leaves the screen black. Catching the activation of the
 * menu item itself, in the capture phase, means Steam's handler never runs at all and
 * the two paths become the same path.
 *
 * Identified by the item's own text, so it works whatever Steam calls its internals this
 * week. Only ever armed when the plugin would take the sleep over anyway, so when it is
 * off or idle the menu behaves exactly as it always has.
 */
const SLEEP_LABELS = new Set([
    "sleep", "suspend", "suspender", "suspensao", "modo de suspensao", "dormir",
    "reposo", "suspender equipo", "ruhezustand", "energie sparen", "standby",
    "veille", "mettre en veille", "mise en veille", "sospendi", "sospensione",
    "slaapstand", "vilolage", "vilolage", "hvile", "dvale", "lepotila", "viloläge",
    "uyku", "uspij", "uspienie", "spiaci rezim", "rezim spanku",
    "спящий режим", "сон", "スリープ", "睡眠", "절전", "휴면",
]);
const normalizeLabel = (text) => text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
let menuGuardWindow = null;
let menuGuardHandler = null;
let lastMenuInterception = 0;
let activationsLogged = 0;
/**
 * The menu row under this event, if its text says it is the sleep entry.
 *
 * Runs on every click and key press while the plugin is armed, so it has to stay cheap:
 * reading `textContent` serializes an element's whole subtree, and `getBoundingClientRect`
 * forces the browser to lay the page out. Both are skipped unless the node is small
 * enough to be a menu row in the first place, and the rectangle is only measured once the
 * text has already matched.
 */
const sleepItemFromEvent = (target) => {
    let node = target;
    for (let depth = 0; node && depth < 5; depth++) {
        try {
            // A menu row holds a label, not a page. Anything bigger is not worth reading.
            if ((node.childElementCount ?? 0) <= 4) {
                const raw = String(node.textContent ?? "");
                if (raw.length > 0 && raw.length <= 40) {
                    const label = normalizeLabel(raw);
                    if (SLEEP_LABELS.has(label)) {
                        const rect = node.getBoundingClientRect?.();
                        const win = uiWindow();
                        if (!rect || (rect.height <= 200 && rect.width <= win.innerWidth * 0.7)) {
                            return { el: node, label };
                        }
                    }
                }
            }
        }
        catch (e) { }
        node = node.parentElement;
    }
    return null;
};
/** Does exactly what the physical power button does, through the same backend call. */
const takeOverSleepFromMenu = (label) => {
    lastMenuInterception = Date.now();
    // Steam's handler never ran, so its interface was never touched and there is nothing
    // to recover afterwards - the same situation as a press of the power button.
    sharedUiInitiatedSleep = false;
    sharedRouteBeforeTakeover = null;
    clearTakeover();
    closeSteamSideMenus();
    call("log_debug", { kind: "menu_sleep_intercepted", label }).catch(() => { });
    call("request_standby", "standby_power_menu").catch((e) => console.error("[NewSuspendMode] request_standby failed:", e));
};
const installMenuItemGuard = (win) => {
    if (!win || win === menuGuardWindow)
        return;
    removeMenuItemGuard();
    menuGuardHandler = (e) => {
        try {
            if (e.type === "keydown" && (e.repeat || (e.key !== "Enter" && e.key !== " ")))
                return;
            if (!sharedSettings.enabled)
                return;
            if (sharedIsBackgroundMode || sharedShowSplash || sharedShowHud)
                return;
            if (Date.now() < sharedWakeCooldownUntil)
                return;
            if (Date.now() - lastMenuInterception < 2000)
                return;
            if (Date.now() < sharedRealSuspendUntil)
                return;
            // Only when the plugin would take this sleep over anyway.
            const downloading = sharedDownloadInfo.is_downloading && !sharedDownloadInfo.is_paused;
            if (!downloading && !sharedSettings.standby_on_power_off)
                return;
            const hit = sleepItemFromEvent(e.target);
            if (!hit) {
                if (activationsLogged < 8 && sharedSettings.debug_logging !== false) {
                    activationsLogged += 1;
                    const t = String(e.target?.textContent ?? "").slice(0, 60);
                    call("log_debug", {
                        kind: "activation_seen",
                        event: e.type,
                        text: t,
                        cls: String(e.target?.className ?? "").slice(0, 80),
                    }).catch(() => { });
                }
                return;
            }
            console.log(`[NewSuspendMode] Power menu "${hit.label}" caught before Steam saw it.`);
            e.stopImmediatePropagation();
            e.preventDefault();
            takeOverSleepFromMenu(hit.label);
        }
        catch (err) {
            console.error("[NewSuspendMode] Menu guard failed:", err);
        }
    };
    ["click", "keydown"].forEach((type) => {
        try {
            win.addEventListener(type, menuGuardHandler, true);
        }
        catch (e) { }
    });
    menuGuardWindow = win;
    console.log("[NewSuspendMode] Power menu guard installed on the interface window.");
};
const removeMenuItemGuard = () => {
    if (!menuGuardWindow || !menuGuardHandler)
        return;
    ["click", "keydown"].forEach((type) => {
        try {
            menuGuardWindow.removeEventListener(type, menuGuardHandler, true);
        }
        catch (e) { }
    });
    menuGuardWindow = null;
    menuGuardHandler = null;
};
/** How many of the plugin's overlay nodes are in the document right now. */
const overlayNodesInDom = () => {
    try {
        return uiDocument()?.querySelectorAll?.(".nsm-overlay-container")?.length ?? 0;
    }
    catch (e) {
        return 0;
    }
};
let lastCenterSample = 0;
const sampleHealthyCenter = () => {
    if (sharedIsBackgroundMode || sharedShowSplash || sharedShowHud)
        return;
    // elementFromPoint forces a layout, so this is kept well away from the poll cadence.
    if (Date.now() - lastCenterSample < 10000)
        return;
    lastCenterSample = Date.now();
    const sig = centerSignature();
    if (sig === "ours" || sig === "none" || sig === "error")
        return;
    sharedCenterBeforeSleep = sig;
};
/**
 * Tells the Steam client its suspend was called off, if it has a way to be told.
 *
 * Returning false from the suspend-request callback stops the suspend, but it does not
 * appear to walk Steam's own interface back out of the state it entered when it decided
 * to sleep - which is why a sleep started from the power menu comes back to a blank
 * screen while the power button, which Steam never hears about, comes back clean.
 *
 * Which method does that is not documented and differs between Steam builds, so this
 * looks for one whose name can only mean that, calls it, and records what it found. A
 * name has to mention cancelling or aborting AND suspending or sleeping to be called.
 */
const cancelSteamSuspendFlow = (request) => {
    const called = [];
    const tried = [];
    const wanted = /^(?=.*(cancel|abort))(?=.*(suspend|sleep)).*$/i;
    const methodNames = (obj) => {
        if (!obj)
            return [];
        try {
            const proto = Object.getPrototypeOf(obj);
            return Array.from(new Set([...Object.keys(obj), ...(proto ? Object.getOwnPropertyNames(proto) : [])]));
        }
        catch (e) {
            return [];
        }
    };
    // 1. The request object the callback is handed, if this build hands one over. A
    // cancel on the request itself is the most likely intended way to refuse.
    if (request && typeof request === "object") {
        for (const name of methodNames(request)) {
            if (typeof request[name] !== "function")
                continue;
            tried.push(`request.${name}`);
            if (!/^(cancel|abort|block|deny|reject|veto)/i.test(name))
                continue;
            try {
                request[name]();
                called.push(`request.${name}`);
            }
            catch (e) { }
        }
    }
    // 2. A client-level "the suspend was cancelled" call.
    const sc = window.SteamClient;
    for (const group of ["System", "User", "UI"]) {
        for (const name of methodNames(sc?.[group])) {
            if (!wanted.test(name) || typeof sc[group][name] !== "function")
                continue;
            try {
                sc[group][name]();
                called.push(`${group}.${name}`);
            }
            catch (e) { }
        }
    }
    call("log_debug", {
        kind: "suspend_cancel_attempt",
        called,
        request_type: typeof request,
        request_members: request && typeof request === "object" ? tried : null,
        system: methodNames(sc?.System).filter((n) => /susp|sleep|resume|power/i.test(n)),
        user: methodNames(sc?.User).filter((n) => /susp|sleep|resume|power/i.test(n)),
        ui: methodNames(sc?.UI).filter((n) => /susp|sleep|resume|power|mode/i.test(n)),
    }).catch(() => { });
    if (called.length) {
        console.log(`[NewSuspendMode] Told Steam its suspend was cancelled via: ${called.join(", ")}`);
    }
    return called;
};
/**
 * Gets the Steam interface back after a sleep it started itself.
 *
 * Three steps, each only taken if the one before it did not help, because the screen
 * being black is the only evidence available and every step costs the user something:
 *   1. nothing (the ordinary wake already closed the menus and put the route back)
 *   2. navigate home, which remounts the main view
 *   3. reload the Steam interface, the last resort, and still far better than the reboot
 *      that is otherwise the only way out.
 */
const recoverSteamUi = () => {
    clearRecoveryTimers();
    if (!sharedUiInitiatedSleep || sharedSettings.ui_recovery_on_wake === false) {
        sharedUiInitiatedSleep = false;
        return;
    }
    const before = sharedCenterBeforeSleep;
    sharedRecoveryTimers.push(setTimeout(() => {
        // Our own overlay first: it is the cheapest and most precise thing to rule out,
        // and it was the actual cause of the black screen all along.
        if (overlayNodesInDom() > 0 && forceHideOverlayDom() > 0) {
            call("log_debug", { kind: "ui_recovery", step: "hid_stale_overlay" }).catch(() => { });
        }
        const after = centerSignature();
        // Unchanged middle of the screen means the interface is where it was.
        if (sharedIsBackgroundMode || (before && after === before)) {
            sharedUiInitiatedSleep = false;
            return;
        }
        console.warn(`[NewSuspendMode] Screen changed across the sleep (${before} -> ${after}) -> navigating home.`);
        call("log_debug", {
            kind: "ui_recovery", step: "navigate_home", before, after,
            has_content: centerHasContent(),
        }).catch(() => { });
        try {
            const nav = DFL.Navigation;
            if (typeof nav.NavigateToLibraryTab === "function")
                nav.NavigateToLibraryTab();
            else
                nav.Navigate?.("/library/home");
        }
        catch (e) {
            console.warn("[NewSuspendMode] Could not navigate home:", e);
        }
        sharedRecoveryTimers.push(setTimeout(() => {
            sharedUiInitiatedSleep = false;
            sharedCenterBeforeSleep = null;
            // The last resort needs two independent reasons to believe the interface is
            // broken: the middle of the screen is not what it was, AND there is nothing
            // readable there. A view that merely moved on still has content in it.
            if (sharedIsBackgroundMode)
                return;
            const after = centerSignature();
            if (before && after === before)
                return;
            if (centerHasContent()) {
                call("log_debug", {
                    kind: "ui_recovery", step: "skipped_reload", before, after, reason: "screen has content",
                }).catch(() => { });
                return;
            }
            const restart = window.SteamClient?.Browser?.RestartJSContext;
            console.warn("[NewSuspendMode] Screen STILL empty -> reloading the Steam UI.");
            call("log_debug", {
                kind: "ui_recovery",
                step: "restart_js_context",
                before,
                after,
                available: typeof restart === "function",
            }).catch(() => { });
            if (typeof restart !== "function")
                return;
            toaster.toast({
                title: "New Suspend Mode",
                body: "Reloading the Steam interface to finish waking up",
                duration: 3000,
            });
            try {
                restart();
            }
            catch (e) {
                console.error("[NewSuspendMode] Could not reload the Steam UI:", e);
            }
        }, 2500));
    }, 1500));
};
const currentUiRoute = () => {
    try {
        return window.location.pathname || null;
    }
    catch (e) {
        return null;
    }
};
const restoreUiRoute = () => {
    const target = sharedRouteBeforeTakeover;
    sharedRouteBeforeTakeover = null;
    if (!target)
        return;
    const now = currentUiRoute();
    if (!now || now === target)
        return;
    console.log(`[NewSuspendMode] Steam UI moved to ${now} on sleep; going back to ${target}.`);
    try {
        DFL.Navigation.Navigate?.(target);
    }
    catch (e) {
        console.warn("[NewSuspendMode] Could not restore the Steam UI route:", e);
    }
};
/**
 * Records what is actually on screen, for a wake that comes back only partially.
 *
 * The plugin's own overlay is unmounted synchronously on wake, and while it is up it
 * swallows every pointer and key event, so a screen that is black with working menus is
 * something else's. This names it: the elements under a handful of screen points, with
 * their background, opacity and stacking.
 */
const probeWakeScreen = (reason) => {
    if (sharedSettings.debug_logging === false) {
        return;
    }
    try {
        const points = [[0.5, 0.5], [0.5, 0.2], [0.5, 0.8]];
        const win = uiWindow();
        const doc = uiDocument();
        const samples = points.map(([fx, fy]) => {
            const x = Math.round(win.innerWidth * fx);
            const y = Math.round(win.innerHeight * fy);
            const chain = [];
            let node = doc.elementFromPoint(x, y);
            for (let depth = 0; node && depth < 5; depth++) {
                const cs = win.getComputedStyle(node);
                const rect = node.getBoundingClientRect();
                chain.push({
                    tag: node.tagName,
                    cls: String(node.className ?? "").slice(0, 120),
                    bg: cs.backgroundColor,
                    opacity: cs.opacity,
                    z: cs.zIndex,
                    pos: cs.position,
                    vis: cs.visibility,
                    display: cs.display,
                    size: [Math.round(rect.width), Math.round(rect.height)],
                });
                node = node.parentElement;
            }
            return { at: [fx, fy], chain };
        });
        call("log_debug", {
            kind: "wake_screen_probe",
            reason,
            route: currentUiRoute(),
            route_at_takeover: sharedRouteBeforeTakeover,
            visibility: doc.visibilityState,
            hidden: doc.hidden,
            viewport: [win.innerWidth, win.innerHeight],
            ui_window: sharedUiWindow ? "interface" : "shared_context_fallback",
            overlay_in_dom: overlayNodesInDom(),
            overlay_state: {
                background_mode: sharedIsBackgroundMode,
                show_hud: sharedShowHud,
                show_splash: sharedShowSplash,
                standby: sharedStandbyMode,
            },
            samples,
        }).catch(() => { });
    }
    catch (e) {
        console.warn("[NewSuspendMode] Wake screen probe failed:", e);
    }
};
const clearStandbySplash = () => {
    if (sharedSplashTimer) {
        clearTimeout(sharedSplashTimer);
        sharedSplashTimer = null;
    }
    sharedShowSplash = false;
};
/**
 * Everything the interface has to undo on wake, shared by both ways a wake arrives:
 * this side asking for it, and the backend announcing it already happened.
 *
 * It used to be written out twice, and the backend's copy was the shorter one: it never
 * cleared the standby splash or the standby flag, so a wake that came from the backend
 * could leave state behind that the plugin's own overlay is drawn from.
 */
const finishWakeUi = (reason) => {
    const steamWasInvolved = sharedUiInitiatedSleep;
    sharedIsBackgroundMode = false;
    sharedShowHud = false;
    sharedStandbyMode = false;
    sharedWakeCooldownUntil = Date.now() + WAKE_COOLDOWN_MS;
    clearStandbySplash();
    clearTakeover();
    // If this sleep came from the Steam interface, Steam prepared for a suspend that never
    // happened. This is the call it would have made itself on a real resume.
    if (steamWasInvolved) {
        resumeSteamFromPreparedSuspend();
    }
    if (sharedHudTimer) {
        clearInterval(sharedHudTimer);
        sharedHudTimer = null;
    }
    // Unmounts the overlay from the DOM before anything else is attempted...
    notifyStateListeners();
    // ...and then makes sure it is actually gone, whether or not React obliged. Repeated,
    // because a component that re-renders late can put it back on screen.
    forceHideOverlayDom();
    // Not tracked with the recovery timers on purpose: those are cleared further down.
    [120, 400, 1200].forEach((delay) => setTimeout(() => {
        if (!sharedIsBackgroundMode && !sharedShowHud && !sharedShowSplash) {
            forceHideOverlayDom();
        }
    }, delay));
    closeSteamSideMenus();
    // Records what is on screen while it is still wrong, then puts the interface back
    // where it was if Steam's own sleep handler moved it.
    probeWakeScreen(reason);
    restoreUiRoute();
    // A nudge for anything that stopped repainting while the screen was off.
    try {
        uiWindow().dispatchEvent(new Event("resize"));
    }
    catch (e) { }
    // Only for a sleep the Steam interface started itself, and only if it is still blank.
    recoverSteamUi();
};
/**
 * Enters standby, replacing the HUD with nothing: the splash has already been shown.
 */
const triggerEnterStandby = async (reason) => {
    if (Date.now() < sharedWakeCooldownUntil) {
        console.log("[NewSuspendMode] Wake cooldown active, not entering standby.");
        return;
    }
    if (sharedHudTimer) {
        clearInterval(sharedHudTimer);
        sharedHudTimer = null;
    }
    clearStandbySplash();
    sharedShowHud = false;
    sharedIsBackgroundMode = true;
    sharedStandbyMode = true;
    sharedBackgroundModeEnteredTime = Date.now();
    clearOverlayDomOverrides(); // The wake hides the overlay node by hand; undo that first
    notifyStateListeners();
    try {
        const success = await call("enter_background_mode", reason);
        if (success === false) {
            sharedIsBackgroundMode = false;
            notifyStateListeners();
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
 * drawn after that is invisible. This mirrors the download HUD countdown, which is why
 * a download shows its card but standby used to appear to show nothing at all.
 */
const startStandbySplash = (seconds, reason = "standby_splash") => {
    if (sharedIsBackgroundMode || Date.now() < sharedWakeCooldownUntil) {
        return;
    }
    if (seconds <= 0) {
        triggerEnterStandby(reason);
        return;
    }
    if (sharedHudTimer) {
        clearInterval(sharedHudTimer);
        sharedHudTimer = null;
    }
    clearStandbySplash();
    sharedShowHud = false;
    sharedShowSplash = true;
    clearOverlayDomOverrides();
    notifyStateListeners();
    sharedSplashTimer = setTimeout(() => {
        sharedSplashTimer = null;
        triggerEnterStandby(reason);
    }, seconds * 1000);
};
/**
 * Triggers a complete system wake:
 * 1. Synchronously drops any black screen or HUD from the DOM
 * 2. Activates the cooldown against re-sleep
 * 3. Calls backend exit_background_mode to restore hardware/backlight
 * 4. Keeps dismissing any menu a stray button press may have opened
 */
const triggerFullWake = async (reason = "wake") => {
    console.log("[NewSuspendMode] triggerFullWake called! Reason:", reason);
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
/**
 * Enters Pitch Black mode (download continuing in background)
 */
const triggerEnterBlackout = async (reason = "countdown_completed") => {
    if (Date.now() < sharedWakeCooldownUntil) {
        console.log("[NewSuspendMode] Wake cooldown active, blocking enter blackout.");
        return;
    }
    if (sharedHudTimer) {
        clearInterval(sharedHudTimer);
        sharedHudTimer = null;
    }
    sharedShowHud = false;
    sharedIsBackgroundMode = true;
    sharedBackgroundModeEnteredTime = Date.now();
    clearOverlayDomOverrides();
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
        console.error("[NewSuspendMode] Error entering background mode:", e);
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
    clearOverlayDomOverrides();
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
/**
 * Takes over Sleep chosen from the SteamOS power menu, at the only point where it is
 * safe to do so.
 *
 * Blocking the suspend lower down does not work. By the time logind sees the request,
 * Steam has already begun its own suspend sequence and blanked the screen; making the
 * suspend fail there (an inhibitor, or a masked systemd sleep target) leaves the session
 * on a black, lit screen that it never comes back from. So the client's own suspend
 * entry points are wrapped instead, and Steam never starts that sequence at all.
 *
 * When the plugin has no business taking the sleep over, the original method is called
 * and SteamOS suspends exactly as it does without this plugin.
 */
const SUSPEND_METHODS = [
    // The one that actually puts the console to sleep.
    ["System", "SuspendPC"],
    ["System", "Suspend"],
    // And the one that runs FIRST. This is what the console's log finally showed: the
    // power menu calls User.PrepareForSystemSuspend() before SuspendPC(), and that call is
    // where Steam suspends the running games and moves its interface into its sleeping
    // state. Swallowing only SuspendPC stopped the suspend but left Steam prepared for one
    // that never happened, with nothing to undo it - the interface came back half dead.
    // The power button never goes through any of this, which is why it always came back clean.
    ["User", "PrepareForSystemSuspend"],
    ["User", "StartSuspend"],
    ["User", "SuspendPC"],
];
let suspendHooks = [];
let suspendPassThrough = false;
let sharedTakeover = null;
/** A real suspend the plugin itself asked for: every hook gets out of the way. */
let sharedRealSuspendUntil = 0;
const clearTakeover = () => {
    sharedTakeover = null;
};
const activeTakeover = () => {
    if (sharedTakeover && Date.now() > sharedTakeover.expires) {
        // A decision that never came back must never swallow sleeps forever.
        console.warn("[NewSuspendMode] Sleep decision timed out; forgetting it.");
        sharedTakeover = null;
    }
    return sharedTakeover;
};
/**
 * Undoes Steam's own preparation for a sleep that is not going to happen.
 *
 * ResumeSuspendedGames is the exact counterpart of PrepareForSystemSuspend, and it is
 * what Steam itself calls on a real resume. Harmless when nothing was suspended.
 */
const resumeSteamFromPreparedSuspend = () => {
    const user = window.SteamClient?.User;
    if (typeof user?.ResumeSuspendedGames !== "function")
        return false;
    try {
        user.ResumeSuspendedGames();
        console.log("[NewSuspendMode] Called User.ResumeSuspendedGames() to undo Steam's sleep preparation.");
        return true;
    }
    catch (e) {
        console.warn("[NewSuspendMode] ResumeSuspendedGames failed:", e);
        return false;
    }
};
/**
 * Calls the real Steam method. The flag covers the case of one suspend entry point
 * calling another one that is also wrapped, which would otherwise loop back in here.
 */
const callOriginalSuspend = (hook, args) => {
    suspendPassThrough = true;
    try {
        return hook.original.apply(hook.owner, args);
    }
    finally {
        setTimeout(() => {
            suspendPassThrough = false;
        }, 0);
    }
};
const handleMenuSuspend = (hook, args) => {
    // Logged on every single call, before any decision. Whether these hooks fire at all
    // for a sleep chosen in the power menu is the one thing the log could never answer,
    // and it decides where the fix has to go: if nothing appears here, the sleep is not
    // going through the Steam client methods this plugin wraps.
    call("log_debug", {
        kind: "sleep_hook_fired",
        method: hook.name,
        pass_through: suspendPassThrough,
        enabled: sharedSettings.enabled,
        in_background: sharedIsBackgroundMode,
        takeover: sharedTakeover?.state ?? null,
        standby: sharedSettings.standby_on_power_off,
        downloading: sharedDownloadInfo.is_downloading,
        paused: sharedDownloadInfo.is_paused,
    }).catch(() => { });
    // Our own pass-through, a real suspend the plugin asked for, or the plugin is off.
    if (suspendPassThrough || !sharedSettings.enabled || Date.now() < sharedRealSuspendUntil) {
        return callOriginalSuspend(hook, args);
    }
    // Our screen is already up: a sleep request now is the way out of it, not a new one.
    if (sharedIsBackgroundMode) {
        const timeInBg = Date.now() - sharedBackgroundModeEnteredTime;
        if (timeInBg >= 2000) {
            console.log(`[NewSuspendMode] ${hook.name} while in our mode -> waking up.`);
            triggerFullWake("menu_suspend_wake");
        }
        return Promise.resolve();
    }
    // One sleep, several calls: prepare and suspend both land here, and they must not be
    // decided on separately.
    const pending = activeTakeover();
    if (pending) {
        if (pending.state === "deciding") {
            pending.held.push({ hook, args });
            return Promise.resolve();
        }
        if (pending.state === "ours") {
            return Promise.resolve();
        }
        return callOriginalSuspend(hook, args);
    }
    // The splash or the HUD is already counting down into our mode, or the console only
    // just woke up: swallow it either way.
    if (sharedShowSplash || sharedShowHud || Date.now() < sharedWakeCooldownUntil) {
        return Promise.resolve();
    }
    // Nothing of ours would happen here, so do not even pause the menu: SteamOS sleeps
    // with its own animation, as if the plugin were not installed.
    const looksIdle = !sharedDownloadInfo.is_downloading || sharedDownloadInfo.is_paused;
    if (looksIdle && !sharedSettings.standby_on_power_off) {
        return callOriginalSuspend(hook, args);
    }
    // Taking this sleep over. Everything Steam asks for from here on is held until the
    // answer comes back, so the preparation never runs behind our back.
    sharedTakeover = { state: "deciding", held: [{ hook, args }], expires: Date.now() + 15000 };
    // Remember where the interface was, and dismiss the power menu that is still open.
    // Steam's own suspend flow would have taken it down; the power-button path, which
    // comes back clean, never has a menu open in the first place.
    sharedRouteBeforeTakeover = currentUiRoute();
    sharedUiInitiatedSleep = true;
    closeSteamSideMenus();
    // If Steam already prepared for the sleep before calling us, undo that preparation:
    // nothing else ever will, because the suspend it was preparing for is not happening.
    cancelSteamSuspendFlow();
    resumeSteamFromPreparedSuspend();
    // The backend decides, on state it re-reads right now rather than on the last poll,
    // and starts the standby splash itself when standby is what takes over.
    console.log(`[NewSuspendMode] Power menu sleep (${hook.name}) -> asking the backend.`);
    call("trigger_suspend_intercept")
        .then((res) => {
        const verdict = String(res?.verdict ?? "");
        console.log(`[NewSuspendMode] Power menu sleep verdict: ${verdict}`);
        if (verdict === "allow") {
            releaseHeldSleep();
        }
        else {
            // Only long enough to cover the follow-up calls of this same sleep. Any longer
            // and a second attempt - after cancelling the countdown, say - would be
            // swallowed in silence instead of being decided on again.
            if (sharedTakeover) {
                sharedTakeover.state = "ours";
                sharedTakeover.expires = Date.now() + 3000;
            }
            if (verdict === "hud") {
                startHudCountdown(sharedSettings.hud_timeout_seconds ?? 5);
            }
        }
    })
        .catch((e) => {
        console.error("[NewSuspendMode] trigger_suspend_intercept failed:", e);
        releaseHeldSleep();
    });
    return Promise.resolve();
};
/**
 * Not ours after all: let SteamOS have the whole sleep, in the order Steam asked for it,
 * so the preparation still happens before the suspend.
 */
const releaseHeldSleep = () => {
    const held = sharedTakeover?.held ?? [];
    sharedTakeover = { state: "none", held: [], expires: Date.now() + 3000 };
    sharedRouteBeforeTakeover = null;
    sharedUiInitiatedSleep = false;
    held.forEach(({ hook, args }) => callOriginalSuspend(hook, args));
    setTimeout(clearTakeover, 2000);
};
const installSuspendMethodHooks = () => {
    const sc = window.SteamClient;
    if (!sc || suspendHooks.length > 0) {
        return suspendHooks.length;
    }
    const hooked = [];
    for (const [group, name] of SUSPEND_METHODS) {
        const owner = sc[group];
        const original = owner?.[name];
        if (typeof original !== "function") {
            continue;
        }
        const hook = { owner, name: `${group}.${name}`, original };
        try {
            owner[name] = function (...args) {
                // Whatever goes wrong in here, the console must still be able to sleep.
                try {
                    return handleMenuSuspend(hook, args);
                }
                catch (e) {
                    console.error("[NewSuspendMode] Suspend hook failed, falling back to SteamOS:", e);
                    return callOriginalSuspend(hook, args);
                }
            };
            if (owner[name] === original) {
                // A read-only or proxied property: do not claim it was hooked.
                console.warn(`[NewSuspendMode] SteamClient.${group}.${name} could not be replaced.`);
                continue;
            }
            suspendHooks.push(hook);
            hooked.push(hook.name);
        }
        catch (e) {
            console.warn(`[NewSuspendMode] Could not hook SteamClient.${group}.${name}:`, e);
        }
    }
    console.log(`[NewSuspendMode] Suspend entry points hooked: ${hooked.join(", ") || "none"}`);
    call("log_debug", {
        kind: "suspend_hooks",
        hooked,
        system_methods: sc?.System ? Object.keys(sc.System).filter((k) => /susp|sleep|power/i.test(k)) : null,
        user_methods: sc?.User ? Object.keys(sc.User).filter((k) => /susp|sleep|power/i.test(k)) : null,
    }).catch(() => { });
    return suspendHooks.length;
};
const removeSuspendMethodHooks = () => {
    for (const hook of suspendHooks) {
        try {
            const [, name] = hook.name.split(".");
            hook.owner[name] = hook.original;
        }
        catch (e) { }
    }
    suspendHooks = [];
};
// Global Overlay Container Component registered in routerHook
const GlobalOverlayContainer = () => {
    const [, setTick] = SP_REACT.useState(0);
    const probeRef = SP_REACT.useRef(null);
    // Rendered in every state, including idle, so the plugin always has a reference into
    // the window the interface is really drawn in. Without it everything this plugin
    // measures about the screen describes Steam's hidden 1x1 scratch window instead.
    SP_REACT.useEffect(() => {
        const win = probeRef.current?.ownerDocument?.defaultView;
        if (!win)
            return;
        if (!sharedUiWindow || (win.innerWidth ?? 0) > (sharedUiWindow.innerWidth ?? 0)) {
            sharedUiWindow = win;
        }
        installMenuItemGuard(sharedUiWindow);
    });
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
        return SP_JSX.jsx("div", { ref: probeRef, style: { display: "none" } });
    }
    return (SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsx("div", { ref: probeRef, style: { display: "none" } }), SP_JSX.jsx("style", { children: PLUGIN_STYLES }), SP_JSX.jsx(Overlay, { isBackgroundMode: sharedIsBackgroundMode, showHud: sharedShowHud, showSplash: sharedShowSplash, countdown: sharedCountdown, downloadInfo: sharedDownloadInfo, settings: sharedSettings, batteryCapacity: sharedBatteryCapacity, isCharging: sharedIsCharging, onWake: () => triggerFullWake("overlay_wake"), onEnterBlackout: () => triggerEnterBlackout("manual_screen_off") })] }));
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
    routerHook.addGlobalComponent("NewSuspendModeOverlay", GlobalOverlayContainer);
    let pollTimer = null;
    let pollStopped = false;
    let dlUnregister = null;
    let suspendUnregister = null;
    let modeUnregister = null;
    let suspendEventUnregister = null;
    let standbyRequestUnregister = null;
    let batteryCriticalUnregister = null;
    let downloadsCompletedUnregister = null;
    // Listen directly for background mode changes from Python backend
    try {
        modeUnregister = addEventListener("background_mode_changed", (data) => {
            console.log("[NewSuspendMode] background_mode_changed event received:", data);
            const isBg = typeof data === "boolean" ? data : Boolean(data?.is_background_mode);
            if (!isBg) {
                // System awakened from the backend: same cleanup as a wake asked for here.
                finishWakeUi(String(data?.reason ?? "backend_wake"));
            }
            else {
                sharedIsBackgroundMode = true;
                sharedBackgroundModeEnteredTime = Date.now();
                sharedShowHud = false;
                clearStandbySplash();
                if (Boolean(data?.standby)) {
                    sharedStandbyMode = true;
                }
                notifyStateListeners();
            }
        });
    }
    catch (e) {
        console.warn("[NewSuspendMode] Could not register background_mode_changed listener:", e);
    }
    // Listen for suspend intercepted events from backend
    try {
        suspendEventUnregister = addEventListener("on_suspend_intercepted", (data) => {
            console.log("[NewSuspendMode] on_suspend_intercepted event received:", data);
            const now = Date.now();
            if (sharedIsBackgroundMode) {
                // If already in background mode, this is a wake action!
                triggerFullWake("suspend_event_during_bg");
                return;
            }
            if (now < sharedWakeCooldownUntil) {
                console.log("[NewSuspendMode] Ignoring on_suspend_intercepted during wake cooldown.");
                return;
            }
            const timeoutSec = data?.hud_timeout ?? sharedSettings.hud_timeout_seconds ?? 5;
            startHudCountdown(timeoutSec);
        });
    }
    catch (e) {
        console.warn("[NewSuspendMode] Could not register on_suspend_intercepted listener:", e);
    }
    // Backend asked for standby: draw the plugin mark first, then go dark
    try {
        standbyRequestUnregister = addEventListener("on_standby_requested", (data) => {
            console.log("[NewSuspendMode] on_standby_requested received:", data);
            if (sharedIsBackgroundMode) {
                return;
            }
            const seconds = Number(data?.splash_seconds ?? sharedSettings.hud_timeout_seconds ?? 5);
            startStandbySplash(seconds, String(data?.reason ?? "standby_splash"));
        });
    }
    catch (e) {
        console.warn("[NewSuspendMode] Could not register on_standby_requested listener:", e);
    }
    // Critical battery auto-suspend notification
    try {
        batteryCriticalUnregister = addEventListener("battery_critical_suspend", (data) => {
            // A suspend the plugin itself asked for: Steam must be allowed to prepare for it.
            sharedRealSuspendUntil = Date.now() + 60000;
            clearTakeover();
            toaster.toast({
                title: "New Suspend Mode",
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
            // Also a real suspend: let Steam suspend its games properly on the way down.
            sharedRealSuspendUntil = Date.now() + 60000;
            clearTakeover();
            toaster.toast({
                title: "New Suspend Mode",
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
                    console.log("[NewSuspendMode] Backend woke up -> Synchronizing frontend!");
                    finishWakeUi("status_poll_sync");
                }
                else {
                    sharedIsBackgroundMode = backendIsBg;
                }
                // Keep a picture of the interface while it is still working, for the recovery
                // check after a wake.
                sampleHealthyCenter();
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
            console.error("[NewSuspendMode] Error polling backend status:", e);
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
        console.warn("[NewSuspendMode] Could not register for download overview changes:", e);
    }
    // Take over the power menu's Sleep before Steam starts suspending. SteamClient is not
    // always populated the moment a plugin loads, so this retries for a while.
    let suspendHookAttempts = 0;
    let suspendHookTimer = null;
    const tryInstallSuspendHooks = () => {
        suspendHookTimer = null;
        let installed = 0;
        try {
            installed = installSuspendMethodHooks();
        }
        catch (e) {
            console.warn("[NewSuspendMode] Could not install suspend hooks:", e);
        }
        if (installed === 0 && ++suspendHookAttempts < 6) {
            suspendHookTimer = setTimeout(tryInstallSuspendHooks, 3000);
        }
    };
    tryInstallSuspendHooks();
    // Hook Steam Client Suspend Request if available
    try {
        if (window.SteamClient?.System?.RegisterForOnSuspendRequest) {
            const reg = window.SteamClient.System.RegisterForOnSuspendRequest(async (request) => {
                console.log("[NewSuspendMode] SteamClient Suspend Request event received!", request);
                call("log_debug", {
                    kind: "suspend_request_fired",
                    in_background: sharedIsBackgroundMode,
                    enabled: sharedSettings.enabled,
                    standby: sharedSettings.standby_on_power_off,
                    request_type: typeof request,
                }).catch(() => { });
                const now = Date.now();
                // 1. If currently in background mode, this suspend request is actually a WAKE request from the Power Button!
                if (sharedIsBackgroundMode) {
                    const timeInBg = Date.now() - sharedBackgroundModeEnteredTime;
                    if (timeInBg < 2000) {
                        console.log(`[NewSuspendMode] Ignoring suspend request in initial transition grace period (${timeInBg}ms).`);
                        return false;
                    }
                    console.log("[NewSuspendMode] Power button pressed while in background mode -> WAKING UP!");
                    await triggerFullWake("power_button_wake");
                    return false; // Prevent Steam from suspending
                }
                // 2. Cooldown check: ignore suspend request if the system just woke up
                if (now < sharedWakeCooldownUntil) {
                    console.log("[NewSuspendMode] Ignoring suspend request: within wake cooldown period.");
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
                    console.log("[NewSuspendMode] No active download and standby off -> Allowing stock SteamOS suspend.");
                    return true;
                }
                // 5. Confirm against the Steam client before taking the suspend over
                await querySteamDownloads();
                const isDownloading = Boolean(sharedDownloadInfo.is_downloading && !sharedDownloadInfo.is_paused);
                if (!isDownloading && sharedSettings.standby_on_power_off) {
                    console.log("[NewSuspendMode] Sleep requested with standby enabled -> splash, then standby.");
                    call("log_debug", {
                        kind: "suspend_request",
                        source: "RegisterForOnSuspendRequest",
                        standby: true,
                        download_info: sharedDownloadInfo,
                    }).catch(() => { });
                    // Steam asked, so Steam may already have touched its own interface.
                    sharedRouteBeforeTakeover = currentUiRoute();
                    sharedUiInitiatedSleep = true;
                    cancelSteamSuspendFlow(request);
                    resumeSteamFromPreparedSuspend();
                    startStandbySplash(sharedSettings.hud_timeout_seconds ?? 5, "standby_sleep_request");
                    return false;
                }
                if (isDownloading) {
                    console.log("[NewSuspendMode] Active download running -> Intercepting suspend and showing HUD");
                    try {
                        const res = await call("trigger_suspend_intercept");
                        if (String(res?.verdict ?? "") === "allow") {
                            // The backend re-read the state and found nothing running after all.
                            console.log("[NewSuspendMode] Backend says idle -> allowing stock suspend.");
                            return true;
                        }
                    }
                    catch (e) {
                        console.error("[NewSuspendMode] Error calling trigger_suspend_intercept:", e);
                    }
                    sharedRouteBeforeTakeover = currentUiRoute();
                    sharedUiInitiatedSleep = true;
                    cancelSteamSuspendFlow(request);
                    resumeSteamFromPreparedSuspend();
                    startHudCountdown(sharedSettings.hud_timeout_seconds ?? 5);
                    return false; // Prevent suspend in SteamClient
                }
                console.log("[NewSuspendMode] Download is paused or idle -> Allowing normal Steam suspend without intercepting.");
                return true; // Allow suspend immediately
            });
            if (reg && typeof reg.unregister === "function") {
                suspendUnregister = reg.unregister;
            }
        }
    }
    catch (e) {
        console.warn("[NewSuspendMode] Could not hook SteamClient.System.RegisterForOnSuspendRequest:", e);
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
        // Every namespace, not a filtered slice: the one call that puts Steam's interface
        // back on screen has to be in here somewhere, and guessing at names has not worked.
        const namespaces = {};
        for (const name of keysOf(sc) ?? []) {
            try {
                const value = sc[name];
                if (value && typeof value === "object") {
                    namespaces[name] = keysOf(value);
                }
            }
            catch (e) { }
        }
        call("log_debug", {
            kind: "steamclient_api_surface",
            top_level: keysOf(sc),
            namespaces,
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
            console.log(`[NewSuspendMode] Kernel resume detected (delta=${delta}ms)! Enforcing wake state.`);
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
        name: "New Suspend Mode",
        icon: SP_JSX.jsx(FaDownload, {}),
        content: SP_JSX.jsx(PluginContent, {}),
        onDismount() {
            routerHook.removeGlobalComponent("NewSuspendModeOverlay");
            pollStopped = true;
            if (pollTimer) {
                clearTimeout(pollTimer);
                pollTimer = null;
            }
            clearTimeout(apiDumpTimer);
            if (suspendHookTimer) {
                clearTimeout(suspendHookTimer);
                suspendHookTimer = null;
            }
            removeSuspendMethodHooks();
            removeMenuItemGuard();
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
            if (standbyRequestUnregister) {
                try {
                    removeEventListener("on_standby_requested", standbyRequestUnregister);
                }
                catch (e) { }
            }
            clearStandbySplash();
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
