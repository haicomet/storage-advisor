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
import time

from . import database
from . import scanner
from . import analyzer
from . import disk
from . import actions
from . import volumes

# NOTE: keep imports package-relative so `python -m backend.main` works from the
# repo root (same fix tracked for scan_cli). e.g. from .analyzer import ...


def send(message: dict) -> None:
    """Write one protocol message to stdout as a single JSON line, then flush."""

    json_str = json.dumps(message)
    print(json_str, flush=True)


def log(message: str) -> None:
    """Write a human/debug line to stderr (never stdout)."""

    print(message, file=sys.stderr, flush=True)


def handle_scan(req_id: str, args: dict) -> None:
    """Handle a `scan` request: walk the path, stream progress, insert rows, finish."""

    # Phase 4: no path means "scan the default target" (home dir), not an error.
    target_path = disk.resolve_scan_target(args.get("path"))

    log(f"[scan] Starting scan of {target_path}")
    started_at = int(time.time())
    scan_id = database.create_scan(target_path, started_at)
    total_bytes = 0
    files_seen = 0

    # The callback maps the scanner's raw dict into a valid protocol progress message
    def _progress_cb(update: dict):
        send({
            "id": req_id,
            "type": "progress",
            "data": update
        })

    try:
        start_time = time.time()

        # Iterate over the batched results from the scanner
        for batch in scanner.scan_directory(target_path, progress_callback=_progress_cb):
            if batch:
                database.insert_file_batch(scan_id, batch)
                total_bytes += sum(row[1] for row in batch)  # row[1] is size_bytes
                files_seen += len(batch)

        duration_ms = int((time.time() - start_time) * 1000)

        # snapshot of volume capacity
        free_bytes, disk_total = disk.get_disk_usage(target_path)

        database.finish_scan(
            scan_id,
            int(time.time()),
            total_bytes,
            status="complete",
            disk_free_bytes=free_bytes,
            disk_total_bytes=disk_total
        )

        # On success, send one terminal result message
        send({
            "id": req_id,
            "type": "result",
            "data": {
                "scan_id": scan_id,
                "files_seen": files_seen,
                "duration_ms": duration_ms,
                "total_bytes": total_bytes,
                "disk_free_bytes": free_bytes,
                "disk_total_bytes": disk_total
            }
        })
        log(f"[scan] Complete. Took {duration_ms}ms")

    except Exception as e:
        log(f"[scan] Failed: {e}")
        database.finish_scan(scan_id, int(time.time()), total_bytes, status=f"failed: {str(e)}")

        # Map permission errors specifically, otherwise default to a generic error
        error_code = "PERMISSION_DENIED" if isinstance(e, PermissionError) else "SCAN_ERROR"
        send({
            "id": req_id,
            "type": "error",
            "error": {"code": error_code, "message": str(e)}
        })
    finally:
        database.prune_old_scans()


def handle_top_large_stale(req_id: str, args: dict) -> None:
    """Handle a `top_large_stale` request: query and return ranked file rows."""
    log("[top_large_stale] Fetching insights...")
    
    limit = args.get("limit", analyzer.DEFAULT_LIMIT)
    stale_months = args.get("stale_months", analyzer.DEFAULT_STALE_MONTHS)
    min_size_bytes = args.get("min_size_bytes", analyzer.DEFAULT_MIN_SIZE_BYTES)

    try:
        with database.get_db_connection() as conn:
            items = analyzer.top_large_stale(
                conn,
                limit=limit,
                stale_months=stale_months,
                min_size_bytes=min_size_bytes
            )

        send({
            "id": req_id,
            "type": "result",
            "data": {"items": items}
        })

    except Exception as e:
        log(f"[top_large_stale] Error: {e}")
        send({
            "id": req_id,
            "type": "error",
            "error": {"code": "QUERY_ERROR", "message": str(e)}
        })


