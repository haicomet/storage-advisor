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
import type { FileRow, ScanProgress, ScanResult } from "./types";

/**
 * Start a scan of `path`, receiving streamed progress via `onProgress`.
 */
export async function startScan(
  path: string,
  onProgress: (p: ScanProgress) => void,
): Promise<ScanResult> {
  // subscribe to the event channel before scan
  // Tauri returns an unlisten functionto clean up later
  const unlisten = await listen<ScanProgress>("scan-progress", (event) => {
    onProgress(event.payload);
  });
  try {
    // trigger the scan, this promise won't resolve until Python finishes
    const result = await invoke<ScanResult>("start_scan", { path });
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
