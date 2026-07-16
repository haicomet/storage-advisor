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

// TODO: add an error shape ({ code, message }) once you decide how the Rust
// layer surfaces protocol errors to JS (rejected promise vs. event).
