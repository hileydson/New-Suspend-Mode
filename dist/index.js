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
}function FaHome (props) {
  return GenIcon({"attr":{"viewBox":"0 0 576 512"},"child":[{"tag":"path","attr":{"d":"M280.37 148.26L96 300.11V464a16 16 0 0 0 16 16l112.06-.29a16 16 0 0 0 15.92-16V368a16 16 0 0 1 16-16h64a16 16 0 0 1 16 16v95.64a16 16 0 0 0 16 16.05L464 480a16 16 0 0 0 16-16V300L295.67 148.26a12.19 12.19 0 0 0-15.3 0zM571.6 251.47L488 182.56V44.05a12 12 0 0 0-12-12h-56a12 12 0 0 0-12 12v72.61L318.47 43a48 48 0 0 0-61 0L4.34 251.47a12 12 0 0 0-1.6 16.9l25.5 31A12 12 0 0 0 45.15 301l235.22-193.74a12.19 12.19 0 0 1 15.3 0L530.9 301a12 12 0 0 0 16.9-1.6l25.5-31a12 12 0 0 0-1.7-16.93z"},"child":[]}]})(props);
}function FaDownload (props) {
  return GenIcon({"attr":{"viewBox":"0 0 512 512"},"child":[{"tag":"path","attr":{"d":"M216 0h80c13.3 0 24 10.7 24 24v168h87.7c17.8 0 26.7 21.5 14.1 34.1L269.7 378.3c-7.5 7.5-19.8 7.5-27.3 0L90.1 226.1c-12.6-12.6-3.7-34.1 14.1-34.1H192V24c0-13.3 10.7-24 24-24zm296 376v112c0 13.3-10.7 24-24 24H24c-13.3 0-24-10.7-24-24V376c0-13.3 10.7-24 24-24h146.7l49 49c20.1 20.1 52.5 20.1 72.6 0l49-49H488c13.3 0 24 10.7 24 24zm-124 88c0-11-9-20-20-20s-20 9-20 20 9 20 20 20 20-9 20-20zm64 0c0-11-9-20-20-20s-20 9-20 20 9 20 20 20 20-9 20-20z"},"child":[]}]})(props);
}function FaBolt (props) {
  return GenIcon({"attr":{"viewBox":"0 0 320 512"},"child":[{"tag":"path","attr":{"d":"M296 160H180.6l42.6-129.8C227.2 15 215.7 0 200 0H56C44 0 33.8 8.9 32.2 20.8l-32 240C-1.7 275.2 9.5 288 24 288h118.7L96.6 482.5c-3.6 15.2 8 29.5 23.3 29.5 8.4 0 16.4-4.4 20.8-12l176-304c9.3-15.9-2.2-36-20.7-36z"},"child":[]}]})(props);
}function FaBatteryThreeQuarters (props) {
  return GenIcon({"attr":{"viewBox":"0 0 640 512"},"child":[{"tag":"path","attr":{"d":"M544 160v64h32v64h-32v64H64V160h480m16-64H48c-26.51 0-48 21.49-48 48v224c0 26.51 21.49 48 48 48h512c26.51 0 48-21.49 48-48v-16h8c13.255 0 24-10.745 24-24V184c0-13.255-10.745-24-24-24h-8v-16c0-26.51-21.49-48-48-48zm-144 96H96v128h320V192z"},"child":[]}]})(props);
}

