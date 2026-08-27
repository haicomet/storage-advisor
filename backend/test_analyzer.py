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


def _seed_scan(files, *, status="complete", started_at=1_600_000_000,
               disk_free_bytes=None, disk_total_bytes=None):
    """Create one scan, insert `files`, mark it complete; return its scan_id.

    `files` is a list of (filepath, size_bytes, last_modified) triples; the
    remaining columns (atime, is_symlink, inode) are filled with harmless
    defaults since the analyzer doesn't read them. Pass disk_* to exercise the
    free-space history query.
    """
    scan_id = database.create_scan("/Users/demo", started_at)
    batch = [
        (path, size, mtime, mtime, 0, i)
        for i, (path, size, mtime) in enumerate(files)
    ]
    database.insert_file_batch(scan_id, batch)
    database.finish_scan(
        scan_id, started_at + 1, sum(f[1] for f in files), status=status,
        disk_free_bytes=disk_free_bytes, disk_total_bytes=disk_total_bytes,
    )
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


# --- scan_trends (Phase 3) ---------------------------------------------------

def test_trends_empty_when_no_scans(tmp_path, monkeypatch):
    """No completed scans -> [] so the UI shows an empty state, not a broken chart."""
    _fresh_db(tmp_path, monkeypatch)
    with database.get_db_connection() as conn:
        assert analyzer.scan_trends(conn) == []


def test_trends_ordered_oldest_to_newest(tmp_path, monkeypatch):
    """Points come back ascending by started_at, with the right total_bytes each."""
    _fresh_db(tmp_path, monkeypatch)
    # Seed out of chronological order to prove the query sorts, not insert order.
    _seed_scan([("/b", 2000, 1)], started_at=2000)
    _seed_scan([("/a", 1000, 1)], started_at=1000)
    _seed_scan([("/c", 3000, 1)], started_at=3000)
    with database.get_db_connection() as conn:
        points = analyzer.scan_trends(conn)
    assert [p["started_at"] for p in points] == [1000, 2000, 3000]
    assert [p["total_bytes"] for p in points] == [1000, 2000, 3000]


def test_trends_excludes_incomplete_scans(tmp_path, monkeypatch):
    """running/failed scans (partial totals) must NOT appear as trend points."""
    _fresh_db(tmp_path, monkeypatch)
    _seed_scan([("/a", 1000, 1)], status="complete", started_at=1000)
    _seed_scan([("/b", 500, 1)], status="running", started_at=2000)
    _seed_scan([("/c", 700, 1)], status="failed: boom", started_at=3000)
    with database.get_db_connection() as conn:
        points = analyzer.scan_trends(conn)
    assert [p["started_at"] for p in points] == [1000]


def test_trends_rows_match_shape(tmp_path, monkeypatch):
    """Each point carries exactly the fields the chart/types.ts expect."""
    _fresh_db(tmp_path, monkeypatch)
    _seed_scan([("/a", 1000, 1)], started_at=1000)
    with database.get_db_connection() as conn:
        point = analyzer.scan_trends(conn)[0]
    assert set(point) == {"scan_id", "started_at", "total_bytes", "total_human"}


# --- disk_history (Phase 4) --------------------------------------------------

def test_disk_history_empty_when_no_scans(tmp_path, monkeypatch):
    """No scans with disk data -> []."""
    _fresh_db(tmp_path, monkeypatch)
    with database.get_db_connection() as conn:
        assert analyzer.disk_history(conn) == []


def test_disk_history_skips_scans_without_disk_data(tmp_path, monkeypatch):
    """Pre-Phase-4 scans (disk_free_bytes NULL) must not appear as false dips."""
    _fresh_db(tmp_path, monkeypatch)
    _seed_scan([("/a", 100, 1)], started_at=1000)  # no disk_* -> NULL
    _seed_scan([("/b", 100, 1)], started_at=2000,
               disk_free_bytes=500, disk_total_bytes=1000)
    with database.get_db_connection() as conn:
        points = analyzer.disk_history(conn)
    assert [p["started_at"] for p in points] == [2000]
    assert points[0]["disk_free_bytes"] == 500


