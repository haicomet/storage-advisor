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
          if not dest_path:
            raise ValueError("offload requires a dest_path")
          undo_token = offload_to_volume(path, dest_path)
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


def offload_to_volume(src: str, dest_dir: str) -> str:
    """Move `src` (file OR folder cohort) to an external volume. Return an undo token.

    A cross-volume move is NOT atomic, so this is copy → verify → delete-original,
    NEVER a blind move (DESIGN.md §6). The original is removed only after the
    destination copy is proven good — so an interrupted offload leaves the
    original intact.

    Returns the destination path (the undo_token: where it now lives, so
    undo_action can move it back).

    TODO:
      1. Compute dest = os.path.join(dest_dir, os.path.basename(src)). Refuse if
         dest already exists (don't clobber).
      2. PRE-CHECK (safety prerequisites — see reconciliation helpers):
           - skip/refuse iCloud dataless placeholders (copying triggers a download).
           - if src shares an inode with another kept file (clone/hardlink),
             offloading frees nothing — surface that rather than proceed silently.
           - confirm the volume has enough free space for the cohort.
      3. COPY: shutil.copytree(src, dest) for a dir, shutil.copy2 for a file
         (copy2 preserves mtime — keeps staleness signals meaningful).
      4. VERIFY before deleting: compare total size, and checksum
         (hash the bytes) — the copy must match the source. If verification
         FAILS, delete the partial dest and raise; the original is untouched.
      5. DELETE ORIGINAL only now — via move_to_trash(src), NOT rm, so even the
         "original" removal is reversible. (Trash the source; the offloaded copy
         is the primary now.)
      6. Return dest as the undo_token.
    Disconnect handling: if the volume vanishes mid-copy, the copy raises; the
    original was never touched, so perform_action marks the row 'failed' and the
    file is safe. Never delete the original outside the verified path.
    """
    # TODO: implement
    raise NotImplementedError


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
        # Move the offloaded copy back from the external volume to the original
        # path. undo_token is the destination path where it now lives.
        # TODO:
        #   - copy dest (undo_token) back to action["path"], verify, then remove
        #     the copy from the external volume. Mirror the copy→verify→delete
        #     discipline in reverse so an interrupted undo never loses the file.
        #   - refuse if action["path"] already exists (something recreated it).
        raise NotImplementedError("Offload undo — implement in Phase 7")
    else:
        raise ValueError(f"Unknown action kind for undo: {action['kind']}")

    database.complete_action(action_id, status="undone", completed_at=int(time.time()))

