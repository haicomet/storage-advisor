/**
 * ScanView.tsx — the "run a scan" panel: pick/enter a path, start, watch progress.
 *
 * Owns the scan lifecycle UI: an idle state (path input + Scan button), a
 * running state (progress bar / files-seen counter), and hands the finished
 * result up to the parent so ResultsTable can query. Business logic lives in
 * api.ts; this file is presentation + local state only.
 */

import { useState } from "react";
import type { ScanProgress, ScanResult } from "../types";

interface ScanViewProps {
  // Called once a scan finishes so the parent can trigger the results query.
  onScanComplete: (result: ScanResult) => void;
}

export default function ScanView({ onScanComplete: _onScanComplete }: ScanViewProps) {
  const [_path, _setPath] = useState("");
  const [_progress, _setProgress] = useState<ScanProgress | null>(null);
  const [_isScanning, _setIsScanning] = useState(false);

  // TODO: handleScan()
  //   - set isScanning true, clear old progress
  //   - call api.startScan(path, setProgress)
  //   - on resolve: setIsScanning(false), call onScanComplete(result)
  //   - on reject: surface the error (permission denied etc.) — do NOT leave the
  //     UI stuck in a spinner. The denied-permission case is a first-class state
  //     (ROADMAP Phase 2 pitfalls), not an afterthought.

  // TODO: render
  //   - idle: a path input + "Scan" button
  //   - scanning: a progress indicator using progress.files_seen / current_dir
  //     (indeterminate is fine — total file count is unknown up front)
  return (
    <section>
      {/* TODO: scan controls + progress UI */}
    </section>
  );
}
