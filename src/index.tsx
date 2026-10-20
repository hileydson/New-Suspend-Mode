import React from "react";
import { definePlugin, routerHook } from "@decky/api";
import { FaDownload } from "react-icons/fa";
import { GlobalOverlay } from "./components/GlobalOverlay";
import { PluginContent } from "./components/PluginContent";
import { listenToBackend, startBackendSync } from "./backend";
import { stopFlowTimers } from "./flows";
import { installSleepPatch } from "./steam/sleepPatch";
import { watchSteamDownloads } from "./steam/downloads";

export default definePlugin(() => {
  // The HUD, the standby splash and the black screen, drawn over the whole interface.
  routerHook.addGlobalComponent("NewSuspendModeOverlay", GlobalOverlay);

  const stopListening = listenToBackend();
  const stopWatchingDownloads = watchSteamDownloads();
  const removeSleepPatch = installSleepPatch();
  const stopSync = startBackendSync();

  return {
    name: "New Suspend Mode",
    icon: <FaDownload />,
    content: <PluginContent />,
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