def handle_trends(req_id: str, args: dict) -> None:
    """Handle a `trends` request: return total-size-per-scan over history."""
    log("[trends] Fetching historical scan trends...")

    # Pull optional limit, defaulting to None if not provided
    limit = args.get("limit")

    try:
        with database.get_db_connection() as conn:
            points = analyzer.scan_trends(
                conn,
                limit=limit
            )

        send({
            "id": req_id,
            "type": "result",
            "data": {"points": points}
        })
        log(f"[trends] Returned {len(points)} trend points")

    except Exception as e:
        log(f"[trends] Error: {e}")
        send({
            "id": req_id,
            "type": "error",
            "error": {"code": "QUERY_ERROR", "message": str(e)}
        })



def handle_large_files(req_id: str, args: dict) -> None:
    """Handle a `large_files` request: biggest files by size (offload candidates).

    Emits one {type:"result", data:{items:[file, ...]}}.

    """
    limit = args.get("limit", analyzer.DEFAULT_LIMIT)
    min_size_bytes = args.get("min_size_bytes", analyzer.DEFAULT_MIN_SIZE_BYTES)

    try:
        with database.get_db_connection() as conn:
            items = analyzer.large_files(
                conn,
                limit=limit,
                min_size_bytes=min_size_bytes
            )

        send({
            "id": req_id,
            "type": "result",
            "data": {"items": items}
        })

    except Exception as e:
        log(f"[large_files] Error: {e}")
        send({
            "id": req_id,
            "type": "error",
            "error": {"code": "QUERY_ERROR", "message": str(e)}
        })




def handle_folder_rollups(req_id: str, args: dict) -> None:
    """Handle a `folder_rollups` request: directories by recursive size (cohorts).

    Emits one {type:"result", data:{folders:[rollup, ...]}}.

    """
    limit = args.get("limit", analyzer.DEFAULT_LIMIT)
    min_size_bytes = args.get("min_size_bytes", analyzer.DEFAULT_MIN_SIZE_BYTES)

    try:
        with database.get_db_connection() as conn:
            items = analyzer.folder_rollups(
                conn,
                limit=limit,
                min_size_bytes=min_size_bytes
            )

        send({
            "id": req_id,
            "type": "result",
            "data": {"folders": items}
        })

    except Exception as e:
        log(f"[folder_rollups] Error: {e}")
        send({
            "id": req_id,
            "type": "error",
            "error": {"code": "QUERY_ERROR", "message": str(e)}
        })





def handle_disk_history(req_id: str, args: dict) -> None:
    """Handle a `disk_history` request: free-space-per-scan over history.

    Emits one {type:"result", data:{points:[disk history point, ...]}}. This is
    the free-space trend (how full the disk is over time) — distinct from the
    `trends` command, which tracks scanned-folder size.
    """
    log("[disk_history] Fetching free-space history...")

    limit = args.get("limit")

    try:
        with database.get_db_connection() as conn:
            points = analyzer.disk_history(conn, limit=limit)

        send({
            "id": req_id,
            "type": "result",
            "data": {"points": points}
        })
        log(f"[disk_history] Returned {len(points)} points")

    except Exception as e:
        log(f"[disk_history] Error: {e}")
        send({
            "id": req_id,
            "type": "error",
            "error": {"code": "QUERY_ERROR", "message": str(e)}
        })


def handle_disk_status(req_id: str, args: dict) -> None:
    """Handle a `disk_status` request: report current free/total space + low flag."""

    log("[disk_status] Fetching current volume status...")
    
    try:
        target_path = disk.resolve_scan_target(args.get("path"))
        free_bytes, total_bytes = disk.get_disk_usage(target_path)
        
        is_low = disk.is_low_space(free_bytes, total_bytes)
        used_bytes = total_bytes - free_bytes
        percent_free = (free_bytes / total_bytes * 100) if total_bytes > 0 else 0.0

        send({
            "id": req_id,
            "type": "result",
            "data": {
                "free_bytes": free_bytes,
                "total_bytes": total_bytes,
                "used_bytes": used_bytes,
                "percent_free": percent_free,
                "is_low": is_low
            }
        })
        
    except Exception as e:
        log(f"[disk_status] Error: {e}")
        send({
            "id": req_id,
            "type": "error",
            "error": {"code": "QUERY_ERROR", "message": str(e)}
        })


