/**
 * GoalsView.tsx — storage goals + progress (the "footprint" made visible).
 *
 * Shows the user's active goals with computed progress, and lets them create a
 * new one. The three goal kinds (free a target amount / stay above a threshold /
 * work through a triage list) are all views over the footprint — see
 * DESIGN.md §4/§5. Progress is computed on the backend, never stored.
 *
 * Presentation only; App fetches goals and passes them in, and provides a
 * create handler.
 */

import type { GoalWithProgress, GoalKind } from "../types";
import { useState } from "react"

interface GoalsViewProps {
  goals: GoalWithProgress[];
  // Create a goal, then refresh. App owns the api call + reload.
  onCreateGoal: (kind: GoalKind, opts?: { targetBytes?: number; thresholdBytes?: number }) => void;
}

export default function GoalsView({ goals, onCreateGoal: _onCreateGoal }: GoalsViewProps) {
  // TODO: render
  //   - empty state when goals.length === 0 ("Set a goal to start tracking cleanup.")
  //   - each goal: a progress bar from goal.progress.percent + goal.progress.label,
  //     and a "done" state when goal.progress.done. Reuse the meter styling from
  //     DiskStatusBar for visual consistency (consider extracting a shared meter).
  //   - a small create-goal form: pick kind (free_amount / stay_above / triage) and
  //     enter a target/threshold in GB (convert GB -> bytes before calling
  //     onCreateGoal). Keep it minimal.
  const [kind, setKind] = useState<GoalKind>("free_amount");
  const [gbInput, setGbInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const bytes = parseFloat(gbInput) * 1024 * 1024 * 1024;

    if (kind === "free_amount") {
    _onCreateGoal(kind, { targetBytes: bytes });
  } else if (kind === "stay_above") {
    _onCreateGoal(kind, { thresholdBytes: bytes });
  } else {
    _onCreateGoal(kind);
  }

  setGbInput("");
  };

  return (
    <section className="goals-panel">
      <h2>Goals</h2>
      <form onSubmit={handleSubmit}>
        <select value={kind} onChange={(e) => setKind(e.target.value as GoalKind)}>
          <option value="free_amount">Free Up Space</option>
          <option value="stay_above">Keep Free Space Above</option>
          <option value="triage">Empty Triage Inbox</option>
        </select>

        {/* only show the number input if they didn't pick "triage" */}
        {kind !== "triage" && (
          <input 
            type="number" 
            placeholder="Amount in GB" 
            value={gbInput}
            onChange={(e) => setGbInput(e.target.value)}
            required
          />
        )}
        
        <button type="submit">Create Goal</button>
      </form>
      {goals.length === 0 ? (
        <p>Set a goal to start tracking cleanup.</p>
      ) : (
        goals.map(goal => (
          <div className="goal-item" key={goal.id}>
            <p>{goal.progress.label}</p>
            <div style={{ background: "#eee", height: "20px", width: "100%", borderRadius: "10px", overflow: "hidden" }}>
              <div style={{ 
                background: goal.progress.done ? "green" : "blue",
                height: "100%",
                width: `${goal.progress.percent}%`
              }} />
            </div>
          </div>
        ))
      )}
    </section>

  );
}
