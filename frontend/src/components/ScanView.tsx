/**
 * ScanView.tsx — scan lifecycle UI (Phase 4: auto-targeted).
 *
 * The path input is gone. The app scans the home directory automatically — on
 * launch (triggered by App) and via a manual "Rescan" button. This component
 * owns only the scan lifecycle state (running / progress / error) and bubbles
 * the finished result up via onScanComplete. Business logic lives in api.ts.
 */

import { useState } from "react";
import { startScan } from "../api";
import type { ScanProgress, ScanResult } from "../types";

interface ScanViewProps {
  onScanComplete: (result: ScanResult) => void;
  // TODO (App wiring): App will call the scan on mount too. Options:
  //   - expose an imperative handle, OR
  //   - lift handleScan into App and pass `onRescan` down. Pick one; keep a
  //     single code path so launch-scan and manual-rescan behave identically.
}

export default function ScanView({ onScanComplete }: ScanViewProps) {
  const [progress, setProgress] = useState<ScanProgress | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleScan() {
    setIsScanning(true);
    setError(null);
    setProgress({ files_seen: 0, current_dir: "Starting..." });

    try {
      // Phase 4: no path — undefined means "auto-target home" (see api.startScan).
      const result = await startScan(undefined, (p) => setProgress(p));
      onScanComplete(result);
    } catch (err: any) {
      // The denied-permission case (Full Disk Access) is a first-class state,
      // not a silent failure — keep surfacing it clearly.
      setError(err.toString());
    } finally {
      setIsScanning(false);
      setProgress(null);
    }
  }

  return (
    <section>
      <div className="scan-controls">
        {/* TODO: show the target (e.g. "Scanning your home folder") instead of a
            path input, plus a Rescan button. */}
        <button onClick={handleScan} disabled={isScanning}>
          {isScanning ? "Scanning..." : "Rescan"}
        </button>
      </div>

      {error && (
        <div className="scan-error">
          {/* TODO: if this is a Full Disk Access denial, give guidance on granting
              it in System Settings — don't just dump the raw error. */}
          <strong>Scan Failed:</strong> {error}
        </div>
      )}

      {isScanning && progress && (
        <div className="progress-display">
          <p><strong>Files mapped:</strong> {progress.files_seen}</p>
          <p className="path-truncate"><strong>Current:</strong> {progress.current_dir}</p>
        </div>
      )}
    </section>
  );
}
