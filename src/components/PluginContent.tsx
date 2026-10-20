import React, { FC } from "react";
import { SettingsPanel } from "./SettingsPanel";
import { PluginSettings } from "../types";
import { setState, useUiState } from "../state";

/** The plugin's page in the Quick Access menu. */
export const PluginContent: FC = () => {
  const s = useUiState();

  return (
    <SettingsPanel
      settings={s.settings}
      setSettings={(settings: PluginSettings) => setState({ settings })}
      downloadInfo={s.downloadInfo}
      isBackgroundMode={s.isBackgroundMode}
      standbyMode={s.standbyMode}
      batteryCapacity={s.batteryCapacity}
      isCharging={s.isCharging}
      powerPlugged={s.powerPlugged}
    />
  );
};
