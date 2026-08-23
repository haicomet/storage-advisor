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
  return (
    <section className="goals-panel">
      <h2>Goals</h2>
      {/* TODO: goal list + progress bars + create-goal form */}
    </section>
  );
}
