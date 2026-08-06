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
    """Capture every message passed to main.send(); isolate the DB to tmp_path."""
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
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

def test_scan_missing_path_is_invalid_args(sent):
    """A scan with no path returns INVALID_ARGS before touching the disk."""
    main.handle_scan("r1", {})
    assert sent[-1]["type"] == "error"
    assert sent[-1]["error"]["code"] == "INVALID_ARGS"


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
    # TODO: scan a subdir (so the test DB isn't counted — see
    #   test_scan_streams_progress_then_result), then main.handle_trends("r2", {}).
    #   Assert sent[-1]["type"] == "result" and "points" in sent[-1]["data"], and
    #   that the point's total_bytes matches the scanned bytes.
    raise NotImplementedError
