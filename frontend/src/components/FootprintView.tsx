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

    return (
    <section className="footprint-panel empty-state">
      <p>No actions yet. Trash or offload something to see it here.</p>
    </section>
    )
  }

  return (
    <section className="footprint-panel">
      <h2>Activity</h2>

      <ul>
        {actions.map((action) => {
          const fileName = action.path.split('/').pop() || action.path;
          const dateString = new Date(action.created_at * 1000).toLocaleDateString();
          const sizeString = action.size_bytes ? formatBytes(action.size_bytes) : "Unknown size";

          return (
            <li key={action.id} className="footprint-row">
              <div className="action-details">
                <strong>{action.kind.toUpperCase()}</strong>: {fileName} ({sizeString}) on {dateString}
              </div>
              
              <div className="action-controls">
                {action.status === "done" && (
                  <button onClick={() => _onUndo(action.id)}>Undo</button>
                )}
                {action.status === "undone" && (
                  <span className="badge">Restored</span>
                )}
              </div>
            </li>
          );
        })}
      </ul>

    </section>
  );
}
