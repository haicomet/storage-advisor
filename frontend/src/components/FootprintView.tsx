/**
 * FootprintView.tsx — the action log ("what the app has done") + undo.
 *
 * Shows the permanent record of Trash/offload actions (DESIGN.md §4/§6) with an
 * Undo button per reversible action. This is the trust surface for *acting*:
 * the user can always see, and reverse, what happened.
 *
 * Presentation only; App fetches the actions and provides an undo handler.
 */

import type { Action } from "../types";
import { formatBytes } from "../utils";

interface FootprintViewProps {
  actions: Action[];
  onUndo: (actionId: number) => void;
}

export default function FootprintView({ actions, onUndo: _onUndo }: FootprintViewProps) {
  if (actions.length === 0) {
    // TODO: empty state — "No actions yet. Trash or offload something to see it here."
    return <section className="footprint-panel empty-state" />;
  }

  // TODO: render a row per action:
  //   - kind (Trash/Offload), path basename, size (formatBytes), status, date
  //   - an Undo button ONLY when action.status === "done" (pending/failed/undone
  //     are not undoable). Wire it to _onUndo(action.id).
  //   - show a clear "undone" state after reversal.
  return (
    <section className="footprint-panel">
      <h2>Activity</h2>
      {/* TODO: action log rows + per-row Undo */}
    </section>
  );
}
