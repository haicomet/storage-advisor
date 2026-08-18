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
import { useEffect, useRef } from "react";

interface ScanViewProps {
  onScanComplete: (result: ScanResult) => void;
}

export default function ScanView({ onScanComplete }: ScanViewProps) {
  const [progress, setProgress] = useState<ScanProgress | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Guard against React 18 StrictMode double-invoke
  const hasInitialized = useRef(false);

  // Trigger the initial home-dir scan automatically on mount
  useEffect(() => {
    if (hasInitialized.current) return;
    hasInitialized.current = true;
    
    handleScan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  // Detect macOS permission errors
  const isPermissionError =
    error?.toLowerCase().includes("operation not permitted") || 
    error?.toLowerCase().includes("permission denied");

  return (
    <section>
      <div className="scan-controls">
        <div style={{ flexGrow: 1, color: '#444' }}>
          <strong>Target:</strong> Home Folder (~)
        </div>
        <button onClick={handleScan} disabled={isScanning}>
          {isScanning ? "Scanning..." : "Rescan"}
        </button>
      </div>

      {error && (
        <div className="scan-error">
          <strong>Scan Failed:</strong> {error}

          {isPermissionError && (
            <div style={{ marginTop: '0.5rem', fontSize: '0.95em' }}>
              <p>macOS is blocking access to some of your folders.</p>
              <p>To fix this, open <strong>System Settings &gt; Privacy &amp; Security &gt; Full Disk Access</strong>, and toggle on Storage Advisor.</p>
            </div>
          )}
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