def test_disk_history_ordered_and_shaped(tmp_path, monkeypatch):
    """Points ascend by time and carry exactly the DiskHistoryPoint fields."""
    _fresh_db(tmp_path, monkeypatch)
    _seed_scan([("/a", 100, 1)], started_at=2000,
               disk_free_bytes=400, disk_total_bytes=1000)
    _seed_scan([("/b", 100, 1)], started_at=1000,
               disk_free_bytes=600, disk_total_bytes=1000)
    with database.get_db_connection() as conn:
        points = analyzer.disk_history(conn)
    assert [p["started_at"] for p in points] == [1000, 2000]
    assert set(points[0]) == {
        "scan_id", "started_at", "disk_free_bytes", "disk_total_bytes", "free_human",
    }


# --- large_files (Phase 4.5) -------------------------------------------------

def test_large_files_empty_when_no_scans(tmp_path, monkeypatch):
    """No scans -> [] (empty state, not an error)."""
    _fresh_db(tmp_path, monkeypatch)
    with database.get_db_connection() as conn:
        assert analyzer.large_files(conn) == []


def test_large_files_ranked_by_size_no_staleness(tmp_path, monkeypatch):
    """Ranked by size DESC, and RECENT files are included (offload != delete)."""
    _fresh_db(tmp_path, monkeypatch)
    big = 200 * 1024 * 1024
    bigger = 500 * 1024 * 1024
    small = 1024
    recent = 2_000_000_000  # fresh mtime — would be excluded by top_large_stale
    _seed_scan([
        ("/big", big, recent),
        ("/bigger", bigger, recent),
        ("/small", small, recent),
    ])
    with database.get_db_connection() as conn:
        rows = analyzer.large_files(conn)
    # small is below the 100 MB default; big/bigger present, largest first.
    assert [r["filepath"] for r in rows] == ["/bigger", "/big"]


def test_large_files_rows_match_shape(tmp_path, monkeypatch):
    """Each row carries exactly {filepath, size_bytes, size_human} — no evidence."""
    _fresh_db(tmp_path, monkeypatch)
    _seed_scan([("/big", 300 * 1024 * 1024, 1)])
    with database.get_db_connection() as conn:
        row = analyzer.large_files(conn)[0]
    assert set(row) == {"filepath", "size_bytes", "size_human"}


def test_large_files_respects_limit(tmp_path, monkeypatch):
    """`limit` caps the number of rows."""
    _fresh_db(tmp_path, monkeypatch)
    big = 200 * 1024 * 1024
    _seed_scan([(f"/f{i}", big + i, 1) for i in range(5)])
    with database.get_db_connection() as conn:
        rows = analyzer.large_files(conn, limit=2)
    assert len(rows) == 2


# --- folder_rollups (Phase 4.5) ----------------------------------------------

def test_folder_rollups_sums_recursively(tmp_path, monkeypatch):
    """A folder's size is its whole subtree: School = Fall2024 + Spring2025."""
    _fresh_db(tmp_path, monkeypatch)
    mb = 1024 * 1024
    _seed_scan([
        ("/root/School/Fall2024/a.mp4", 200 * mb, 1),
        ("/root/School/Spring2025/b.pdf", 150 * mb, 1),
        ("/root/Movies/c.mkv", 300 * mb, 1),
    ])
    with database.get_db_connection() as conn:
        rollups = {r["path"]: r for r in analyzer.folder_rollups(conn, min_size_bytes=0)}
    # School rolls up both semesters; Movies is just its one file.
    assert rollups["/root/School"]["total_bytes"] == 350 * mb
    assert rollups["/root/School"]["file_count"] == 2
    assert rollups["/root/Movies"]["total_bytes"] == 300 * mb
    # Deepest leaf carries only its own file.
    assert rollups["/root/School/Fall2024"]["total_bytes"] == 200 * mb


def test_folder_rollups_ranked_and_filtered(tmp_path, monkeypatch):
    """Ranked by total size DESC; folders below min_size_bytes are dropped."""
    _fresh_db(tmp_path, monkeypatch)
    mb = 1024 * 1024
    _seed_scan([
        ("/root/Big/x", 300 * mb, 1),
        ("/root/Small/y", 1 * mb, 1),
    ])
    with database.get_db_connection() as conn:
        rollups = analyzer.folder_rollups(conn, min_size_bytes=100 * mb)
    paths = [r["path"] for r in rollups]
    assert "/root/Small" not in paths          # filtered out (too small)
    assert paths[0] == "/root/Big" or paths[0] == "/root"  # biggest ranked first
    assert rollups == sorted(rollups, key=lambda r: r["total_bytes"], reverse=True)


