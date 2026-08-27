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
import OffloadCandidatesView from "./components/OffloadCandidatesView";
import GoalsView from "./components/GoalsView";
import FootprintView from "./components/FootprintView";
import { topLargeStale, getDiskHistory, getDiskStatus, getLargeFiles, getFolderRollups, listGoals, createGoal, listActions, undoAction } from "./api";
import type { FileRow, ScanResult, DiskHistoryPoint, DiskStatus, LargeFile, FolderRollup, GoalWithProgress, GoalKind, Action } from "./types";
import "./App.css";

function App() {
  const [_results, _setResults] = useState<FileRow[]>([]);
  const [trends, setTrends] = useState<DiskHistoryPoint[]>([]);
  const [diskStatus, setDiskStatus] = useState<DiskStatus | null>(null);
  const [largeFiles, setLargeFiles] = useState<LargeFile[]>([]);
  const [folders, setFolders] = useState<FolderRollup[]>([]);
  // Phase 5: goals (footprint). Progress is computed backend-side per goal.
  const [goals, setGoals] = useState<GoalWithProgress[]>([]);
  // Phase 6: the action log (Trash/offload history + undo).
  const [actions, setActions] = useState<Action[]>([]);
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

    // Load goals + progress on mount (footprint persists across sessions)
    refreshGoals();

    // Load the action log on mount (Phase 6 footprint/undo)
    refreshActions();

    // Keep the monitor alive by polling every 10 seconds
    const intervalId = setInterval(refreshDiskStatus, 10000);
    return () => clearInterval(intervalId);
  }, []);

  async function refreshGoals() {
    // Loads active goals with computed progress. Safe to call anytime; the
    // listGoals api wrapper is still a stub, so guard against its throw for now.
    try {
      setGoals(await listGoals("active"));
    } catch (err) {
      console.error("Failed to load goals", err);
    }
  }

  async function handleCreateGoal(kind: GoalKind, opts?: { targetBytes?: number; thresholdBytes?: number }) {
    try {
      await createGoal(kind, opts);
      await refreshGoals();
    } catch (err) {
      console.error("Failed to create goal", err);
    }
  }

  async function refreshActions() {
    // Loads the action log. Guarded — the backend list_actions is still a stub.
    try {
      setActions(await listActions());
    } catch (err) {
      console.error("Failed to load actions", err);
    }
  }

  async function handleUndo(actionId: number) {
    try {
      await undoAction(actionId);
      await refreshActions();
      await refreshGoals();       // undo changes reclaimed bytes → goal progress
      await refreshDiskStatus();  // and free space
    } catch (err) {
      console.error("Failed to undo action", err);
    }
  }

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

      setFolders(await getFolderRollups(50));
      setLargeFiles(await getLargeFiles(50));

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

      {/* Goals / footprint — Phase 5 */}
      <GoalsView goals={goals} onCreateGoal={handleCreateGoal} />

      {/* Action log + undo — Phase 6 */}
      <FootprintView actions={actions} onUndo={handleUndo} />

      <ScanView onScanComplete={handleScanComplete} />
      <TrendsView points={trends} />
      {/* Offload candidates (size-led, folders first) — Phase 4.5 */}
      <OffloadCandidatesView folders={folders} files={largeFiles} />
      {/* Large & Stale (deletion-oriented) */}
      <ResultsTable items={_results} hasScanned={hasScanned} />
    </main>
  );
}

export default App;
