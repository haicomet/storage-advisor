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
    # Open a connection with the row factory and pragmas this app expects.

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn



def init_db() -> None:
    # Create the `scans` and `files` tables and indexes if absent.


    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                root_path TEXT NOT NULL,
                started_at INTEGER NOT NULL,
                finished_at INTEGER,
                status TEXT NOT NULL,
                total_bytes INTEGER
            )
        """
        )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER NOT NULL,
                filepath TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                last_modified INTEGER NOT NULL,
                last_accessed INTEGER NOT NULL,
                is_symlink INTEGER NOT NULL,
                inode INTEGER NOT NULL,
                FOREIGN KEY(scan_id) REFERENCES scans(id)
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_scan_id ON files(scan_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_size ON files(size_bytes)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_last_mod ON files(last_modified)")


def create_scan(root_path: str, started_at: int) -> int:
    # Insert a new scan row (status='running') and return its id.
    with get_db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO scans (root_path, started_at, status) VALUES (?, ?, ?)",
            (root_path, started_at, "running")
        )
        return cursor.lastrowid


def finish_scan(scan_id: int, finished_at: int, total_bytes: int,
                status: str = "complete") -> None:
    # Mark a scan finished and record its summary total.

    with get_db_connection() as conn:
        conn.execute(
            "UPDATE scans SET finished_at = ?, total_bytes = ?, status = ? WHERE id = ?",
            (finished_at, total_bytes, status, scan_id)
        )


def insert_file_batch(scan_id: int, rows: list[tuple]) -> None:
    """Batch-insert a chunk of file rows for one scan.

    `rows` is a list of tuples matching the files columns (minus id/scan_id,
    which this function supplies). The scanner streams batches here rather than
    building one giant list, so memory stays flat on a big home directory.
    """

    batch = [(scan_id,) + row for row in rows]

    with get_db_connection() as conn:
        conn.executemany(
            """
            INSERT INTO files (
                scan_id, filepath, size_bytes, last_modified, 
                last_accessed, is_symlink, inode
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            batch
        )


def prune_old_scans(keep: int = FILE_RETENTION_SCANS) -> None:
    # Delete `files` rows belonging to all but the most recent `keep` scans.

    with get_db_connection() as conn:
        conn.execute(
            """
            DELETE FROM files
            WHERE scan_id NOT IN (
                SELECT id FROM scans 
                ORDER BY started_at DESC 
                LIMIT ?
            )
            """,
            (keep,)
        )
