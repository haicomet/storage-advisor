"""
test_analyzer.py — tests for the read-only "Large & Stale" analytics.

The analyzer is the product's trust surface: if size formatting or the
large/stale filter is wrong, the app confidently shows the user false evidence.
The `_human_size` tests below exist specifically because an off-by-1000 unit bug
shipped once — pin the behavior down so it can't regress.

Run:  pytest backend/test_analyzer.py   (from the repo root)
"""

import sqlite3

from backend import database, analyzer


# --- fixtures / helpers ------------------------------------------------------

def _fresh_db(tmp_path, monkeypatch):
    """Point database.DB_PATH at a throwaway file and init the schema."""
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    database.init_db()


def _seed_scan(files, *, status="complete", started_at=1_600_000_000):
    """Create one scan, insert `files`, mark it complete; return its scan_id.

    `files` is a list of (filepath, size_bytes, last_modified) triples; the
    remaining columns (atime, is_symlink, inode) are filled with harmless
    defaults since the analyzer doesn't read them.
    """
    scan_id = database.create_scan("/Users/demo", started_at)
    batch = [
        (path, size, mtime, mtime, 0, i)
        for i, (path, size, mtime) in enumerate(files)
    ]
    database.insert_file_batch(scan_id, batch)
    database.finish_scan(scan_id, started_at + 1, sum(f[1] for f in files), status=status)
    return scan_id


# --- _human_size -------------------------------------------------------------

def test_human_size_uses_correct_units():
    """Bytes must map to the right unit — this is the regression guard for the
    off-by-1000 bug (200 MB was once reported as 200 GB)."""
    assert analyzer._human_size(500) == "500 B"
    assert analyzer._human_size(5_000) == "5 KB"
    assert analyzer._human_size(2_000_000) == "2 MB"
    assert analyzer._human_size(200_000_000) == "200 MB"
    assert analyzer._human_size(4_500_000_000) == "4.5 GB"
    assert analyzer._human_size(1_500_000_000_000) == "1.5 TB"


def test_human_size_keeps_one_decimal():
    """Non-round sizes keep a single decimal place."""
    assert analyzer._human_size(1536) == "1.5 KB"


# --- _format_evidence --------------------------------------------------------

def test_format_evidence_combines_size_and_date():
    """Evidence carries the human size and a month/year — the 'why flagged' string."""
    evidence = analyzer._format_evidence(4_500_000_000, 1_560_000_000)  # ~2019
    assert "4.5 GB" in evidence
    assert "not modified since" in evidence
    assert "2019" in evidence


# --- get_latest_scan_id ------------------------------------------------------

def test_latest_scan_id_none_when_empty(tmp_path, monkeypatch):
    """No scans -> None, so callers can render an empty state, not crash."""
    _fresh_db(tmp_path, monkeypatch)
    with database.get_db_connection() as conn:
        assert analyzer.get_latest_scan_id(conn) is None


def test_latest_scan_id_ignores_incomplete(tmp_path, monkeypatch):
    """Only completed scans count as 'latest' (a running scan isn't queryable)."""
    _fresh_db(tmp_path, monkeypatch)
    done = _seed_scan([("/a", 1, 1)], status="complete", started_at=1000)
    database.create_scan("/Users/demo", started_at=2000)  # newer, still 'running'
    with database.get_db_connection() as conn:
        assert analyzer.get_latest_scan_id(conn) == done


# --- top_large_stale ---------------------------------------------------------

def test_top_large_stale_empty_when_no_scans(tmp_path, monkeypatch):
    """No data -> [] (empty state), never an error."""
    _fresh_db(tmp_path, monkeypatch)
    with database.get_db_connection() as conn:
        assert analyzer.top_large_stale(conn) == []


def test_top_large_stale_filters_small_and_fresh(tmp_path, monkeypatch):
    """Only files that are BOTH large AND stale come back."""
    _fresh_db(tmp_path, monkeypatch)
    now = 2_000_000_000
    two_years = now - 2 * 365 * 24 * 3600
    yesterday = now - 24 * 3600
    big = 200 * 1024 * 1024   # over the 100 MB default
    small = 1024
    _seed_scan([
        ("/big_old", big, two_years),      # kept: large + stale
        ("/big_fresh", big, yesterday),    # dropped: not stale
        ("/small_old", small, two_years),  # dropped: not large
    ])
    with database.get_db_connection() as conn:
        rows = analyzer.top_large_stale(conn, now=now)
    paths = [r["filepath"] for r in rows]
    assert paths == ["/big_old"]


def test_top_large_stale_ranks_by_size_times_age(tmp_path, monkeypatch):
    """Ranking is size × age, descending — the explainable score."""
    _fresh_db(tmp_path, monkeypatch)
    now = 2_000_000_000
    old = now - 5 * 365 * 24 * 3600
    older = now - 6 * 365 * 24 * 3600
    big = 500 * 1024 * 1024
    bigger = 900 * 1024 * 1024
    _seed_scan([
        ("/big_old", big, old),
        ("/bigger_older", bigger, older),   # highest size×age -> first
    ])
    with database.get_db_connection() as conn:
        rows = analyzer.top_large_stale(conn, now=now)
    assert [r["filepath"] for r in rows] == ["/bigger_older", "/big_old"]


def test_top_large_stale_respects_limit(tmp_path, monkeypatch):
    """`limit` caps the number of rows returned."""
    _fresh_db(tmp_path, monkeypatch)
    now = 2_000_000_000
    old = now - 3 * 365 * 24 * 3600
    big = 200 * 1024 * 1024
    _seed_scan([(f"/f{i}", big + i, old) for i in range(5)])
    with database.get_db_connection() as conn:
        rows = analyzer.top_large_stale(conn, now=now, limit=2)
    assert len(rows) == 2


def test_top_large_stale_rows_match_protocol_shape(tmp_path, monkeypatch):
    """Each row carries exactly the protocol `file row` fields the UI renders."""
    _fresh_db(tmp_path, monkeypatch)
    now = 2_000_000_000
    old = now - 3 * 365 * 24 * 3600
    _seed_scan([("/big_old", 300 * 1024 * 1024, old)])
    with database.get_db_connection() as conn:
        row = analyzer.top_large_stale(conn, now=now)[0]
    assert set(row) == {"filepath", "size_bytes", "last_modified", "size_human", "evidence"}
