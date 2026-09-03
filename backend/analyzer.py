"""
analyzer.py — read-only analytics queries over a scan snapshot.

This module answers product questions ("what is large AND stale?") by querying
the `files`/`scans` tables.
"""

import sqlite3
import time
import datetime
import os
from collections import defaultdict
import stat

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


def large_files(
    conn: sqlite3.Connection,
    *,
    limit: int = DEFAULT_LIMIT,
    min_size_bytes: int = DEFAULT_MIN_SIZE_BYTES,
    scan_id: int | None = None,
) -> list[dict]:
    """Return the largest files for one scan, ranked by size ONLY (no staleness).

    This is the primary *offload* candidate list (DESIGN.md §7): offloading is
    reversible, so it leads with size and does not gate on age. Contrast with
    top_large_stale, the *deletion* list, which requires staleness.

    Each dict: {filepath, size_bytes, size_human}.

    TODO:
      - Resolve scan_id via get_latest_scan_id() when None; return [] if still None.
      - SELECT filepath, size_bytes FROM files
        WHERE scan_id = ? AND size_bytes >= ?
        ORDER BY size_bytes DESC
        LIMIT ?
        (the idx_files_size index covers this ordering).
      - Map rows through _human_size(). No evidence string / no mtime needed —
        size is the whole story here.
    """
    if scan_id is None:
        scan_id = get_latest_scan_id(conn)
        if scan_id is None:
            return []

    query = """
        SELECT filepath, size_bytes FROM files
        WHERE scan_id = ? AND size_bytes >= ?
        ORDER BY size_bytes DESC
        LIMIT ?
        """

    cursor = conn.execute(query, (scan_id, min_size_bytes, limit))

    results = []
    for row in cursor:
        size = row["size_bytes"]

        results.append(
            {
                "filepath": row["filepath"],
                "size_bytes": size,
                "size_human": _human_size(size)
            }
        )

    return results


def folder_rollups(
    conn: sqlite3.Connection,
    *,
    limit: int = DEFAULT_LIMIT,
    min_size_bytes: int = DEFAULT_MIN_SIZE_BYTES,
    scan_id: int | None = None,
) -> list[dict]:
    """Return directories ranked by RECURSIVE total size — the cohort view.

    Surfaces the "school-year folder" case: the unit most offloads act on is a
    folder, not a single file. Each dict: {path, total_bytes, total_human,
    file_count}.
    """
    if scan_id is None:
        scan_id = get_latest_scan_id(conn)
        if scan_id is None:
            return []

    folder_stats = defaultdict(lambda: [0,0])

    query = """
        SELECT filepath, size_bytes FROM files
        WHERE scan_id = ?
    """
    cursor = conn.execute(query, (scan_id,))

    for row in cursor:
        filepath = row["filepath"]
        curr_dir = os.path.dirname(filepath)

        while curr_dir != "/" and curr_dir != "":
            folder_stats[curr_dir][0] += row["size_bytes"]
            folder_stats[curr_dir][1] += 1
            curr_dir = os.path.dirname(curr_dir)

    results = []

    for folder_path, stats in folder_stats.items():
        total_bytes = stats[0]
        file_count = stats[1]

        if total_bytes >= min_size_bytes:
            results.append(
                {
                    "path": folder_path,
                    "total_bytes": total_bytes,
                    "total_human": _human_size(total_bytes),
                    "file_count": file_count
                }
            )

    results.sort(key=lambda x: x["total_bytes"], reverse=True)
    limited_results = results[:limit]

    return limited_results


def scan_trends(conn: sqlite3.Connection, *, limit: int | None = None) -> list[dict]:
    """Return total storage size per completed scan over time, for the trends chart."""

    if limit is not None:
        # subquery fetches the N most recent scans; outer query re-sorts them chronologically
        query = """
            SELECT id, started_at, total_bytes
            FROM (
                SELECT id, started_at, total_bytes
                FROM scans
                WHERE status = 'complete'
                ORDER BY started_at DESC
                LIMIT ?
            )
            ORDER BY started_at ASC
        """
        cursor = conn.execute(query, (limit,))
    else:
        # no limit: just fetch everything chronologically.
        query = """
            SELECT id, started_at, total_bytes
            FROM scans
            WHERE status = 'complete'
            ORDER BY started_at ASC
        """
        cursor = conn.execute(query)

    results = []
    for row in cursor:
        total_bytes = row["total_bytes"]
        # handle cases where total_bytes might be NULL in older corrupted DB entries
        if total_bytes is None:
            total_bytes = 0 
            
        results.append({
            "scan_id": row["id"],
            "started_at": row["started_at"],
            "total_bytes": total_bytes,
            "total_human": _human_size(total_bytes),
        })

    return results


