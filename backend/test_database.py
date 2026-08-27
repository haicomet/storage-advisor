"""
test_database.py — tests for the persistence layer.
"""

from backend import database
import sqlite3


def test_init_db_creates_tables(tmp_path, monkeypatch):
    """init_db creates the scans and files tables."""

    test_db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", str(test_db))
    database.init_db()

    with sqlite3.connect(test_db) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

    assert "scans" in tables
    assert "files" in tables
    # Phase 5 footprint tables
    assert "actions" in tables
    assert "triage" in tables
    assert "goals" in tables


def test_create_and_finish_scan(tmp_path, monkeypatch):
    """A scan can be created (status running) then finished (status complete)."""

    test_db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", str(test_db))
    database.init_db()

    scan_id = database.create_scan(root_path="/Users/demo", started_at=1600000000)
    assert scan_id > 0

    database.finish_scan(scan_id, finished_at=1600000050, total_bytes=1048576, status="complete")

    with sqlite3.connect(test_db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()

    assert row["status"] == "complete"
    assert row["total_bytes"] == 1048576
    assert row["started_at"] == 1600000000
    assert row["finished_at"] == 1600000050


def test_insert_file_batch_roundtrip(tmp_path, monkeypatch):
    """Inserted file rows can be read back and belong to the right scan."""

    test_db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", str(test_db))
    database.init_db()

    scan_id = database.create_scan("/Users/demo", 1600000000)

    batch = [
        ("/Users/demo/file1.txt", 1024, 1500000000, 1500000000, 0, 99991),
        ("/Users/demo/file2.txt", 2048, 1500000000, 1500000000, 0, 99992)
    ]
    database.insert_file_batch(scan_id, batch)

    with sqlite3.connect(test_db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM files WHERE scan_id = ?", (scan_id,)).fetchall()

    assert len(rows) == 2

    filepaths = {r["filepath"] for r in rows}
    assert "/Users/demo/file1.txt" in filepaths
    assert "/Users/demo/file2.txt" in filepaths


def test_prune_keeps_only_recent_scans(tmp_path, monkeypatch):
    """prune_old_scans drops file rows for old scans but keeps scan summaries."""

    test_db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", str(test_db))
    database.init_db()

    total_scans_to_run = database.FILE_RETENTION_SCANS + 3

    for i in range(total_scans_to_run):
        scan_id = database.create_scan("/Users/demo", started_at=1000 + i)
        database.insert_file_batch(scan_id, [
            (f"/Users/demo/file_{i}.txt", 100, 1000, 1000, 0, i)
        ])

    database.prune_old_scans()

    with sqlite3.connect(test_db) as conn:
        scan_count = conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
        retained_file_scans = conn.execute("SELECT COUNT(DISTINCT scan_id) FROM files").fetchone()[0]

    assert scan_count == total_scans_to_run
    assert retained_file_scans == database.FILE_RETENTION_SCANS


# --- Phase 5: footprint (actions / triage / goals) ---------------------------

def _fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    database.init_db()


def test_record_action_starts_pending(tmp_path, monkeypatch):
    """record_action inserts a 'pending' row before the filesystem is touched."""
    _fresh(tmp_path, monkeypatch)
    action_id = database.record_action(
        "trash", "/Users/demo/old", is_dir=True, size_bytes=4096, created_at=1000
    )
    assert action_id > 0
    with database.get_db_connection() as conn:
        row = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    assert row["status"] == "pending"
    assert row["kind"] == "trash"
    assert row["is_dir"] == 1
    assert row["completed_at"] is None


def test_complete_action_marks_done_with_undo(tmp_path, monkeypatch):
    """complete_action transitions the row and records the undo token."""
    _fresh(tmp_path, monkeypatch)
    action_id = database.record_action("trash", "/x", is_dir=False, created_at=1000)
    database.complete_action(action_id, status="done", completed_at=2000, undo_token="tok-1")
    with database.get_db_connection() as conn:
        row = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    assert row["status"] == "done"
    assert row["completed_at"] == 2000
    assert row["undo_token"] == "tok-1"


def test_set_triage_upserts_latest_decision(tmp_path, monkeypatch):
    """A second decision on the same path overwrites the first (one row per path)."""
    _fresh(tmp_path, monkeypatch)
    database.set_triage("/Users/demo/School", is_dir=True, decision="offload", decided_at=1000)
    database.set_triage("/Users/demo/School", is_dir=True, decision="keep", decided_at=2000)
    rows = database.list_triage()
    assert len(rows) == 1
    assert rows[0]["decision"] == "keep"
    assert rows[0]["decided_at"] == 2000


def test_list_triage_filters_by_decision(tmp_path, monkeypatch):
    """list_triage(decision) returns only matching rows."""
    _fresh(tmp_path, monkeypatch)
    database.set_triage("/a", is_dir=False, decision="delete", decided_at=1)
    database.set_triage("/b", is_dir=False, decision="keep", decided_at=2)
    delete_only = database.list_triage("delete")
    assert [r["path"] for r in delete_only] == ["/a"]


def test_create_and_list_goals(tmp_path, monkeypatch):
    """create_goal inserts an active goal that list_goals returns."""
    _fresh(tmp_path, monkeypatch)
    goal_id = database.create_goal("free_amount", target_bytes=20_000_000_000, created_at=1000)
    assert goal_id > 0
    active = database.list_goals("active")
    assert len(active) == 1
    assert active[0]["id"] == goal_id
    assert active[0]["kind"] == "free_amount"
    assert active[0]["target_bytes"] == 20_000_000_000
    assert active[0]["status"] == "active"

