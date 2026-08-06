/**
 * TrendsView.tsx — storage-growth-over-time chart.
 *
 * Given the trend points (one per completed scan), render a simple line/area
 * chart of total size over scan history — the "your storage grew 8 GB since
 * April" story (ROADMAP Phase 3). Presentation only; data is fetched in App and
 * passed in as props, matching ResultsTable's prop-driven shape.
 */

import type { TrendPoint } from "../types";
// TODO: import the chart primitives once recharts is installed, e.g.
//   import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

interface TrendsViewProps {
  points: TrendPoint[];
}

export default function TrendsView({ points }: TrendsViewProps) {
  // Empty states matter here (ROADMAP Phase 3 pitfall: one scan is not a trend).
  // TODO: 0 points  -> "No scan history yet."
  //       1 point   -> "Come back after another scan to see a trend."
  //       2+ points -> render the chart below.
  if (points.length < 2) {
    return (
      <section className="trends-panel empty-state">
        {/* TODO: show the right message for 0 vs 1 point */}
      </section>
    );
  }

  // TODO: render the chart
  //   - x-axis: started_at (epoch seconds). Format to a short date — divide by
  //     nothing; new Date(started_at * 1000). Consider a tickFormatter.
  //   - y-axis: total_bytes. Add a tickFormatter that shows human sizes (reuse
  //     the same base-1000 logic as the backend _human_size so units match the
  //     table). Consider a shared formatDbytes helper rather than duplicating.
  //   - Tooltip: show total_human + the formatted date.
  //   - Wrap in <ResponsiveContainer> so it fills the panel width.
  //   - BEFORE writing chart code, read the `dataviz` skill (colors, axes,
  //     accessibility) — ROADMAP Phase 3 "Learn first".
  return (
    <section className="trends-panel">
      <h2>Storage Over Time</h2>
      {/* TODO: <ResponsiveContainer><LineChart data={points}> ... </LineChart></ResponsiveContainer> */}
    </section>
  );
}
