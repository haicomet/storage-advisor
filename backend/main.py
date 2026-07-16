"""
main.py — the sidecar entry point: a JSON-over-stdio command loop.

Tauri spawns this process and talks to it over stdin/stdout using line-delimited
JSON (one complete JSON object per line). This module reads request lines,
dispatches to the scanner/analyzer, and writes progress + a terminal
result/error line per request. See docs/protocol.md for the exact wire format.

TWO HARD RULES (docs/protocol.md, ROADMAP Phase 2 pitfalls):
  1. stdout is DATA ONLY. Every log/debug/traceback goes to stderr. A stray
     print() to stdout corrupts the channel.
  2. FLUSH after every message, or run unbuffered (python -u). Without flushing,
     Python buffers stdout and the UI hangs waiting for a line that never comes.

Run standalone for manual testing (paste JSON lines on stdin):
    python -m backend.main
"""

import sys
import json

# NOTE: keep imports package-relative so `python -m backend.main` works from the
# repo root (same fix tracked for scan_cli). e.g. from .analyzer import ...


def send(message: dict) -> None:
    """Write one protocol message to stdout as a single JSON line, then flush.

    TODO:
      - json.dumps(message) then write it followed by "\\n".
      - Flush immediately (print(..., flush=True) or sys.stdout.flush()).
      - This is the ONLY function allowed to write to stdout. Route everything
        through it so the "data only + always flush" rules can't be violated
        accidentally.
    """
    # TODO: implement
    raise NotImplementedError


def log(message: str) -> None:
    """Write a human/debug line to stderr (never stdout).

    TODO:
      - Write to sys.stderr with a trailing newline and flush.
    Why: stderr is the safe channel for diagnostics; stdout is reserved for
    protocol JSON only.
    """
    # TODO: implement
    raise NotImplementedError


def handle_scan(req_id: str, args: dict) -> None:
    """Handle a `scan` request: walk the path, stream progress, insert rows, finish.

    Emits: zero or more {type:"progress"} messages, then exactly one
    {type:"result"} (scan_id, files_seen, duration_ms) or {type:"error"}.

    TODO:
      - Read `path` from args; validate it.
      - init_db(); create_scan(); iterate scan_directory(path, progress_callback=...)
        where the callback maps the scanner's dict into a protocol `progress`
        message and calls send(). Insert each batch via insert_file_batch().
      - On success: finish_scan(...) then send one `result`. On failure: set the
        scan status failed and send one `error` (map PermissionError ->
        code "PERMISSION_DENIED", etc.). prune_old_scans() at the end.
      - Reuse the pipeline you already proved in scan_cli.py — this is that logic
        with protocol messages instead of stderr prints. Consider extracting the
        shared run into one place so CLI and sidecar don't drift.
    """
    # TODO: implement
    raise NotImplementedError


def handle_top_large_stale(req_id: str, args: dict) -> None:
    """Handle a `top_large_stale` request: query and return ranked file rows.

    Emits exactly one {type:"result", data:{items:[file row, ...]}}.

    TODO:
      - Pull optional `limit` / `stale_months` from args (fall back to defaults).
      - Open a connection, call analyzer.top_large_stale(...), send the list back
        under data.items. No progress messages — this is a fast read.
    """
    # TODO: implement
    raise NotImplementedError


# Maps a protocol `cmd` string to its handler. Add `trends` here in Phase 3.
COMMANDS = {
    # "scan": handle_scan,
    # "top_large_stale": handle_top_large_stale,
}


def dispatch(request: dict) -> None:
    """Route one parsed request dict to the right handler.

    TODO:
      - Read `id`, `cmd`, `args` from the request.
      - Look `cmd` up in COMMANDS; if unknown, send an `error` (e.g. code
        "UNKNOWN_COMMAND") rather than crashing the loop.
      - Wrap the handler call so one bad request produces an `error` message,
        not a dead sidecar (a crash here takes down every future request too).
    """
    # TODO: implement
    raise NotImplementedError


def main() -> int:
    """Read stdin line by line, parse JSON, dispatch. Runs until stdin closes.

    TODO:
      - Loop over sys.stdin. Skip blank lines. json.loads each line inside a
        try/except so a single malformed line sends an `error` and continues.
      - Call dispatch() per request. Return 0 when stdin reaches EOF (Tauri
        closed the pipe / app is quitting).
    Design note: this is a plain synchronous loop on purpose — DESIGN.md §3 says
    NOT to reach for asyncio. One request at a time, streaming progress, is
    simpler and correct for a single-user disk walk.
    """
    # TODO: implement
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main())
