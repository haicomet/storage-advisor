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
import type { FileRow, ScanResult } from "./types";
import "./App.css";

function App() {
  const [_results, _setResults] = useState<FileRow[]>([]);

  // TODO: handleScanComplete(result)
  //   - call api.topLargeStale() and store the rows in results state so the
  //     table renders. (result carries scan_id/files_seen if you want a summary.)
  async function handleScanComplete(_result: ScanResult) {
    // TODO: implement
  }

  return (
    <main className="container">
      <h1>Storage Advisor</h1>
      <ScanView onScanComplete={handleScanComplete} />
      <ResultsTable items={_results} />
    </main>
  );
}

export default App;
