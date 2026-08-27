"""
test_main.py — tests for the JSON-over-stdio command dispatcher.

We don't drive real stdin/stdout here; instead we monkeypatch `main.send` to
capture the protocol messages the handlers emit, then assert on their shape.
That keeps these tests fast and lets us pin the contract (docs/protocol.md)
without a subprocess.

Run:  pytest backend/test_main.py   (from the repo root)
"""

import pytest

from backend import database, main


@pytest.fixture
def sent(monkeypatch, tmp_path):
    """Capture every message passed to main.send(); isolate the DB to tmp_path.

    init_db() mirrors what main() now does once at sidecar startup — these tests
    call handlers directly (not via the stdio loop), so they must create the
    schema themselves.
    """
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    database.init_db()
    messages = []
    monkeypatch.setattr(main, "send", lambda msg: messages.append(msg))
    return messages


# --- dispatch routing --------------------------------------------------------

def test_unknown_command_returns_error(sent):
    """An unrecognized cmd yields an UNKNOWN_COMMAND error, not a crash."""
    main.dispatch({"id": "r1", "cmd": "bogus", "args": {}})
    assert sent[-1]["type"] == "error"
    assert sent[-1]["error"]["code"] == "UNKNOWN_COMMAND"


def test_missing_id_or_cmd_is_bad_request(sent):
    """Requests must carry id and cmd; otherwise BAD_REQUEST."""
    main.dispatch({"cmd": "scan", "args": {}})  # no id
    assert sent[-1]["type"] == "error"
    assert sent[-1]["error"]["code"] == "BAD_REQUEST"


def test_handler_exception_becomes_internal_error(sent, monkeypatch):
    """A handler blowing up produces an INTERNAL_ERROR message, not a dead loop."""
    def boom(req_id, args):
        raise RuntimeError("kaboom")
    monkeypatch.setitem(main.COMMANDS, "scan", boom)
    main.dispatch({"id": "r1", "cmd": "scan", "args": {}})
    assert sent[-1]["type"] == "error"
    assert sent[-1]["error"]["code"] == "INTERNAL_ERROR"


# --- handle_scan -------------------------------------------------------------

def test_scan_missing_path_auto_targets_home(sent, monkeypatch):
    """Phase 4: a scan with no path auto-targets home, it is NOT an error.

    We stub the scanner so the test doesn't actually walk the real home dir —
    we only care that handle_scan resolves a target and completes rather than
    returning the old INVALID_ARGS error.
    """
    monkeypatch.setattr(main.scanner, "scan_directory", lambda path, progress_callback=None: iter([]))
    main.handle_scan("r1", {})
    assert sent[-1]["type"] == "result"
    # The scan result carries a disk-space snapshot so the UI can flag low space
    # immediately without a second disk_status call.
    assert "disk_free_bytes" in sent[-1]["data"]
    assert "disk_total_bytes" in sent[-1]["data"]


def test_scan_streams_progress_then_result(sent, tmp_path):
    """A real scan emits progress messages (optional) and one terminal result
    carrying the protocol fields the UI expects."""
    # Scan a subdir so the test DB (in tmp_path) isn't itself counted.
    target = tmp_path / "target"
    target.mkdir()
    (target / "a.txt").write_text("hello")
    (target / "b.txt").write_text("world")

    main.handle_scan("r1", {"path": str(target)})

    terminal = sent[-1]
    assert terminal["id"] == "r1"
    assert terminal["type"] == "result"
    # Contract: result must carry these (files_seen was once missing).
    assert set(terminal["data"]) >= {"scan_id", "files_seen", "duration_ms", "total_bytes"}
    assert terminal["data"]["files_seen"] == 2


def test_scan_invalid_path_reports_error(sent, tmp_path):
    """Scanning a nonexistent path ends in an error message, not a traceback."""
    main.handle_scan("r1", {"path": str(tmp_path / "nope")})
    assert sent[-1]["type"] == "error"


# --- handle_top_large_stale --------------------------------------------------

def test_top_large_stale_returns_items_list(sent, tmp_path):
    """After a scan, the query command returns a result with an items list."""
    big = tmp_path / "big.bin"
    big.write_bytes(b"\0" * (200 * 1024 * 1024))
    import os
    old = 1_000_000_000  # year 2001, comfortably stale
    os.utime(big, (old, old))

    main.handle_scan("r1", {"path": str(tmp_path)})
    main.handle_top_large_stale("r2", {"limit": 10, "stale_months": 12})

    terminal = sent[-1]
    assert terminal["id"] == "r2"
    assert terminal["type"] == "result"
    assert "items" in terminal["data"]
    assert any(item["filepath"].endswith("big.bin") for item in terminal["data"]["items"])


# --- handle_trends (Phase 3) -------------------------------------------------

