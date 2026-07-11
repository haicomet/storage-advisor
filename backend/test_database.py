"""
test_database.py — tests for the persistence layer.

The tricky part: database.py hardcodes DB_PATH to a file. For tests you want a
throwaway database so runs are isolated and repeatable.

MENTOR NOTE
-----------
This tension ("my module hardcodes its DB path, but my test needs a different
one") is a real design lesson. Two ways out:
  (a) monkeypatch database.DB_PATH to point at tmp_path/"test.db" (quick), or
  (b) refactor database.py so functions accept a connection/path (cleaner, and
      what you'd do in production code).
Option (b) is the better habit — consider it when you implement. Either is fine
for Phase 1; just pick one and be consistent.

Run:  pytest backend/test_database.py
"""

import database


def test_init_db_creates_tables(tmp_path, monkeypatch):
    """init_db creates the scans and files tables."""
    # TODO:
    #   monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    #   database.init_db()
    #   query sqlite_master, assert both 'scans' and 'files' exist
    raise NotImplementedError


def test_create_and_finish_scan(tmp_path, monkeypatch):
    """A scan can be created (status running) then finished (status complete)."""
    # TODO: create_scan -> assert an id comes back; finish_scan -> assert the
    # row now has status complete and the total_bytes you passed
    raise NotImplementedError


def test_insert_file_batch_roundtrip(tmp_path, monkeypatch):
    """Inserted file rows can be read back and belong to the right scan."""
    # TODO: create a scan, insert a small batch, query files WHERE scan_id=...,
    # assert count and that a known filepath/size survived the roundtrip
    raise NotImplementedError


def test_prune_keeps_only_recent_scans(tmp_path, monkeypatch):
    """prune_old_scans drops file rows for old scans but keeps scan summaries."""
    # TODO: create more than FILE_RETENTION_SCANS scans each with a file row,
    # prune, then assert:
    #   - files rows only remain for the most recent N scans
    #   - ALL scans rows still exist (summaries are never pruned)
    # This is the retention rule from DESIGN.md §4 — worth locking down with a test.
    raise NotImplementedError
