/**
 * ScanView.tsx — the "run a scan" panel: pick/enter a path, start, watch progress.
 *
 * Owns the scan lifecycle UI: an idle state (path input + Scan button), a
 * running state (progress bar / files-seen counter), and hands the finished
 * result up to the parent so ResultsTable can query. Business logic lives in
 * api.ts; this file is presentation + local state only.
 */

import { useState } from "react";
import { startScan } from "../api";
import type { ScanProgress, ScanResult } from "../types";

interface ScanViewProps {
  // Called once a scan finishes so the parent can trigger the results query.
  onScanComplete: (result: ScanResult) => void;
}

export default function ScanView({ onScanComplete: onScanComplete }: ScanViewProps) {
  const [path, setPath] = useState("");
  const [progress, setProgress] = useState<ScanProgress | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleScan() {
    setIsScanning(true);
    setError(null);
    setProgress({ files_seen: 0, current_dir: "Starting..." });

    try {
      const result = await startScan(path, (p) => setProgress(p));
      onScanComplete(result);
    } catch (err: any) {
      setError(err.toString());
    } finally {
      setIsScanning(false);
      setProgress(null);
    }
  }

  return (
    <section>
      <div className="scan-controls">
        <input
          type="text"
          value={path}
          onChange={(e) => setPath(e.target.value)}
          disabled={isScanning}
          placeholder="Enter path to scan (e.g. ~/Downloads)"
        />
        <button onClick={handleScan} disabled={isScanning || !path.trim()}>
          {isScanning ? "Scanning..." : "Scan"}
        </button>
      </div>

      {/* The denied-permission case is a first-class state */}
      {error && (
        <div className="scan-error">
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