const Overlay = ({ downloadInfo, settings, batteryCapacity, isCharging, }) => {
    const [showHud, setShowHud] = SP_REACT.useState(false);
    const [isBlackout, setIsBlackout] = SP_REACT.useState(false);
    const [isPeeking, setIsPeeking] = SP_REACT.useState(false);
    const [countdown, setCountdown] = SP_REACT.useState(5);
    const countdownTimerRef = SP_REACT.useRef(null);
    const blackoutRef = SP_REACT.useRef(false);
    const showHudRef = SP_REACT.useRef(false);
    const peekingRef = SP_REACT.useRef(false);
    const enteredTimestampRef = SP_REACT.useRef(0);
    const buttonsReleasedRef = SP_REACT.useRef(false);
    blackoutRef.current = isBlackout;
    showHudRef.current = showHud;
    peekingRef.current = isPeeking;
    // Full System Wake (triggered via Power Button or manual Home button)
    const fullWakeUp = SP_REACT.useCallback(async (reason = "user_input") => {
        if (countdownTimerRef.current) {
            clearInterval(countdownTimerRef.current);
            countdownTimerRef.current = null;
        }
        setShowHud(false);
        setIsBlackout(false);
        setIsPeeking(false);
        try {
            await call("exit_background_mode", reason);
        }
        catch (e) {
            console.error("[DownloadInBackground] Error exiting background mode:", e);
        }
        // Force navigation to SteamOS Home Screen
        try {
            const steamClient = window.SteamClient;
            if (steamClient?.URL?.ExecuteSteamURL) {
                steamClient.URL.ExecuteSteamURL("steam://open/main");
            }
            else {
                window.location.href = "steam://open/main";
            }
        }
        catch (e) {
            console.error("[DownloadInBackground] Error navigating to Steam home:", e);
        }
        toaster.toast({
            title: "Download in Background",
            body: "Console awakened! Returning to Home screen.",
            duration: 2500,
        });
    }, []);
    // Enter Pitch Black Mode
    const enterBlackout = SP_REACT.useCallback(async (reason = "countdown_completed") => {
        if (countdownTimerRef.current) {
            clearInterval(countdownTimerRef.current);
            countdownTimerRef.current = null;
        }
        setShowHud(false);
        setIsPeeking(false);
        setIsBlackout(true);
        try {
            await call("enter_background_mode", reason);
        }
        catch (e) {
            console.error("[DownloadInBackground] Error entering background mode:", e);
        }
    }, []);
    // Peek Progress: Briefly turn on screen for 4s, keeping power savings intact
    const startPeekHud = SP_REACT.useCallback(async () => {
        if (!blackoutRef.current && !peekingRef.current)
            return;
        try {
            await call("peek_display_on");
        }
        catch (e) {
            console.error("[DownloadInBackground] Error peeking display on:", e);
        }
        setIsPeeking(true);
        setShowHud(true);
        setIsBlackout(false);
        setCountdown(4);
        if (countdownTimerRef.current) {
            clearInterval(countdownTimerRef.current);
        }
        let remaining = 4;
        countdownTimerRef.current = setInterval(async () => {
            remaining -= 1;
            setCountdown(remaining);
            if (remaining <= 0) {
                if (countdownTimerRef.current) {
                    clearInterval(countdownTimerRef.current);
                    countdownTimerRef.current = null;
                }
                setIsPeeking(false);
                setShowHud(false);
                setIsBlackout(true);
                try {
                    await call("peek_display_off");
                }
                catch (e) {
                    console.error("[DownloadInBackground] Error peeking display off:", e);
                }
            }
        }, 1000);
    }, []);
    const dismissPeekNow = SP_REACT.useCallback(async () => {
        if (countdownTimerRef.current) {
            clearInterval(countdownTimerRef.current);
            countdownTimerRef.current = null;
        }
        setIsPeeking(false);
        setShowHud(false);
        setIsBlackout(true);
        try {
            await call("peek_display_off");
        }
        catch (e) {
            console.error("[DownloadInBackground] Error dismissing peek:", e);
        }
    }, []);
    // Initial HUD Sequence before going to sleep (on suspend intercept)
    const startInitialHudSequence = SP_REACT.useCallback((customTimeout) => {
        const timeoutSec = customTimeout ?? settings.hud_timeout_seconds ?? 5;
        if (timeoutSec <= 0) {
            enterBlackout("immediate");
            return;
        }
        setCountdown(timeoutSec);
        setShowHud(true);
        setIsBlackout(false);
        setIsPeeking(false);
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
    SP_REACT.useEffect(() => {
        const handleSuspendIntercepted = (data) => {
            console.log("[DownloadInBackground] Suspend intercepted!", data);
            const customTimeout = data?.hud_timeout ?? settings.hud_timeout_seconds ?? 5;
            startInitialHudSequence(customTimeout);
        };
        const handleBackgroundModeChanged = (data) => {
            if (data && typeof data.is_background_mode === "boolean") {
                if (data.is_background_mode) {
                    setIsBlackout(true);
                    setShowHud(false);
                    setIsPeeking(false);
                }
                else {
                    // Full system wake up
                    if (countdownTimerRef.current) {
                        clearInterval(countdownTimerRef.current);
                        countdownTimerRef.current = null;
                    }
                    setIsBlackout(false);
                    setShowHud(false);
                    setIsPeeking(false);
                    // Force SteamOS to the Home Screen
                    try {
                        const sc = window.SteamClient;
                        if (sc?.URL?.ExecuteSteamURL) {
                            sc.URL.ExecuteSteamURL("steam://open/main");
                        }
                        else {
                            window.location.href = "steam://open/main";
                        }
                    }
                    catch (e) { }
                }
            }
        };
        const handleBatteryCritical = (data) => {
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
    // Update activation timestamp when entering HUD or blackout
    SP_REACT.useEffect(() => {
        if (isBlackout || showHud) {
            enteredTimestampRef.current = Date.now();
            buttonsReleasedRef.current = false;
        }
    }, [isBlackout, showHud]);
    // Controller / Input Listeners:
    // - When screen is black: Controller button press = Peek download status for 4s
    // - When peeking: Controller button press resets 4s peek timer
    SP_REACT.useEffect(() => {
        const handleGlobalKeyDown = () => {
            if (Date.now() - enteredTimestampRef.current < 1200)
                return;
            if (blackoutRef.current) {
                startPeekHud();
            }
            else if (peekingRef.current) {
                setCountdown(4);
            }
        };
        const handlePointerDown = () => {
            if (Date.now() - enteredTimestampRef.current < 1200)
                return;
            if (blackoutRef.current) {
                startPeekHud();
            }
            else if (peekingRef.current) {
                setCountdown(4);
            }
        };
        let gamepadPollId;
        const pollGamepads = () => {
            const timeSinceEntered = Date.now() - enteredTimestampRef.current;
            if (timeSinceEntered > 1200) {
                const gamepads = navigator.getGamepads ? navigator.getGamepads() : [];
                let anyPressed = false;
                for (const gp of gamepads) {
                    if (!gp)
                        continue;
                    for (const btn of gp.buttons) {
                        if (btn.pressed) {
                            anyPressed = true;
                            break;
                        }
                    }
                    if (anyPressed)
                        break;
                }
                if (!anyPressed) {
                    buttonsReleasedRef.current = true;
                }
                else if (buttonsReleasedRef.current) {
                    // Button was pressed after being released!
                    if (blackoutRef.current) {
                        buttonsReleasedRef.current = false;
                        startPeekHud();
                    }
                    else if (peekingRef.current) {
                        setCountdown(4);
                    }
                }
            }
            gamepadPollId = requestAnimationFrame(pollGamepads);
        };
        window.addEventListener("keydown", handleGlobalKeyDown, { capture: true });
        window.addEventListener("pointerdown", handlePointerDown, { capture: true });
        gamepadPollId = requestAnimationFrame(pollGamepads);
        return () => {
            window.removeEventListener("keydown", handleGlobalKeyDown, { capture: true });
            window.removeEventListener("pointerdown", handlePointerDown, { capture: true });
            cancelAnimationFrame(gamepadPollId);
        };
    }, [startPeekHud]);
    // Format Helpers
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
    if (!showHud && !isBlackout) {
        return null;
    }
    // Pure black screen mode
    if (isBlackout) {
        return (SP_JSX.jsx("div", { className: "dib-overlay-container dib-overlay-blackout", onClick: startPeekHud, tabIndex: 0, "aria-hidden": "true" }));
    }
    // Download HUD Mode (both Initial Suspend Countdown and Controller Peek)
    const percent = Math.min(100, Math.max(0, downloadInfo.progress_percent || 0));
    const gameTitle = downloadInfo.game_title || "Steam Game Download";
    return (SP_JSX.jsx("div", { className: "dib-overlay-container dib-overlay-hud", children: SP_JSX.jsxs("div", { className: "dib-hud-card", children: [SP_JSX.jsxs("div", { className: "dib-hud-header", children: [SP_JSX.jsxs("div", { className: "dib-hud-title-box", children: [SP_JSX.jsx(FaDownload, { className: "dib-hud-icon" }), SP_JSX.jsxs("div", { children: [SP_JSX.jsx("div", { className: "dib-hud-title", children: "Download in Background" }), SP_JSX.jsx("div", { className: "dib-hud-subtitle", children: isPeeking
                                                ? "Peeking download progress — Press POWER to fully wake"
                                                : "System entering low-power mode to continue downloads" })] })] }), SP_JSX.jsxs("div", { className: "dib-countdown-badge", children: [SP_JSX.jsx(FaMoon, {}), "Screen off in ", countdown, "s"] })] }), SP_JSX.jsxs("div", { className: "dib-game-info", children: [SP_JSX.jsx("div", { className: "dib-game-title", children: gameTitle }), SP_JSX.jsx("div", { className: "dib-progress-container", children: SP_JSX.jsx("div", { className: "dib-progress-bar", style: { width: `${percent > 0 ? percent : 2}%` } }) }), SP_JSX.jsxs("div", { className: "dib-metrics-row", children: [SP_JSX.jsxs("div", { className: "dib-metric-item", children: [SP_JSX.jsx("span", { children: "Speed:" }), SP_JSX.jsx("span", { className: "dib-metric-value", children: formatSpeed(downloadInfo.bytes_per_second) })] }), SP_JSX.jsxs("div", { className: "dib-metric-item", children: [SP_JSX.jsx("span", { children: "Progress:" }), SP_JSX.jsxs("span", { className: "dib-metric-value", children: [percent.toFixed(1), "% (", formatSize(downloadInfo.completed_bytes), " / ", formatSize(downloadInfo.total_bytes), ")"] })] }), SP_JSX.jsxs("div", { className: "dib-metric-item", children: [SP_JSX.jsx("span", { children: "Time Left:" }), SP_JSX.jsx("span", { className: "dib-metric-value", children: formatTime(downloadInfo.estimated_seconds_remaining) })] })] })] }), SP_JSX.jsxs("div", { className: "dib-status-badges", children: [SP_JSX.jsxs("div", { className: "dib-badge", children: [SP_JSX.jsx(FaBatteryThreeQuarters, { className: `dib-badge-icon ${batteryCapacity <= 20 ? "warning" : ""}` }), SP_JSX.jsxs("div", { children: [SP_JSX.jsx("div", { className: "dib-badge-title", children: "Battery Level" }), SP_JSX.jsxs("div", { className: "dib-badge-val", children: [batteryCapacity, "% ", isCharging ? "(Charging)" : ""] })] })] }), SP_JSX.jsxs("div", { className: "dib-badge", children: [SP_JSX.jsx(FaBolt, { className: "dib-badge-icon" }), SP_JSX.jsxs("div", { children: [SP_JSX.jsx("div", { className: "dib-badge-title", children: "Auto-Suspend Threshold" }), SP_JSX.jsxs("div", { className: "dib-badge-val", children: ["At \u2264 ", settings.min_battery_threshold, "% or on finish"] })] })] })] }), SP_JSX.jsx("div", { className: "dib-hud-actions", children: isPeeking ? (SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsxs("button", { className: "dib-btn-primary", onClick: dismissPeekNow, children: [SP_JSX.jsx(FaMoon, { style: { marginRight: 6 } }), " Turn Screen Off Now"] }), SP_JSX.jsxs("button", { className: "dib-btn-secondary", onClick: () => fullWakeUp("user_peek_home"), children: [SP_JSX.jsx(FaHome, { style: { marginRight: 6 } }), " Wake to Home Screen"] })] })) : (SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsx("button", { className: "dib-btn-primary", onClick: () => enterBlackout("button_clicked"), children: "Turn Off Screen Now" }), SP_JSX.jsxs("button", { className: "dib-btn-secondary", onClick: () => fullWakeUp("cancel_clicked"), children: [SP_JSX.jsx(FaTimes, { style: { marginRight: 6 } }), " Cancel & Keep Awake"] })] })) }), SP_JSX.jsx("div", { className: "dib-hud-footer", children: isPeeking
                        ? "Press any controller button to reset timer. Press the POWER button to wake console completely to Home."
                        : "Screen turns off automatically. Press any controller button to glance at progress, or POWER to wake." })] }) }));
};

