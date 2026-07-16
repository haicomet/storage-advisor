"""
analyzer.py — read-only analytics queries over a scan snapshot.

This module answers product questions ("what is large AND stale?") by querying
the `files`/`scans` tables that Phase 1 populated. It never writes; it only
reads and *reshapes* rows into the `file row` dicts defined in docs/protocol.md,
so main.py can hand them straight to the UI without further transformation.

Design intent (see DESIGN.md §5 and docs/protocol.md):
  - The flagship insight is "Large & Stale" = large AND stale, ranked by
    size × age.
  - Queries return plain dicts shaped like the protocol's `file row`, so the
    sidecar layer is "wire it up," not "reshape everything."
"""

import sqlite3

# Default thresholds for the "Large & Stale" signal. These are the concrete,
# user-visible numbers DESIGN.md §5 insists on (no vague adjectives).
DEFAULT_STALE_MONTHS = 12
DEFAULT_MIN_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB
DEFAULT_LIMIT = 200

# Rough seconds-per-month, used to translate `stale_months` into an mtime
# cutoff. Precision doesn't matter here — "older than a year-ish" is the point.
SECONDS_PER_MONTH = 30 * 24 * 60 * 60


def get_latest_scan_id(conn: sqlite3.Connection) -> int | None:
    """Return the id of the most recent *completed* scan, or None if none exist.

    TODO:
      - SELECT the max/most-recent scan id from `scans` (order by started_at DESC,
        or filter status = 'complete' — decide which and document it).
      - Return None when the table is empty so callers can show an empty state
        instead of crashing.
    Why this exists: every query runs against "the latest snapshot" unless a
    specific scan_id is passed. Centralize that lookup here.
    """
    # TODO: implement
    raise NotImplementedError


def top_large_stale(
    conn: sqlite3.Connection,
    *,
    limit: int = DEFAULT_LIMIT,
    stale_months: int = DEFAULT_STALE_MONTHS,
    min_size_bytes: int = DEFAULT_MIN_SIZE_BYTES,
    now: int | None = None,
    scan_id: int | None = None,
) -> list[dict]:
    """Return the top `limit` large-and-stale files for one scan, ranked by size × age.

    Each returned dict must match the protocol's `file row` shape:
        {
          "filepath": str,
          "size_bytes": int,
          "last_modified": int,        # epoch seconds
          "size_human": str,           # e.g. "4.2 GB"
          "evidence": str,             # e.g. "4.2 GB · not modified since Jun 2019"
        }

    TODO:
      - If scan_id is None, resolve it via get_latest_scan_id(); if still None,
        return [] (empty state, not an error).
      - Compute the staleness cutoff: cutoff = (now or current time) -
        stale_months * SECONDS_PER_MONTH. Lead with `last_modified` (mtime), NOT
        last_accessed — atime is unreliable on macOS (DESIGN.md §5).
      - SELECT filepath, size_bytes, last_modified FROM files
        WHERE scan_id = ? AND size_bytes >= ? AND last_modified < ?
        ORDER BY (size_bytes * (now - last_modified)) DESC
        LIMIT ?
        (You have indexes on size_bytes and last_modified from Phase 1 — think
        about which the planner can actually use here.)
      - Map each row through _human_size() and _format_evidence() to build the
        two presentation fields.
    Design note: the ranking key size × age is deliberately simple and
    explainable — the product's credibility rests on transparent evidence, so
    resist a fancier score you can't explain in the UI.
    """
    # TODO: implement
    raise NotImplementedError


def _human_size(size_bytes: int) -> str:
    """Format a byte count as a short human string (e.g. 4509715660 -> "4.2 GB").

    TODO:
      - Walk KB/MB/GB/TB (base 1024 or 1000 — pick one and be consistent with
        what you tell the user), keep one decimal place, return a compact string.
    """
    # TODO: implement
    raise NotImplementedError


def _format_evidence(size_bytes: int, last_modified: int) -> str:
    """Build the human-readable 'why this was flagged' string.

    Example: "4.2 GB · not modified since Jun 2019".

    TODO:
      - Combine _human_size(size_bytes) with a friendly month/year derived from
        last_modified (epoch -> "Jun 2019").
      - This string is the product's trust surface — it's the evidence the user
        judges the recommendation by. Keep it factual and specific.
    """
    # TODO: implement
    raise NotImplementedError
