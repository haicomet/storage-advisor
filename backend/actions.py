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

from . import database


def perform_action(kind: str, path: str, is_dir: bool, *,
                   dest_path: str | None = None, size_bytes: int | None = None,
                   inode: int | None = None) -> dict:
    """Run one action through the record → execute → verify → commit contract.

    Returns a summary dict the handler can send back, e.g.
    {action_id, status, undo_token}.

    TODO:
      - action_id = database.record_action(kind, path, is_dir, dest_path=...,
          size_bytes=..., inode=..., created_at=int(time.time()))   # status='pending'
      - try:
            if kind == "trash":  undo_token = move_to_trash(path)
            elif kind == "offload":  raise NotImplementedError  # Phase 7
            else: raise ValueError(kind)
            # verify step goes here (for offload; trash is atomic via the OS API)
            database.complete_action(action_id, status="done",
                completed_at=int(time.time()), undo_token=undo_token)
            return {"action_id": action_id, "status": "done", "undo_token": undo_token}
        except Exception:
            database.complete_action(action_id, status="failed",
                completed_at=int(time.time()))
            raise
    Design note: record BEFORE executing so a crash mid-op leaves a 'pending' row
    (recoverable), never a silent loss.
    """
    # TODO: implement
    raise NotImplementedError


def move_to_trash(path: str) -> str:
    """Move `path` (file OR folder) to the macOS Trash. Return an undo token.

    NEVER uses `rm`/os.remove/shutil.rmtree — that would be irreversible and
    violate the product's core safety principle. Use the system Trash API so the
    move is reversible from Finder and by undo_action().

    TODO:
      - Preferred: PyObjC — NSFileManager.defaultManager()
        .trashItemAtURL_resultingItemURL_error_(NSURL.fileURLWithPath_(path), ...).
        The "resulting item URL" it returns is the file's new location in the
        Trash — capture it as the undo_token so undo_action can move it back.
      - Fallback (no PyObjC): osascript telling Finder to `delete POSIX file`.
        Note Finder returns the trashed item's path too.
      - Works for a folder cohort as a single call (the whole subtree goes to
        Trash atomically — do NOT walk and delete file-by-file).
      - Raise on failure (perform_action marks the action failed).
    Non-macOS: raise a clear "unsupported platform" error rather than falling
    back to a destructive delete.
    """
    # TODO: implement
    raise NotImplementedError


def undo_action(action_id: int) -> None:
    """Reverse a completed action using its recorded undo_token.

    TODO:
      - Look up the action row (need a database.get_action(id) or reuse
        list_actions and filter). Read its kind + undo_token.
      - trash: move the item back from its Trash location (undo_token) to the
        original `path`. offload (Phase 7): move it back from the external volume.
      - On success: database.complete_action(action_id, status="undone",
        completed_at=int(time.time())).
      - Guard: only 'done' actions can be undone; a 'pending'/'failed' row has no
        reliable undo_token.
    """
    # TODO: implement
    raise NotImplementedError
