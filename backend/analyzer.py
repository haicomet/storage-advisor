"""
analyzer.py — read-only analytics queries over a scan snapshot.

This module answers product questions ("what is large AND stale?") by querying
the `files`/`scans` tables.
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
    """Return the id of the most recent *completed* scan, or None if none exist."""

    cursor = conn.execute(
        """
        SELECT id FROM scans 
        WHERE status = 'complete' 
        ORDER BY started_at DESC 
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    return row["id"] if row else None


def top_large_stale(
    conn: sqlite3.Connection,
    *,
    limit: int = DEFAULT_LIMIT,
    stale_months: int = DEFAULT_STALE_MONTHS,
    min_size_bytes: int = DEFAULT_MIN_SIZE_BYTES,
    now: int | None = None,
    scan_id: int | None = None,
) -> list[dict]:
    """Return the top `limit` large-and-stale files for one scan, ranked by size × age."""

    if scan_id is None:
        scan_id = get_latest_scan_id(conn)
        if scan_id is None:
            return []

    current_time = now if now is not None else int(time.time())
    cutoff_time = current_time - (stale_months * SECONDS_PER_MONTH)

    query = """
        SELECT filepath, size_bytes, last_modified
        FROM files
        WHERE scan_id = ? 
          AND size_bytes >= ? 
          AND last_modified < ?
        ORDER BY (size_bytes * (? - last_modified)) DESC
        LIMIT ?
    """

    cursor = conn.execute(
        query, 
        (scan_id, min_size_bytes, cutoff_time, current_time, limit)
    )

    results = []
    for row in cursor:
        size = row["size_bytes"]
        mtime = row["last_modified"]
        results.append({
            "filepath": row["filepath"],
            "size_bytes": size,
            "last_modified": mtime,
            "size_human": _human_size(size),
            "evidence": _format_evidence(size, mtime),
        })

    return results


def _human_size(size_bytes: int) -> str:
    """Format a byte count as a short human string (e.g. 4509715660 -> "4.2 GB")."""

    base = 1000.0
    
    if size_bytes < base:
        return f"{size_bytes} B"

    for unit in ['KB', 'MB', 'GB', 'TB']:
        if size_bytes < base:
          formatted = f"{size_bytes:.1f}".rstrip('0').rstrip('.')
          return f"{formatted} {unit}"
        size_bytes /= base

    return f"{size_bytes:.1f} PB"


def _format_evidence(size_bytes: int, last_modified: int) -> str:
    """Build the human-readable 'why this was flagged' string."""

    human_size = _human_size(size_bytes)
    dt = datetime.datetime.fromtimestamp(last_modified)
    month_year = dt.strftime("%b %Y")

    return f"{human_size} · not modified since {month_year}"
