/**
 * api.ts — typed wrapper around Tauri `invoke` calls to the Rust shell.
 *
 * Components never call `invoke` directly; they call these functions. That keeps
 * command-name strings and argument shapes in ONE place, so when the Rust
 * command signatures change, only this file changes. The Rust commands in turn
 * forward to the Python sidecar (see src-tauri/src/lib.rs).
 */

import { invoke } from "@tauri-apps/api/core";
import type { FileRow, ScanProgress, ScanResult } from "./types";

/**
 * Start a scan of `path`, receiving streamed progress via `onProgress`.
 *
 * TODO:
 *   - Subscribe to the progress event the Rust side emits (Tauri `listen`),
 *     forwarding each payload to onProgress; unsubscribe when done.
 *   - invoke("start_scan", { path }) and resolve with the final ScanResult.
 *   - Decide the streaming mechanism WITH the Rust side: Tauri events are the
 *     idiomatic way to push progress to the UI while one invoke() is in flight.
 */
export async function startScan(
  _path: string,
  _onProgress: (p: ScanProgress) => void,
): Promise<ScanResult> {
  // TODO: implement
  throw new Error("not implemented");
}

/**
 * Fetch the ranked "Large & Stale" list for the latest scan.
 *
 * TODO:
 *   - invoke("top_large_stale", { limit, staleMonths }) and return FileRow[].
 *   - Keep argument names matching the #[tauri::command] signature (Tauri maps
 *     camelCase JS args to snake_case Rust params — verify the casing).
 */
export async function topLargeStale(
  _limit?: number,
  _staleMonths?: number,
): Promise<FileRow[]> {
  // TODO: implement
  throw new Error("not implemented");
}

/**
 * Reveal a file in Finder (advise-only; never deletes).
 *
 * TODO:
 *   - Use the Tauri opener plugin (already a dependency) or a Rust command that
 *     runs `open -R <path>` on macOS. This is the only "action" in the MVP and
 *     it is deliberately non-destructive (DESIGN.md §2).
 */
export async function revealInFinder(_filepath: string): Promise<void> {
  // TODO: implement
  throw new Error("not implemented");
}
