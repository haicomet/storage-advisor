/**
 * App.tsx — top-level composition for the MVP: ScanView above ResultsTable.
 *
 * Holds the little shared state that connects the two views: when a scan
 * finishes, fetch the ranked results and hand them to the table. Keep this thin
 * — per-view state belongs in the components; only the cross-view handoff lives
 * here.
 */

import { useState } from "react";
import ScanView from "./components/ScanView";
import ResultsTable from "./components/ResultsTable";
import TrendsView from "./components/TrendsView";
import DiskStatusBar from "./components/DiskStatusBar";
import { topLargeStale, getTrends, getDiskStatus } from "./api";
import type { FileRow, ScanResult, TrendPoint, DiskStatus } from "./types";
import "./App.css";

function App() {
  const [_results, _setResults] = useState<FileRow[]>([]);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [diskStatus, setDiskStatus] = useState<DiskStatus | null>(null);
  const [hasScanned, setHasScanned] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // TODO (Phase 4 auto-scan): on mount, fetch disk status immediately (cheap,
  // no scan) so the DiskStatusBar shows right away, then kick off the home-dir
  // scan. Use a useEffect with an empty dep array; guard against React 18
  // StrictMode double-invoke so it doesn't scan twice in dev.
  //   useEffect(() => { getDiskStatus().then(setDiskStatus); /* + trigger scan */ }, []);

  async function handleScanComplete(_result: ScanResult) {
    setHasScanned(true);
    setError(null);
    try {
      // Fetch the top 50 large & stale files (defaulting to 12 months in the backend)
      const items = await topLargeStale(50, 12);
      _setResults(items);

      const points = await getTrends();
      setTrends(points);

      // TODO: refresh disk status after a scan too (free space just changed if
      // the user acted, and the scan captured a fresh snapshot).
      //   setDiskStatus(await getDiskStatus());
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
