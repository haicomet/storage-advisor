"""
actions.py — the safe-action framework (Phase 6).

Every destructive operation the app performs goes through ONE contract
(DESIGN.md §6), so safety is built once and reused by Move to Trash (here) and
later by offload (Phase 7):

    1. record intent   — write an actions row status='pending' BEFORE touching
                          the filesystem (so an interrupted op is recoverable)
    2. execute         — perform the operation in the sidecar
    3. verify          — confirm it happened (offload also checksums the copy
                          before deleting the original — Phase 7)
    4. commit / undo   — mark 'done' with an undo_token; expose a reversal path

Hard rule (DESIGN.md §2): NEVER `rm`. Deletion means the macOS Trash (reversible
by construction). This module must not contain an unlink/rmtree of user data.
"""

import time
import sys
import shutil
from . import database


def perform_action(kind: str, path: str, is_dir: bool, *,
                   dest_path: str | None = None, size_bytes: int | None = None,
                   inode: int | None = None) -> dict:
    """Run one action through the record → execute → verify → commit contract.
    """
    action_id = database.record_action(kind, path, is_dir,
                                        dest_path=dest_path,
                                        size_bytes=size_bytes,
                                        inode=inode,
                                        created_at=int(time.time()))

    try:
        if kind == "trash":
          undo_token = move_to_trash(path)
        elif kind == "offload":
          raise NotImplementedError("Offload coming in Phase 7")
        else:
          raise ValueError(f"Unknown action kind: {kind}")

        database.complete_action(action_id, status="done",
                completed_at=int(time.time()), undo_token=undo_token)
        return {"action_id": action_id, "status": "done", "undo_token": undo_token}

    except Exception:
        # if move_to_trash blew up, mark it failed and re-raise the error
        database.complete_action(action_id, status="failed",
                completed_at=int(time.time()))
        raise


def move_to_trash(path: str) -> str:
    """Move `path` (file OR folder) to the macOS Trash. Return an undo token.
    """
    if sys.platform != "darwin":
      raise RuntimeError("Safe delete is only supported on macOS.")

    from Foundation import NSFileManager, NSURL

    file_url = NSURL.fileURLWithPath_(path)
    manager = NSFileManager.defaultManager()

    success, new_url, error = manager.trashItemAtURL_resultingItemURL_error_(
        file_url, None, None
    )

    if not success:
        raise Exception(f"Failed to move to Trash: {error}")

    return new_url.path()


def undo_action(action_id: int) -> None:
    """Reverse a completed action using its recorded undo_token.
    """

    action = database.get_action(action_id)

    if action is None:
        raise ValueError(f"No action found with id {action_id}")

    if action["status"] != "done":
      raise ValueError("Only 'done' actions can be undone.")

    if action["kind"] == "trash":
        shutil.move(action["undo_token"], action["path"])
    elif action["kind"] == "offload":
        raise NotImplementedError("Offload undo coming in Phase 7")
    else:
        raise ValueError(f"Unknown action kind for undo: {action['kind']}")

    database.complete_action(action_id, status="undone", completed_at=int(time.time()))

