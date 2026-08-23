/**
 * types.ts — shared TypeScript shapes mirroring the sidecar protocol.
 *
 * These mirror docs/protocol.md (the Python side is the source of truth). Keep
 * them in sync by hand: if a protocol field changes, change it here too. Having
 * one typed definition means the components and the api wrapper agree on shape.
 */

// One row rendered in the results table. Matches the protocol `file row`.
export interface FileRow {
  filepath: string;
  size_bytes: number;
  last_modified: number; // epoch seconds
  size_human: string; // e.g. "4.2 GB"
  evidence: string; // e.g. "4.2 GB · not modified since Jun 2019"
}

// Payload of a `progress` message streamed during a scan.
export interface ScanProgress {
  files_seen: number;
  current_dir: string;
}

// Payload of the terminal `result` message for a `scan` command.
export interface ScanResult {
  scan_id: number;
  files_seen: number;
  duration_ms: number;
  disk_free_bytes: number; // volume snapshot at scan time
  disk_total_bytes: number;
}

export interface ProtocolError {
  code: string;
  message: string;
}

// One point on the trends chart: total storage size at one scan in history.
// Mirrors analyzer.scan_trends() output (see docs/protocol.md).
export interface TrendPoint {
  scan_id: number;
  started_at: number; // epoch seconds — chart x-axis
  total_bytes: number; // chart y-axis
  total_human: string; // e.g. "4.2 GB" — tooltip/label
}

// Current volume fullness. Mirrors main.handle_disk_status() output.
// Drives the disk-status bar and the low-space flag (DESIGN.md §5).
export interface DiskStatus {
  free_bytes: number;
  total_bytes: number;
  used_bytes: number;
  percent_free: number; // 0–100
  is_low: boolean; // true when at/below the low-space threshold
}

// One point on the free-space trend: how much disk was free at one scan.
// Mirrors analyzer.disk_history() output. Powers the "Free Space Over Time" chart.
export interface DiskHistoryPoint {
  scan_id: number;
  started_at: number; // epoch seconds — chart x-axis
  disk_free_bytes: number; // chart y-axis
  disk_total_bytes: number;
  free_human: string; // e.g. "35.9 GB" — tooltip
}

// A large file, ranked by size only (offload candidate). Mirrors
// analyzer.large_files() output. No staleness — offload leads with size (§7).
export interface LargeFile {
  filepath: string;
  size_bytes: number;
  size_human: string; // e.g. "4.2 GB"
}

// A folder cohort ranked by RECURSIVE total size. Mirrors analyzer.folder_rollups().
// The primary unit of offload/triage — the "school-year folder" case.
export interface FolderRollup {
  path: string;
  total_bytes: number; // recursive: whole subtree, not just direct files
  total_human: string; // e.g. "22 GB"
  file_count: number;
}

// --- Phase 5: footprint / goals ---------------------------------------------

// The user's decision on a path (file or folder cohort). Mirrors the triage table.
export type TriageDecision = "keep" | "delete" | "offload" | "undecided";

export interface TriageItem {
  path: string;
  is_dir: boolean;
  decision: TriageDecision;
  decided_at: number; // epoch seconds
}

export type GoalKind = "free_amount" | "stay_above" | "triage";

// A goal row (config only — progress is computed, see GoalProgress).
export interface Goal {
  id: number;
  kind: GoalKind;
  target_bytes: number | null; // for free_amount
  threshold_bytes: number | null; // for stay_above
  created_at: number;
  status: "active" | "achieved" | "abandoned";
}

// Computed progress for a goal (analyzer.goal_progress). Never persisted.
export interface GoalProgress {
  kind: GoalKind;
  current: number;
  target: number | null;
  percent: number; // 0–100
  done: boolean;
  label: string; // human summary, e.g. "12 GB of 20 GB freed"
}

// A goal with its computed progress attached (what list_goals returns).
export interface GoalWithProgress extends Goal {
  progress: GoalProgress;
}