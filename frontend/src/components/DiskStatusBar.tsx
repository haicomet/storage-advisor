/**
 * DiskStatusBar.tsx — at-a-glance volume fullness + low-space flag.
 *
 * The always-visible header strip that makes the app feel like a monitor rather
 * than a one-shot report: how full the disk is right now, and a clear warning
 * when it's running low (DESIGN.md §5). Presentation only; App fetches the
 * status and passes it in.
 */

import type { DiskStatus } from "../types";
import { formatBytes } from "../utils";

interface DiskStatusBarProps {
  status: DiskStatus | null; // null before the first fetch
}

export default function DiskStatusBar({ status }: DiskStatusBarProps) {
  if (!status) {
    // TODO: render a quiet loading/placeholder strip ("Checking disk…").
    return <section className="disk-status-bar" />;
  }

  // TODO: render
  //   - free vs total using formatBytes(status.free_bytes) / formatBytes(status.total_bytes)
  //   - a usage meter (percent_free) — consider reading the `dataviz` skill for a
  //     clean, accessible meter rather than a raw bar.
  //   - when status.is_low, a prominent low-space warning that links to the
  //     recommendations below (this is the "flag when low" behavior).
  return (
    <section className={`disk-status-bar${status.is_low ? " low" : ""}`}>
      {/* TODO: free/total + meter + low-space warning */}
    </section>
  );
}