def handle_set_triage(req_id: str, args: dict) -> None:
    """Record a keep/delete/offload decision for a path (file or folder cohort).
    """
    path = args.get("path")
    is_dir = args.get("is_dir", False)
    decision = args.get("decision")

    if decision not in ("keep", "delete", "offload", "undecided"):
        send({"id": req_id, "type": "error", "error": {"code": "INVALID_ARGS", "message": f"Invalid decision: {decision}"}})
        return

    try:
        database.set_triage(path, is_dir, decision, decided_at=(int(time.time())))
        send({"id": req_id, "type": "result", "data": {"ok": True}})
    except Exception as e:
        log(f"[set_triage] Error: {e}")
        send({"id": req_id, "type": "error", "error": {"code": "QUERY_ERROR", "message": str(e)}})


def handle_list_triage(req_id: str, args: dict) -> None:
    """Return triage decisions, optionally filtered (e.g. decision='undecided').
    """
    decision = args.get("decision")
    
    try:
        items = database.list_triage(decision)
        send({"id": req_id, "type": "result", "data": {"items": items}})
    except Exception as e:
        log(f"[list_triage] Error: {e}")
        send({"id": req_id, "type": "error", "error": {"code": "QUERY_ERROR", "message": str(e)}})


def handle_create_goal(req_id: str, args: dict) -> None:
    """Create a goal (free_amount / stay_above / triage).
    """
    kind = args.get("kind")
    target_bytes = args.get("target_bytes")
    threshold_bytes = args.get("threshold_bytes")
    
    if kind not in ("free_amount", "stay_above", "triage"):
        send({"id": req_id, "type": "error", "error": {"code": "INVALID_ARGS", "message": f"Invalid goal kind: {kind}"}})
        return

    try:
        goal_id = database.create_goal(
            kind, 
            target_bytes=target_bytes, 
            threshold_bytes=threshold_bytes, 
            created_at=int(time.time())
        )
        send({"id": req_id, "type": "result", "data": {"goal_id": goal_id}})
    except Exception as e:
        log(f"[create_goal] Error: {e}")
        send({"id": req_id, "type": "error", "error": {"code": "QUERY_ERROR", "message": str(e)}})


def handle_list_goals(req_id: str, args: dict) -> None:
    """Return goals with computed progress.
    """
    status = args.get("status", "active")
    
    try:
        with database.get_db_connection() as conn:
            raw_goals = database.list_goals(status)
            enriched_goals = []
            
            for goal in raw_goals:
                progress = analyzer.goal_progress(conn, goal)
                goal["progress"] = progress
                enriched_goals.append(goal)
                
        send({"id": req_id, "type": "result", "data": {"goals": enriched_goals}})
    except Exception as e:
        log(f"[list_goals] Error: {e}")
        send({"id": req_id, "type": "error", "error": {"code": "QUERY_ERROR", "message": str(e)}})


def handle_move_to_trash(req_id: str, args: dict) -> None:
    """Handle a `move_to_trash` request: safely trash a file or folder cohort.
    """
    path = args.get("path")
    is_dir = args.get("is_dir", False)
    size_bytes = args.get("size_bytes")
    
    if path is None:
        send({"id": req_id, "type": "error", "error": {"code": "INVALID_ARGS", "message": "path is required"}})
        return

    try:
        result = actions.perform_action("trash", path, is_dir, size_bytes=size_bytes)
        send({"id": req_id, "type": "result", "data": result})
    except Exception as e:
        log(f"[move_to_trash] Error: {e}")
        send({"id": req_id, "type": "error", "error": {"code": "ACTION_ERROR", "message": str(e)}})


def handle_undo_action(req_id: str, args: dict) -> None:
    """Handle an `undo_action` request: reverse a completed action.
    """
    action_id = args.get("action_id")

    if action_id is None:
        send({"id": req_id, "type": "error", "error": {"code": "INVALID_ARGS", "message": "action_id is required"}})
        return

    try:
        actions.undo_action(action_id)
        send({"id": req_id, "type": "result", "data": {"ok": True}})
    except Exception as e:
        log(f"[undo_action] Error: {e}")
        send({"id": req_id, "type": "error", "error": {"code": "ACTION_ERROR", "message": str(e)}})


