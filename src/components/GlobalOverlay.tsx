import React, { FC } from "react";
import { Overlay } from "./Overlay";
import { PLUGIN_STYLES } from "../styles";
import { useUiState } from "../state";
import { triggerEnterBlackout, triggerFullWake } from "../flows";

/**
 * The plugin's full-screen layer, mounted over the whole Steam interface through
 * routerHook.addGlobalComponent.
 *
 * Renders nothing at all unless the HUD, the splash or the black screen is up, so once
 * the console is awake there is nothing of the plugin left on screen.
 */
export const GlobalOverlay: FC = () => {
  const s = useUiState();

  if (!s.isBackgroundMode && !s.showHud && !s.showSplash) {
    return null;
  }

  return (
    <>
      <style>{PLUGIN_STYLES}</style>
      <Overlay
        isBackgroundMode={s.isBackgroundMode}
        showHud={s.showHud}
        showSplash={s.showSplash}
        countdown={s.countdown}
        downloadInfo={s.downloadInfo}
        settings={s.settings}
        batteryCapacity={s.batteryCapacity}
        isCharging={s.isCharging}
        onWake={() => triggerFullWake("overlay_wake")}
        onEnterBlackout={() => triggerEnterBlackout("manual_screen_off")}
      />
    </>
  );
};
