/**
 * api.ts — typed wrapper around Tauri `invoke` calls to the Rust shell.
 *
 * Components never call `invoke` directly; they call these functions. That keeps
 * command-name strings and argument shapes in ONE place, so when the Rust
 * command signatures change, only this file changes. The Rust commands in turn
 * forward to the Python sidecar (see src-tauri/src/lib.rs).
 */

import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import type { FileRow, ScanProgress, ScanResult, TrendPoint, DiskStatus, DiskHistoryPoint, LargeFile, FolderRollup } from "./types";

/**
 * Start a scan, receiving streamed progress via `onProgress`.
 */
export async function startScan(
  path: string | undefined,
  onProgress: (p: ScanProgress) => void,
): Promise<ScanResult> {
  // subscribe to the event channel before scan
  // Tauri returns an unlisten functionto clean up later
  const unlisten = await listen<ScanProgress>("scan-progress", (event) => {
    onProgress(event.payload);
  });
  try {
    // trigger the scan, this promise won't resolve until Python finishes
    const result = await invoke<ScanResult>("start_scan", { path: path ?? null });
    return result;
  } finally {
    // guarantee we clean up the listener whether the scan succeeds or fails,
    // preventing memory leaks or duplicated progress bars on the next scan
    unlisten();
  }
}

/**
 * Fetch the ranked "Large & Stale" list for the latest scan.
 */
export async function topLargeStale(
  limit?: number,
  staleMonths?: number,
): Promise<FileRow[]> {
  // tauri automatically maps JS camelCase (staleMonths) to Rust snake_case (stale_months)
  const response = await invoke<{ items: FileRow[] }>("top_large_stale", {
    limit,
    staleMonths,
  });

  return response.items;
}

/**
 * Reveal a file in Finder (advise-only; never deletes).
 */
export async function revealInFinder(filepath: string): Promise<void> {
  await invoke("reveal_in_finder", { filepath });
}

/**
 * Fetch total-storage-size-per-scan over history for the trends chart.
 */
export async function getTrends(): Promise<TrendPoint[]> {

  const response = await invoke<{ points: TrendPoint[] }>("get_trends");
  return response.points;
}

/**
 * Fetch the largest files (offload candidates, ranked by size — no staleness).
 */
export async function getLargeFiles(limit?: number): Promise<LargeFile[]> {
  const response = await invoke<{ items: LargeFile[] }>("get_large_files", { limit })
  return response.items
}

/**
 * Fetch folder cohorts ranked by recursive total size (the offload/triage unit).
 */
export async function getFolderRollups(limit?: number): Promise<FolderRollup[]> {
  const response = await invoke<{ folders: FolderRollup[] }>("get_folder_rollups", { limit });
  return response.folders
}

/**
 * Fetch free-space-per-scan over history for the "Free Space Over Time" chart.
 */
export async function getDiskHistory(): Promise<DiskHistoryPoint[]> {
  const response = await invoke<{ points: DiskHistoryPoint[] }>("get_disk_history");
  return response.points;
}

/**
 * Fetch the current disk status (free/total space + low-space flag).
 */
export async function getDiskStatus(): Promise<DiskStatus> {
  return await invoke<DiskStatus>("get_disk_status");
}
