/**
 * ResultsTable.tsx — the ranked "Large & Stale" list with evidence.
 *
 * Given a list of FileRow items, render a table: path, human size, and the
 * evidence string, plus a "Reveal in Finder" action per row. This is the
 * product's payoff view — the transparent evidence is what earns user trust
 * (DESIGN.md §2/§8), so render `evidence` prominently, not as an afterthought.
 */

import type { FileRow } from "../types";

interface ResultsTableProps {
  items: FileRow[];
  // TODO: consider loading/empty flags so the table can show "no results yet"
  // vs. "scan found nothing large & stale" — they mean different things.
}

export default function ResultsTable({ items }: ResultsTableProps) {
  // TODO: handleReveal(filepath)
  //   - call api.revealInFinder(filepath); this is advise-only (no delete).

  // TODO: render
  //   - empty state when items.length === 0 (see DESIGN.md: don't look broken)
  //   - a table row per item: filepath, size_human, evidence, Reveal button
  //   - keep it simple; sorting/filtering is out of scope for the MVP view
  return (
    <section>
      {/* TODO: results table */}
      {items.length === 0 ? null : null}
    </section>
  );
}