const SettingsPanel = ({ settings, setSettings, downloadInfo, isBackgroundMode, batteryCapacity, isCharging, powerPlugged, }) => {
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
    const isDownloading = downloadInfo.is_downloading || (downloadInfo.bytes_per_second || 0) > 10000;
    return (SP_JSX.jsxs("div", { children: [SP_JSX.jsxs(DFL.PanelSection, { title: "Download & System Status", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.Field, { label: "Download Status", description: isDownloading
                                ? `${downloadInfo.game_title || "Steam Download"} (${formatSpeed(downloadInfo.bytes_per_second)})`
                                : "No active downloads", children: SP_JSX.jsx("span", { className: `dib-status-tag ${isDownloading ? "downloading" : "idle"}`, children: isDownloading ? "DOWNLOADING" : "IDLE" }) }) }), isDownloading && (SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsxs("div", { style: { width: "100%", margin: "4px 0" }, children: [SP_JSX.jsxs("div", { style: {
                                        display: "flex",
                                        justifyContent: "space-between",
                                        fontSize: "12px",
                                        color: "#cbd5e1",
                                        marginBottom: "4px",
                                    }, children: [SP_JSX.jsxs("span", { children: ["Progress: ", downloadInfo.progress_percent.toFixed(1), "%"] }), SP_JSX.jsxs("span", { children: ["Speed: ", formatSpeed(downloadInfo.bytes_per_second)] })] }), SP_JSX.jsx(DFL.ProgressBar, { nProgress: downloadInfo.progress_percent || 0 })] }) })), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.Field, { label: "Battery Level", description: `Auto-sleep threshold: ${settings.min_battery_threshold}%`, children: SP_JSX.jsxs("span", { style: { fontWeight: "bold" }, children: [batteryCapacity, "% ", isCharging ? "⚡ (Charging)" : "🔋"] }) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.Field, { label: "Background Download Mode", description: isBackgroundMode
                                ? "Active (Screen off & power saving enabled)"
                                : "Inactive (Normal operation)", children: SP_JSX.jsx("span", { className: `dib-status-tag ${isBackgroundMode ? "active" : "idle"}`, children: isBackgroundMode ? "ACTIVE" : "STANDBY" }) }) })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Behavior Settings", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Enable Plugin", description: "Intercepts suspend when downloading, turns off screen, and saves power.", checked: settings.enabled, onChange: (checked) => updateSetting("enabled", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Auto-Suspend Battery Threshold", description: "Console suspends automatically if battery drops below this limit during download.", value: settings.min_battery_threshold, min: 5, max: 30, step: 1, showValue: true, valueSuffix: "%", onChange: (val) => updateSetting("min_battery_threshold", val) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "HUD Display Countdown", description: "Seconds the download card shows on screen before turning display off.", value: settings.hud_timeout_seconds, min: 0, max: 15, step: 1, showValue: true, valueSuffix: "s", onChange: (val) => updateSetting("hud_timeout_seconds", val) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.SliderField, { label: "Completion Suspend Delay", description: "Seconds to wait after all downloads complete before automatically sleeping.", value: settings.auto_suspend_delay_seconds, min: 5, max: 60, step: 5, showValue: true, valueSuffix: "s", onChange: (val) => updateSetting("auto_suspend_delay_seconds", val) }) })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "Power Saving & Screen Options", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Turn Off Display Backlight", description: "Physically drops LCD/OLED panel backlight brightness to 0.", checked: settings.turn_off_backlight, onChange: (checked) => updateSetting("turn_off_backlight", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Pitch Black OLED Mode", description: "Presents a pure black overlay, shutting off individual OLED pixels.", checked: settings.oled_black_screen, onChange: (checked) => updateSetting("oled_black_screen", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Throttle CPU to Powersave", description: "Switches power profile to power-saver and lowers CPU clock frequencies.", checked: settings.throttle_cpu, onChange: (checked) => updateSetting("throttle_cpu", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Throttle GPU to 200MHz", description: "Sets AMD GPU performance level to low, minimizing GPU power draw.", checked: settings.throttle_gpu, onChange: (checked) => updateSetting("throttle_gpu", checked) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Mute Audio While Screen Off", description: "Silences audio output during background download to prevent disturbance.", checked: settings.mute_audio, onChange: (checked) => updateSetting("mute_audio", checked) }) })] })] }));
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
    auto_suspend_delay_seconds: 15,
    throttle_cpu: true,
    throttle_gpu: true,
    mute_audio: true,
    turn_off_backlight: true,
    oled_black_screen: true,
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
// Global shared state for communication between QAM panel and Global Overlay
let sharedDownloadInfo = { ...DEFAULT_DOWNLOAD_INFO };
let sharedSettings = { ...DEFAULT_SETTINGS };
let sharedBatteryCapacity = 100;
let sharedIsCharging = false;
let sharedPowerPlugged = false;
let sharedIsBackgroundMode = false;
const stateListeners = new Set();
function notifyStateListeners() {
    stateListeners.forEach((cb) => cb());
}
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
    return (SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsx("style", { children: PLUGIN_STYLES }), SP_JSX.jsx(Overlay, { downloadInfo: sharedDownloadInfo, settings: sharedSettings, batteryCapacity: sharedBatteryCapacity, isCharging: sharedIsCharging })] }));
};
// Plugin Quick Access Menu Content
const PluginContent = () => {
    const [settings, setSettings] = SP_REACT.useState(sharedSettings);
    const [downloadInfo, setDownloadInfo] = SP_REACT.useState(sharedDownloadInfo);
    const [isBackgroundMode, setIsBackgroundMode] = SP_REACT.useState(sharedIsBackgroundMode);
    const [batteryCapacity, setBatteryCapacity] = SP_REACT.useState(sharedBatteryCapacity);
    const [isCharging, setIsCharging] = SP_REACT.useState(sharedIsCharging);
    const [powerPlugged, setPowerPlugged] = SP_REACT.useState(sharedPowerPlugged);
    SP_REACT.useEffect(() => {
        const update = () => {
            setSettings(sharedSettings);
            setDownloadInfo(sharedDownloadInfo);
            setIsBackgroundMode(sharedIsBackgroundMode);
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
    return (SP_JSX.jsx(SettingsPanel, { settings: settings, setSettings: handleUpdateSettings, downloadInfo: downloadInfo, isBackgroundMode: isBackgroundMode, batteryCapacity: batteryCapacity, isCharging: isCharging, powerPlugged: powerPlugged }));
};
var index = definePlugin(() => {
    // Register global overlay in SteamOS DOM
    routerHook.addGlobalComponent("DownloadInBackgroundOverlay", GlobalOverlayContainer);
    let pollInterval = null;
    let dlUnregister = null;
    let suspendUnregister = null;
    // Sync state with Python backend
    const syncBackendStatus = async () => {
        try {
            const status = await call("get_status");
            if (status) {
                sharedIsBackgroundMode = Boolean(status.is_background_mode);
                sharedBatteryCapacity = Number(status.battery_capacity ?? 100);
                sharedIsCharging = Boolean(status.is_charging);
                sharedPowerPlugged = Boolean(status.power_plugged);
                if (status.settings) {
                    sharedSettings = { ...sharedSettings, ...status.settings };
                }
                if (status.download_info) {
                    sharedDownloadInfo = { ...sharedDownloadInfo, ...status.download_info };
                }
                notifyStateListeners();
            }
        }
        catch (e) {
            console.error("[DownloadInBackground] Error polling backend status:", e);
        }
    };
    // Poll / Query SteamClient Downloads API
    const querySteamDownloads = async () => {
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
                    const isDl = bps > 10000 || overview.bIsDownloading === true || overview.downloading === true;
                    const updatedInfo = {
                        is_downloading: isDl,
                        bytes_per_second: bps,
                        total_bytes: totalBytes,
                        completed_bytes: completedBytes,
                        progress_percent: percent,
                        game_title: gameTitle || "Steam Download",
                        estimated_seconds_remaining: etaSeconds,
                    };
                    sharedDownloadInfo = updatedInfo;
                    notifyStateListeners();
                    // Sync download metrics to backend
                    call("update_download_status", updatedInfo).catch(() => { });
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
                if (sharedSettings.enabled && sharedDownloadInfo.is_downloading) {
                    // Intercept SteamClient suspend!
                    // Trigger overlay HUD countdown
                    window.dispatchEvent(new CustomEvent("decky_event_on_suspend_intercepted", {
                        detail: {
                            download_info: sharedDownloadInfo,
                            hud_timeout: sharedSettings.hud_timeout_seconds,
                        }
                    }));
                    return false; // Prevent suspend in SteamClient
                }
                return true; // Allow suspend
            });
            if (reg && typeof reg.unregister === "function") {
                suspendUnregister = reg.unregister;
            }
        }
    }
    catch (e) {
        console.warn("[DownloadInBackground] Could not hook SteamClient.System.RegisterForOnSuspendRequest:", e);
    }
    // Initial fetch and start interval
    syncBackendStatus();
    querySteamDownloads();
    pollInterval = setInterval(() => {
        syncBackendStatus();
        querySteamDownloads();
    }, 2000);
    return {
        name: "Download in Background",
        icon: SP_JSX.jsx(FaDownload, {}),
        content: SP_JSX.jsx(PluginContent, {}),
        onDismount() {
            routerHook.removeGlobalComponent("DownloadInBackgroundOverlay");
            if (pollInterval) {
                clearInterval(pollInterval);
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
        },
    };
});

export { index as default };
//# sourceMappingURL=index.js.map
