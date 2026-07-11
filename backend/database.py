"""
database.py — SQLite persistence layer.

Owns the schema and all reads/writes. Nothing else in the app should talk to
sqlite3 directly; keeping SQL in one module means when the schema changes, only
this file changes.

Schema (see DESIGN.md §4):

    scans   one row per scan run — the historical snapshot index.
            (id, root_path, started_at, finished_at, status, total_bytes)
    files   one row per file, belonging to a scan via scan_id.
            (id, scan_id, filepath, size_bytes, last_modified,
             last_accessed, is_symlink, inode)

Retention (DESIGN.md §4): keep every `scans` row forever (tiny, powers trends);
keep `files` rows only for the last N scans (default 12) and prune the rest.

MENTOR NOTES
------------
- SQLite enforces foreign keys only if you turn them on PER CONNECTION:
  `PRAGMA foreign_keys = ON`. Forgetting this is the #1 silent bug here.
- Wrap multi-statement writes in a transaction so a mid-scan crash can't leave a
  half-written snapshot.
- Store `total_bytes` ON the scans row at scan time. Then trends never depend on
  `files` rows that retention may have pruned (ROADMAP Phase 3 pitfall).
"""

import sqlite3

DB_PATH = "storage_advisor.db"

# How many scans' worth of `files` rows to keep. Older scans keep their summary
# row in `scans` but lose their per-file detail.
FILE_RETENTION_SCANS = 12


def get_db_connection() -> sqlite3.Connection:
    """Open a connection with the row factory and pragmas this app expects.

    TODO:
      - connect to DB_PATH
      - conn.row_factory = sqlite3.Row  (so rows behave like dicts)
      - execute "PRAGMA foreign_keys = ON"   <-- do NOT skip this
      - return conn
    """
    # TODO: implement
    raise NotImplementedError


def init_db() -> None:
    """Create the `scans` and `files` tables and indexes if absent.

    Idempotent: safe to call on every startup (use CREATE TABLE IF NOT EXISTS).

    TODO:
      - CREATE TABLE scans  (id PK, root_path, started_at, finished_at,
                             status, total_bytes)
      - CREATE TABLE files  (id PK, scan_id FK -> scans(id), filepath,
                             size_bytes, last_modified, last_accessed,
                             is_symlink, inode)
      - CREATE INDEX on files(scan_id)
      - CREATE INDEX on files(size_bytes)
      - CREATE INDEX on files(last_modified)
        (these three back the "large & stale" query and per-scan lookups)
    """
    # TODO: implement
    raise NotImplementedError


def create_scan(root_path: str, started_at: int) -> int:
    """Insert a new scan row (status='running') and return its id.

    The returned id is the `scan_id` every file row for this run gets tagged
    with. Call this BEFORE scanning so files can reference it.

    TODO: INSERT, then return cursor.lastrowid
    """
    # TODO: implement
    raise NotImplementedError


def finish_scan(scan_id: int, finished_at: int, total_bytes: int,
                status: str = "complete") -> None:
    """Mark a scan finished and record its summary total.

    TODO: UPDATE the scans row (finished_at, total_bytes, status) WHERE id=scan_id
    """
    # TODO: implement
    raise NotImplementedError


def insert_file_batch(scan_id: int, rows: list[tuple]) -> None:
    """Batch-insert a chunk of file rows for one scan.

    `rows` is a list of tuples matching the files columns (minus id/scan_id,
    which this function supplies). The scanner streams batches here rather than
    building one giant list, so memory stays flat on a big home directory.

    TODO:
      - build the INSERT
      - use executemany for the batch
      - commit (or let the caller manage the transaction — your design choice;
        document whichever you pick)
    """
    # TODO: implement
    raise NotImplementedError


def prune_old_scans(keep: int = FILE_RETENTION_SCANS) -> None:
    """Delete `files` rows belonging to all but the most recent `keep` scans.

    Leaves the `scans` summary rows intact (retention rule, DESIGN.md §4).

    TODO:
      - find the scan ids to keep (most recent `keep` by id/started_at)
      - DELETE FROM files WHERE scan_id NOT IN (those)
      - (foreign keys ON + this manual delete is fine; ON DELETE CASCADE is an
        alternative worth reading about)
    """
    # TODO: implement
    raise NotImplementedError