def test_trends_returns_points_list(sent, tmp_path):
    """After a scan, the trends command returns a result with a points list."""
    target = tmp_path / "target"
    target.mkdir()
    (target / "a.txt").write_text("hello")

    main.handle_scan("r1", {"path": str(target)})
    main.handle_trends("r2", {})

    terminal = sent[-1]
    assert terminal["id"] == "r2"
    assert terminal["type"] == "result"
    assert "points" in terminal["data"]
    assert len(terminal["data"]["points"]) == 1


# --- handle_disk_status (Phase 4) --------------------------------------------

def test_disk_status_returns_status(sent, monkeypatch):
    """disk_status returns a live free/total/low-flag reading without a scan."""
    # Monkeypatch the volume read for a deterministic result.
    monkeypatch.setattr(main.disk, "get_disk_usage", lambda path: (300, 1000))
    main.handle_disk_status("d1", {})

    terminal = sent[-1]
    assert terminal["id"] == "d1"
    assert terminal["type"] == "result"
    data = terminal["data"]
    assert data["free_bytes"] == 300
    assert data["total_bytes"] == 1000
    assert data["used_bytes"] == 700
    assert data["is_low"] is False  # 30% free is above the 10% threshold


# --- handle_large_files / handle_folder_rollups (Phase 4.5) ------------------

def test_large_files_returns_items(sent, tmp_path):
    """large_files returns big files by size after a scan."""
    target = tmp_path / "target"
    target.mkdir()
    big = target / "big.bin"
    big.write_bytes(b"\0" * (200 * 1024 * 1024))

    main.handle_scan("r1", {"path": str(target)})
    main.handle_large_files("r2", {})

    terminal = sent[-1]
    assert terminal["type"] == "result"
    assert "items" in terminal["data"]
    assert any(i["filepath"].endswith("big.bin") for i in terminal["data"]["items"])


def test_folder_rollups_returns_folders(sent, tmp_path):
    """folder_rollups returns directory cohorts after a scan."""
    target = tmp_path / "target"
    (target / "sub").mkdir(parents=True)
    (target / "sub" / "big.bin").write_bytes(b"\0" * (200 * 1024 * 1024))

    main.handle_scan("r1", {"path": str(target)})
    main.handle_folder_rollups("r2", {})

    terminal = sent[-1]
    assert terminal["type"] == "result"
    assert "folders" in terminal["data"]
    # the 'sub' cohort should be present with the big file's bytes
    assert any(f["path"].endswith("/sub") for f in terminal["data"]["folders"])


# --- Phase 5: triage / goals handlers ----------------------------------------

def test_set_and_list_triage(sent):
    """set_triage records a decision; list_triage returns it (no scan needed)."""
    main.handle_set_triage("t1", {"path": "/Users/demo/School", "is_dir": True, "decision": "offload"})
    assert sent[-1]["type"] == "result"

    main.handle_list_triage("t2", {"decision": "offload"})
    terminal = sent[-1]
    assert terminal["type"] == "result"
    assert any(r["path"] == "/Users/demo/School" for r in terminal["data"]["items"])


def test_set_triage_rejects_bad_decision(sent):
    """An unknown decision is INVALID_ARGS, not a silent write."""
    main.handle_set_triage("t1", {"path": "/x", "is_dir": False, "decision": "banish"})
    assert sent[-1]["type"] == "error"
    assert sent[-1]["error"]["code"] == "INVALID_ARGS"


def test_create_and_list_goals_with_progress(sent):
    """create_goal then list_goals returns the goal with computed progress attached."""
    main.handle_create_goal("g1", {"kind": "free_amount", "target_bytes": 20_000_000_000})
    assert sent[-1]["type"] == "result"
    assert sent[-1]["data"]["goal_id"] > 0

    main.handle_list_goals("g2", {"status": "active"})
    terminal = sent[-1]
    assert terminal["type"] == "result"
    goals = terminal["data"]["goals"]
    assert len(goals) == 1
    assert "progress" in goals[0]
    assert goals[0]["progress"]["kind"] == "free_amount"


def test_create_goal_rejects_bad_kind(sent):
    """An unknown goal kind is INVALID_ARGS."""
    main.handle_create_goal("g1", {"kind": "world_peace"})
    assert sent[-1]["type"] == "error"
    assert sent[-1]["error"]["code"] == "INVALID_ARGS"


def test_list_goals_works_on_fresh_db(sent):
    """Regression: goals commands must work before any scan (init_db in the loop).

    The `sent` fixture init_db's the schema the same way main() does at startup,
    so list_goals returns an empty list rather than 'no such table'."""
    main.handle_list_goals("g1", {"status": "active"})
    assert sent[-1]["type"] == "result"
    assert sent[-1]["data"]["goals"] == []