def test_folder_rollups_rows_match_shape(tmp_path, monkeypatch):
    """Each rollup carries exactly the FolderRollup fields."""
    _fresh_db(tmp_path, monkeypatch)
    _seed_scan([("/root/A/f", 300 * 1024 * 1024, 1)])
    with database.get_db_connection() as conn:
        row = analyzer.folder_rollups(conn, min_size_bytes=0)[0]
    assert set(row) == {"path", "total_bytes", "total_human", "file_count"}


# --- goal_progress (Phase 5) -------------------------------------------------

def test_goal_progress_free_amount_counts_done_actions(tmp_path, monkeypatch):
    """free_amount progress = bytes reclaimed by 'done' actions since goal created."""
    _fresh_db(tmp_path, monkeypatch)
    # A completed action worth 5 GB, created after the goal.
    aid = database.record_action("trash", "/x", is_dir=False, size_bytes=5_000_000_000, created_at=1500)
    database.complete_action(aid, status="done", completed_at=1600)
    goal = {"kind": "free_amount", "target_bytes": 10_000_000_000, "created_at": 1000}
    with database.get_db_connection() as conn:
        p = analyzer.goal_progress(conn, goal)
    assert p["current"] == 5_000_000_000
    assert p["percent"] == 50.0
    assert p["done"] is False


def test_goal_progress_free_amount_ignores_pending_and_older(tmp_path, monkeypatch):
    """Only 'done' actions created on/after the goal count toward progress."""
    _fresh_db(tmp_path, monkeypatch)
    # pending action — must not count
    database.record_action("trash", "/p", is_dir=False, size_bytes=9_000_000_000, created_at=1500)
    # done but BEFORE the goal was created — must not count
    old = database.record_action("trash", "/o", is_dir=False, size_bytes=9_000_000_000, created_at=500)
    database.complete_action(old, status="done", completed_at=600)
    goal = {"kind": "free_amount", "target_bytes": 10_000_000_000, "created_at": 1000}
    with database.get_db_connection() as conn:
        p = analyzer.goal_progress(conn, goal)
    assert p["current"] == 0


def test_goal_progress_stay_above_reads_latest_free(tmp_path, monkeypatch):
    """stay_above compares the latest scan's free space to the threshold."""
    _fresh_db(tmp_path, monkeypatch)
    _seed_scan([("/a", 1, 1)], started_at=1000, disk_free_bytes=30_000_000_000,
               disk_total_bytes=100_000_000_000)
    _seed_scan([("/b", 1, 1)], started_at=2000, disk_free_bytes=60_000_000_000,
               disk_total_bytes=100_000_000_000)  # latest
    goal = {"kind": "stay_above", "threshold_bytes": 50_000_000_000, "created_at": 1}
    with database.get_db_connection() as conn:
        p = analyzer.goal_progress(conn, goal)
    assert p["current"] == 60_000_000_000
    assert p["done"] is True


def test_goal_progress_triage_counts_undecided(tmp_path, monkeypatch):
    """triage progress = number of paths still undecided; done when zero."""
    _fresh_db(tmp_path, monkeypatch)
    database.set_triage("/a", is_dir=True, decision="undecided", decided_at=1)
    database.set_triage("/b", is_dir=True, decision="keep", decided_at=2)
    goal = {"kind": "triage", "created_at": 1}
    with database.get_db_connection() as conn:
        p = analyzer.goal_progress(conn, goal)
    assert p["current"] == 1
    assert p["done"] is False


def test_goal_progress_all_kinds_have_percent(tmp_path, monkeypatch):
    """Every kind returns a percent (the UI progress bar reads it for all)."""
    _fresh_db(tmp_path, monkeypatch)
    _seed_scan([("/a", 1, 1)], started_at=1000, disk_free_bytes=50, disk_total_bytes=100)
    goals = [
        {"kind": "free_amount", "target_bytes": 100, "created_at": 1},
        {"kind": "stay_above", "threshold_bytes": 100, "created_at": 1},
        {"kind": "triage", "created_at": 1},
    ]
    with database.get_db_connection() as conn:
        for g in goals:
            assert "percent" in analyzer.goal_progress(conn, g)
