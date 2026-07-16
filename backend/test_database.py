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

