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
import { revealInFinder } from "../api";

interface OffloadCandidatesViewProps {
  folders: FolderRollup[]; // recursive-size cohorts, ranked by total_bytes
  files: LargeFile[];      // largest individual files, ranked by size
}

export default function OffloadCandidatesView({ folders, files }: OffloadCandidatesViewProps) {
  if (folders.length === 0 && files.length === 0) {
    return (
      <section className="offload-panel empty-state" >
        <p>"Run a scan to find things to offload."</p>
      </section>
      );
  }


  return (
    <section className="offload-panel">
      <h2>Offload Candidates</h2>

      <div className="offload-folders">
        <h3>Folders ({folders.length})</h3>
        {/* list folders — path · total_human · file_count files */}
        <ul>
          {folders.map((folder) => {
            const filepath = folder.path;
            const basename = filepath.split("/").filter(Boolean).pop();

            return (
              <li key={folder.path}>
                <strong>{basename}</strong> - {filepath} · {folder.total_human} · {folder.file_count}
                <button onClick={() => revealInFinder(filepath)}>Reveal</button>
              </li>
            )
          })}
        </ul>
      </div>

      <div className="offload-files">
        <h3>Large Files ({files.length})</h3>
        {/* list files — basename · size_human */}
        <ul>
          {files.map((file) => {
            const filepath = file.filepath
            const basename = filepath.split("/").filter(Boolean).pop();

            return (
              <li key={file.filepath}>
                <strong>{basename}</strong> - {filepath} · {file.size_human}
                <button onClick={() => revealInFinder(filepath)}>Reveal</button>
              </li>
            )
          })}
        </ul>
      </div>
    </section>
  );
}
