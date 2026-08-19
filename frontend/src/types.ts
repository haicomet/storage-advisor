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