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
import { topLargeStale } from "./api";
import type { FileRow, ScanResult } from "./types";
import "./App.css";

function App() {
  const [_results, _setResults] = useState<FileRow[]>([]);
  const [hasScanned, setHasScanned] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleScanComplete(_result: ScanResult) {
    setHasScanned(true);
    setError(null);
    try {
      // Fetch the top 50 large & stale files (defaulting to 12 months in the backend)
      const items = await topLargeStale(50, 12);
      _setResults(items);
    } catch (err: any) {
      setError(err.toString());
    }
  }

  return (
    <main className="container">
      <h1>Storage Advisor</h1>
      
      {error && <div className="error-banner">Error fetching results: {error}</div>}

      <ScanView onScanComplete={handleScanComplete} />
      <ResultsTable items={_results} hasScanned={hasScanned} />
    </main>
  );
}

export default App;
