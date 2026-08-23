"""
database.py — SQLite persistence layer.

Owns the schema and all reads/writes. Nothing else in the app should talk to
sqlite3 directly; keeping SQL in one module means when the schema changes, only
this file changes.

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
                total_bytes INTEGER,
                disk_free_bytes INTEGER,
                disk_total_bytes INTEGER
            )
        """
        )

        cursor = conn.execute("PRAGMA table_info(scans)")
        columns = [row["name"] for row in cursor.fetchall()]
        
        if "disk_free_bytes" not in columns:
            conn.execute("ALTER TABLE scans ADD COLUMN disk_free_bytes INTEGER")
        if "disk_total_bytes" not in columns:
            conn.execute("ALTER TABLE scans ADD COLUMN disk_total_bytes INTEGER")

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

        # --- Phase 5: the footprint (persists across sessions) ---------------
        # `actions` is the permanent log of what the app did to the user's files
        # AND the undo record. Never pruned. `path` may be a file OR a folder
        # (is_dir), because triage/offload act on folder cohorts (DESIGN.md §4).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,              -- 'trash' | 'offload'
                path TEXT NOT NULL,
                is_dir INTEGER NOT NULL,         -- 0 file, 1 directory (cohort)
                dest_path TEXT,                  -- offload destination (NULL for trash)
                size_bytes INTEGER,
                inode INTEGER,
                status TEXT NOT NULL,            -- 'pending' | 'done' | 'failed' | 'undone'
                created_at INTEGER NOT NULL,
                completed_at INTEGER,
                undo_token TEXT
            )
        """)

        # Persistent per-path keep/delete/offload decisions the user makes over
        # time. `path` may be a directory (a cohort). One row per path (latest
        # decision wins — upsert on path).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS triage (
                path TEXT PRIMARY KEY,
                is_dir INTEGER NOT NULL,
                decision TEXT NOT NULL,          -- 'keep' | 'delete' | 'offload' | 'undecided'
                decided_at INTEGER NOT NULL
            )
        """)

        # A goal the user is working toward. Progress is COMPUTED (analyzer),
        # not stored — these rows just hold the target/config.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,              -- 'free_amount' | 'stay_above' | 'triage'
                target_bytes INTEGER,            -- for free_amount
                threshold_bytes INTEGER,         -- for stay_above
                created_at INTEGER NOT NULL,
                status TEXT NOT NULL             -- 'active' | 'achieved' | 'abandoned'
            )
        """)


def record_action(kind: str, path: str, is_dir: bool, *, dest_path: str | None = None,
                   size_bytes: int | None = None, inode: int | None = None,
                   created_at: int) -> int:
    """Insert a new action row (status='pending') and return its id.

    Called by the safe-action framework (Phase 6) BEFORE touching the filesystem
    — the row exists first so an interrupted action is always recoverable. Only
    the insert lives here; status transitions use complete_action().

    TODO:
      - INSERT INTO actions (kind, path, is_dir, dest_path, size_bytes, inode,
        status, created_at) VALUES (..., 'pending', ...); return lastrowid.
    """
    # TODO: implement
    raise NotImplementedError


def complete_action(action_id: int, *, status: str, completed_at: int,
                    undo_token: str | None = None) -> None:
    """Mark an action done/failed/undone and record its undo token.

    TODO:
      - UPDATE actions SET status=?, completed_at=?, undo_token=? WHERE id=?.
    """
    # TODO: implement
    raise NotImplementedError


def set_triage(path: str, is_dir: bool, decision: str, decided_at: int) -> None:
    """Upsert the user's keep/delete/offload decision for one path.

    TODO:
      - INSERT INTO triage (...) VALUES (...) ON CONFLICT(path) DO UPDATE SET
        decision=excluded.decision, decided_at=excluded.decided_at, is_dir=...
      - Latest decision for a path wins (one row per path).
    """
    # TODO: implement
    raise NotImplementedError


def list_triage(decision: str | None = None) -> list[dict]:
    """Return triage rows, optionally filtered to one decision (e.g. 'undecided').

    TODO:
      - SELECT * FROM triage [WHERE decision = ?] ORDER BY decided_at DESC.
      - Return list of dicts.
    """
    # TODO: implement
    raise NotImplementedError


def create_goal(kind: str, *, target_bytes: int | None = None,
                threshold_bytes: int | None = None, created_at: int) -> int:
    """Insert a new goal (status='active') and return its id.

    TODO:
      - INSERT INTO goals (kind, target_bytes, threshold_bytes, created_at,
        status) VALUES (..., 'active'); return lastrowid.
    """
    # TODO: implement
    raise NotImplementedError


def list_goals(status: str | None = None) -> list[dict]:
    """Return goal rows, optionally filtered by status (e.g. 'active').

    TODO:
      - SELECT * FROM goals [WHERE status = ?] ORDER BY created_at DESC.
      - Progress is NOT stored here — analyzer.goal_progress computes it per goal.
    """
    # TODO: implement
    raise NotImplementedError


def create_scan(root_path: str, started_at: int) -> int:
    # Insert a new scan row (status='running') and return its id.
    with get_db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO scans (root_path, started_at, status) VALUES (?, ?, ?)",
            (root_path, started_at, "running")
        )
        return cursor.lastrowid


def finish_scan(scan_id: int, finished_at: int, total_bytes: int,
                status: str = "complete",
                disk_free_bytes: int | None = None,
                disk_total_bytes: int | None = None) -> None:
    """Mark a scan finished and record its summary total + disk-space snapshot.

    disk_free_bytes / disk_total_bytes capture how full the VOLUME was at scan
    time (from disk.get_disk_usage) — this is what powers the free-space trend
    and the low-space flag. They're optional so existing callers/tests keep
    working; when omitted the columns stay NULL.

    """
    with get_db_connection() as conn:
        conn.execute(
            """UPDATE scans
            SET finished_at = ?,
                total_bytes = ?,
                status = ?,
                disk_free_bytes = ?,
                disk_total_bytes = ?
            WHERE id = ?
            """,
            (finished_at, total_bytes, status, disk_free_bytes, disk_total_bytes, scan_id)
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
