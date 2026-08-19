/**
 * OffloadCandidatesView.tsx — size-led offload candidates (folders first).
 *
 * The offload counterpart to ResultsTable (which is delete-oriented / stale-led).
 * Offloading is reversible, so this view leads with SIZE, not staleness
 * (DESIGN.md §7), and its primary unit is the FOLDER cohort — the way most
 * offloads actually happen ("move ~/School/Fall2024 to the SSD") — with large
 * individual files as a secondary drill-down.
 *
 * Presentation only; App fetches folders + files and passes them in.
 */

import type { FolderRollup, LargeFile } from "../types";

interface OffloadCandidatesViewProps {
  folders: FolderRollup[]; // recursive-size cohorts, ranked by total_bytes
  files: LargeFile[];      // largest individual files, ranked by size
}

export default function OffloadCandidatesView({ folders, files }: OffloadCandidatesViewProps) {
  if (folders.length === 0 && files.length === 0) {
    // TODO: empty state — "Run a scan to find things to offload."
    return <section className="offload-panel empty-state" />;
  }

  // TODO: render, folders FIRST (the primary unit), then large files.
  //   Folders section:
  //     - path (or basename), total_human, file_count
  //     - NOTE: total_bytes is RECURSIVE (whole subtree). If you ever show a
  //       combined "you'll reclaim X" total across a multi-select, collapse
  //       selected paths to their topmost ancestor so a parent + child are not
  //       double-counted (DESIGN.md §7). Do NOT naively sum selected folders.
  //     - drill-down affordance to expand a folder's contents (later phase can
  //       reuse the same query scoped to a subpath).
  //   Large files section:
  //     - filepath (basename), size_human.
  //   Actions (Offload / Trash) are deferred to Phase 6/7 — this view is
  //   advise-only for now, like ResultsTable. Consider a Reveal button reusing
  //   api.revealInFinder as the only action for now.
  return (
    <section className="offload-panel">
      <h2>Offload Candidates</h2>

      <div className="offload-folders">
        <h3>Folders ({folders.length})</h3>
        {/* TODO: list folders — path · total_human · file_count files */}
      </div>

      <div className="offload-files">
        <h3>Large Files ({files.length})</h3>
        {/* TODO: list files — basename · size_human */}
      </div>
    </section>
  );
}
