/**
 * App.tsx — top-level composition for the MVP: ScanView above ResultsTable.
 *
 * Holds the little shared state that connects the two views: when a scan
 * finishes, fetch the ranked results and hand them to the table. Keep this thin
 * — per-view state belongs in the components; only the cross-view handoff lives
 * here.
 */

import { useRef, useEffect, useState } from "react";
import ScanView from "./components/ScanView";
import ResultsTable from "./components/ResultsTable";
import TrendsView from "./components/TrendsView";
import DiskStatusBar from "./components/DiskStatusBar";
import { topLargeStale, getDiskHistory, getDiskStatus } from "./api";
import type { FileRow, ScanResult, DiskHistoryPoint, DiskStatus } from "./types";
import "./App.css";

function App() {
  const [_results, _setResults] = useState<FileRow[]>([]);
  const [trends, setTrends] = useState<DiskHistoryPoint[]>([]);
  const [diskStatus, setDiskStatus] = useState<DiskStatus | null>(null);
  const [hasScanned, setHasScanned] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasInitialized = useRef(false);

  // auto-scan: on mount, fetch disk status immediately
  useEffect(() => {
    if (hasInitialized.current) return;
    hasInitialized.current = true;

    refreshDiskStatus();

    // Load free-space history on mount if it exists
    getDiskHistory().then(setTrends).catch(console.error);

    // Keep the monitor alive by polling every 10 seconds
    const intervalId = setInterval(refreshDiskStatus, 10000);
    return () => clearInterval(intervalId);
  }, []);

  async function refreshDiskStatus() {
    try {
      const status = await getDiskStatus();
      setDiskStatus(status);
      
      // Clear any previous disk errors on a successful fetch
      setError((prev) => (prev?.includes("Disk Monitor Error") ? null : prev));
    } catch (err: any) {
      console.error("Failed to fetch disk status", err);
      setError(`Disk Monitor Error: ${err.toString()}`);
    }
  }

  async function handleScanComplete(_result: ScanResult) {
    setHasScanned(true);
    setError(null);
    try {
      // Fetch the top 50 large & stale files (defaulting to 12 months in the backend)
      const items = await topLargeStale(50, 12);
      _setResults(items);

      const points = await getDiskHistory();
      setTrends(points);

      await refreshDiskStatus();
    } catch (err: any) {
      setError(err.toString());
    }
  }

  return (
    <main className="container">
      <h1>Storage Advisor</h1>

      <DiskStatusBar status={diskStatus} />

      {error && <div className="error-banner">Error fetching results: {error}</div>}

      <ScanView onScanComplete={handleScanComplete} />
      <TrendsView points={trends} />
      <ResultsTable items={_results} hasScanned={hasScanned} />
    </main>
  );
}

export default App;
