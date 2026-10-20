import { call } from "@decky/api";
import { DownloadInfo } from "../types";
import { isPluginEnabled, setState } from "../state";

const steamDownloads = (): any => (window as any).SteamClient?.Downloads;

/**
 * Last snapshot read straight from the Steam client, and when it was taken. It is more
 * accurate than the backend's own detection, but only while it is fresh.
 */
let lastInfo: DownloadInfo | null = null;
let lastInfoTime = 0;

export const freshSteamDownloadInfo = (): DownloadInfo | null =>
  lastInfo && Date.now() - lastInfoTime < 6000 ? lastInfo : null;

// Hand download metrics to the backend only when they actually changed, or every 8s
// while downloading so the backend knows the frontend is still reporting.
let lastSentKey = "";
let lastSentTime = 0;

const pushDownloadStatus = (info: DownloadInfo) => {
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
  call("update_download_status", info).catch(() => {});
};

const firstQueueTitle = (queue: any): string | undefined =>
  Array.isArray(queue) && queue.length > 0
    ? queue[0]?.display_name ?? queue[0]?.app_name ?? queue[0]?.name
    : undefined;

/** True when nothing in the queue is actively downloading. */
const queueLooksPaused = (queue: any): boolean => {
  if (!Array.isArray(queue)) return false;
  if (queue.length === 0) return true;
  return !queue.some(
    (item: any) =>
      (item.bDownloading || item.bIsDownloading || item.active) &&
      !item.bPaused &&
      !item.bIsPaused &&
      !item.paused
  );
};

/** Reads the Steam client's download overview and shares it with the backend. */
export const querySteamDownloads = async () => {
  if (!isPluginEnabled()) {
    return;
  }
  try {
    const downloads = steamDownloads();
    if (!downloads?.GetDownloadOverview) return;
    const overview = downloads.GetDownloadOverview();
    if (!overview) return;

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
    const gameTitle =
      (overview.game_name ?? overview.app_name ?? overview.title) || firstQueueTitle(queue);

    const isPaused = Boolean(
      overview.bIsPaused ||
      overview.paused ||
      overview.bPaused ||
      overview.bQueuePaused ||
      overview.is_paused ||
      overview.m_bPaused
    );
    const queuePaused = queueLooksPaused(queue);

    const isDl =
      !isPaused &&
      !queuePaused &&
      (bps > 10000 || (overview.bIsDownloading === true && bps > 0));

    const info: DownloadInfo = {
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
  } catch (e) {
    // Quietly ignore if SteamClient isn't ready
  }
};

/** Re-reads the downloads whenever the Steam client says they changed. */
export const watchSteamDownloads = (): (() => void) => {
  let unregister: (() => void) | null = null;
  try {
    const reg = steamDownloads()?.RegisterForDownloadOverviewChanges?.((data: any) => {
      if (data) {
        querySteamDownloads();
      }
    });
    if (reg && typeof reg.unregister === "function") {
      unregister = () => reg.unregister();
    }
  } catch (e) {
    console.warn("[NewSuspendMode] Could not register for download overview changes:", e);
  }
  return () => {
    try {
      unregister?.();
    } catch (e) {}
  };
};