def disk_history(conn: sqlite3.Connection, *, limit: int | None = None) -> list[dict]:
    """Return free/total disk space per completed scan over time.

    Powers the free-space trend line (distinct from scan_trends, which tracks the
    scanned bytes total). Each dict: {scan_id, started_at, disk_free_bytes,
    disk_total_bytes, free_human}."""

    if limit is not None:
        # subquery fetches the N most recent scans; outer query re-sorts them chronologically
        query = """
            SELECT id, started_at, disk_free_bytes, disk_total_bytes
            FROM (
                SELECT id, started_at, disk_free_bytes, disk_total_bytes
                FROM scans
                WHERE status = 'complete' 
                  AND disk_free_bytes IS NOT NULL
                ORDER BY started_at DESC
                LIMIT ?
            )
            ORDER BY started_at ASC
        """
        cursor = conn.execute(query, (limit,))
    else:
        # no limit: just fetch everything chronologically.
        query = """
            SELECT id, started_at, disk_free_bytes, disk_total_bytes
            FROM scans
            WHERE status = 'complete' 
              AND disk_free_bytes IS NOT NULL
            ORDER BY started_at ASC
        """
        cursor = conn.execute(query)

    results = []
    for row in cursor:
        free_bytes = row["disk_free_bytes"]
        results.append({
            "scan_id": row["id"],
            "started_at": row["started_at"],
            "disk_free_bytes": free_bytes,
            "disk_total_bytes": row["disk_total_bytes"],
            "free_human": _human_size(free_bytes),
        })

    return results


def goal_progress(conn: sqlite3.Connection, goal: dict, *, now: int | None = None) -> dict:
    """Compute live progress for one goal. Progress is derived, never stored.

    All three goal kinds are views over the footprint (DESIGN.md §4/§5):
      - free_amount: bytes reclaimed since the goal was created, vs target.
      - stay_above:  current free space vs threshold.
      - triage:      how many flagged paths are still undecided.

    `goal` is a row dict from database.list_goals (kind, target_bytes,
    threshold_bytes, created_at, ...). Returns a dict the UI can render, e.g.
    {kind, current, target, percent, done, label}.
    """
    if goal["kind"] == "free_amount":
        cursor = conn.execute(
            """SELECT COALESCE(SUM(size_bytes), 0) FROM actions 
               WHERE status = 'done' AND created_at >= ?""",
            (goal["created_at"],)
        )
        current = cursor.fetchone()[0]
        target = goal["target_bytes"]
        done = current >= target
        percent = (current / target * 100) if target > 0 else 0
        
        return {
            "kind": "free_amount",
            "current": current,
            "target": target,
            "percent": percent,
            "done": done,
            "label": f"{_human_size(current)} / {_human_size(target)} freed"
        }
    elif goal["kind"] == "stay_above":
        # Get the latest free space from the scans table
        cursor = conn.execute(
            "SELECT disk_free_bytes FROM scans WHERE status = 'complete' ORDER BY started_at DESC LIMIT 1"
        )
        row = cursor.fetchone()
        current = row["disk_free_bytes"] if row and row["disk_free_bytes"] is not None else 0
        target = goal["threshold_bytes"]
        done = current >= target
        percent = min(100.0, (current / target * 100)) if target > 0 else 100.0
        
        return {
            "kind": "stay_above",
            "current": current,
            "target": target,
            "done": done,
            "label": f"Current: {_human_size(current)} (Target: {_human_size(target)})",
            "percent": percent
        }
    elif goal["kind"] == "triage":
        cursor = conn.execute("SELECT COUNT(*) FROM triage WHERE decision = 'undecided'")
        current = cursor.fetchone()[0]
        done = current == 0
        percent = 100.0 if done else 0.0
        
        return {
            "kind": "triage",
            "current": current,
            "done": done,
            "label": f"{current} paths left to triage",
            "percent": percent
        }
    else:
        raise ValueError


def reclaimable_bytes(conn: sqlite3.Connection, paths: list[str], *,
                      scan_id: int | None = None) -> int:
    """Return the TRUE bytes freed by removing `paths`, reconciling shared inodes.
    """
    if not paths:
        return 0

    if scan_id is None:
        scan_id = get_latest_scan_id(conn)
        if scan_id is None:
            return []

    clauses = []
    params = [scan_id]
    for p in paths:
        clauses.append("(filepath = ? OR filepath LIKE ?)")
        params.extend(p, f"{p}/%")

    where_sql = " OR ".join(clauses)

    query = f"""
        SELECT SUM(size_bytes) FROM (
            SELECT DISTINCT inode, size_bytes 
            FROM files 
            WHERE scan_id = ? AND ({where_sql})
        )
    """

    cursor = conn.execute(query, params)
    result = cursor.fetchone()[0]
    return result if result else 0

def is_dataless(filepath: str) -> bool:
    """True if `filepath` is an iCloud dataless placeholder (not really on disk).
    """
    try:
        st = os.stat(filepath)

        if hasattr(st, 'st_flags'):
            return bool(st.st_flags & getattr(stat, 'SF_DATALESS', 0x40000000))
        else:
            False
    except OSError:
        return False



def _human_size(size_bytes: int) -> str:
    """Format a byte count as a short human string (e.g. 4509715660 -> "4.2 GB")."""

    base = 1000.0

    if size_bytes < base:
        return f"{size_bytes} B"

    size = float(size_bytes)
    for unit in ['KB', 'MB', 'GB', 'TB']:
        size /= base
        if size < base:
            formatted = f"{size:.1f}".rstrip('0').rstrip('.')
            return f"{formatted} {unit}"

    return f"{size:.1f} PB"


def _format_evidence(size_bytes: int, last_modified: int) -> str:
    """Build the human-readable 'why this was flagged' string."""

    human_size = _human_size(size_bytes)
    dt = datetime.datetime.fromtimestamp(last_modified)
    month_year = dt.strftime("%b %Y")

    return f"{human_size} · not modified since {month_year}"
