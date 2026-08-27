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
import type { FileRow, ScanProgress, ScanResult, TrendPoint, DiskStatus, DiskHistoryPoint, LargeFile, FolderRollup, TriageItem, TriageDecision, GoalKind, GoalWithProgress, Action, ActionResult } from "./types";

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

// --- Phase 5: footprint / goals ---------------------------------------------

/**
 * Record a keep/delete/offload decision for a path (file or folder cohort).
 * NOT a filesystem action — only records intent (the actual move is Phase 6).
 */
export async function setTriage(path: string, isDir: boolean, decision: TriageDecision): Promise<void> {
  await invoke("set_triage", { path, isDir, decision });
}

/**
 * List triage decisions, optionally filtered (e.g. "undecided").
 */
export async function listTriage(decision?: TriageDecision): Promise<TriageItem[]> {
  const response = await invoke<{ items: TriageItem[] }>("list_triage", { decision });
  return response.items.map(item => ({
    ...item,
    is_dir: Boolean(item.is_dir)
  }));
}

/**
 * Create a goal. Pass targetBytes for free_amount, thresholdBytes for stay_above.
 */
export async function createGoal(kind: GoalKind, opts?: { targetBytes?: number; thresholdBytes?: number }): Promise<number> {
  const response = await invoke<{ goal_id: number }>("create_goal", {
    kind,
    targetBytes: opts?.targetBytes ?? null,
    thresholdBytes: opts?.thresholdBytes ?? null
  });
  return response.goal_id
}

/**
 * List goals with their computed progress.
 */
export async function listGoals(status?: string): Promise<GoalWithProgress[]> {
  const response = await invoke<{ goals: GoalWithProgress[] }>("list_goals", { status });
  return response.goals;
}

// --- Phase 6: safe actions (Move to Trash + undo) ---------------------------

/**
 * Move a file or folder cohort to the macOS Trash (reversible; never rm).
 * Returns the recorded action (with an undo_token). Confirm in the UI first.
 */
export async function moveToTrash(path: string, isDir: boolean, sizeBytes?: number): Promise<ActionResult> {
  return await invoke<ActionResult>("move_to_trash", { path, isDir, sizeBytes: sizeBytes ?? null });
}

/** Reverse a completed action (restore from Trash) by its id. */
export async function undoAction(actionId: number): Promise<void> {
  await invoke("undo_action", { actionId });
}

/** The footprint log — actions the app has taken, newest first. */
export async function listActions(status?: string): Promise<Action[]> {
  const response = await invoke<{ actions: Action[] }>("list_actions", { status });
  return response.actions.map(a => ({ ...a, is_dir: Boolean(a.is_dir) }));
}