def handle_list_actions(req_id: str, args: dict) -> None:
    """Handle a `list_actions` request: the footprint log (what the app did).
    """
    status = args.get("status")

    try:
        results = database.list_actions(status)
        send({"id": req_id, "type": "result", "data": {"actions": results}})
    except Exception as e:
        log(f"[list_actions] Error: {e}")
        send({"id": req_id, "type": "error", "error": {"code": "QUERY_ERROR", "message": str(e)}})


def handle_list_volumes(req_id: str, args: dict) -> None:
    """Handle a `list_volumes` request: external volumes usable as offload targets.
    """
    log("[list_volumes] Fetching external volumes...")
    try:
        results = volumes.list_volumes()
        send({
            "id": req_id,
            "type": "result",
            "data": {"volumes": results}
        })
    except Exception as e:
        log(f"[list_volumes] Error: {e}")
        send({
            "id": req_id,
            "type": "error",
            "error": {"code": "QUERY_ERROR", "message": str(e)}
        })


def handle_offload(req_id: str, args: dict) -> None:
    """Handle an `offload` request: move a file/folder cohort to an external volume.
    """
    path = args.get("path")
    is_dir = args.get("is_dir", False)
    dest_path = args.get("dest_path")
    size_bytes = args.get("size_bytes")

    if path is None or dest_path is None:
        send({
            "id": req_id, 
            "type": "error", 
            "error": {"code": "INVALID_ARGS", "message": "path and dest_path are required"}
        })
        return

    try:
        result = actions.perform_action(
            "offload", 
            path, 
            is_dir, 
            dest_path=dest_path, 
            size_bytes=size_bytes
        )
        send({"id": req_id, "type": "result", "data": result})
    except Exception as e:
        log(f"[offload] Error: {e}")
        send({
            "id": req_id, 
            "type": "error", 
            "error": {"code": "ACTION_ERROR", "message": str(e)}
        })


# Maps a protocol `cmd` string to its handler.
COMMANDS = {
    "scan": handle_scan,
    "top_large_stale": handle_top_large_stale,
    "large_files": handle_large_files,
    "folder_rollups": handle_folder_rollups,
    "trends": handle_trends,
    "disk_history": handle_disk_history,
    "disk_status": handle_disk_status,
    "set_triage": handle_set_triage,
    "list_triage": handle_list_triage,
    "create_goal": handle_create_goal,
    "list_goals": handle_list_goals,
    "move_to_trash": handle_move_to_trash,
    "undo_action": handle_undo_action,
    "list_actions": handle_list_actions,
    "list_volumes": handle_list_volumes,
    "offload": handle_offload,
}


def dispatch(request: dict) -> None:
    """Route one parsed request dict to the right handler."""
    req_id = request.get("id")
    cmd = request.get("cmd")
    args = request.get("args", {})

    if not req_id or not cmd:
        send({
            "id": req_id or "unknown",
            "type": "error",
            "error": {"code": "BAD_REQUEST", "message": "Requests must contain 'id' and 'cmd'"}
        })
        return

    handler = COMMANDS.get(cmd)
    if not handler:
        send({
            "id": req_id,
            "type": "error",
            "error": {"code": "UNKNOWN_COMMAND", "message": f"Command '{cmd}' not found"}
        })
        return

    try:
        handler(req_id, args)
    except Exception as e:
        log(f"[dispatch] Unhandled exception in {cmd}: {e}")
        send({
            "id": req_id,
            "type": "error",
            "error": {"code": "INTERNAL_ERROR", "message": str(e)}
        })


def main() -> int:
    """Read stdin line by line, parse JSON, dispatch. Runs until stdin closes."""
    log("Storage Advisor Sidecar started. Waiting for requests...")

    database.init_db()

    # Loop over sys.stdin blockingly. Runs one request at a time.
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
            
        try:
            request = json.loads(line)
            dispatch(request)
        except json.JSONDecodeError:
            log("[main] Received malformed JSON string")
            send({
                "id": "unknown",
                "type": "error",
                "error": {"code": "PARSE_ERROR", "message": "Invalid JSON payload"}
            })
            
    log("Stdin pipe closed. Exiting.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
