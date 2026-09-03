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

import os
import time
import sys
import shutil
import filecmp
from . import database
from . import analyzer

def _get_size(path: str) -> int:
    """helper: recursively calculate the total size of a file or folder in bytes"""
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total += os.path.getsize(fp)
    return total

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
    """
    dest = os.path.join(dest_dir, os.path.basename(src))
    is_dir = os.path.isdir(src)

    if os.path.exists(dest):
      raise FileExistsError(f"Cannot offload: destination already exists at {dest}")

    if analyzer.is_dataless(src):
      raise ValueError(f"Cannot offload dataless iCloud file: {src}")

    with database.get_db_connection() as conn:
        reclaimable = analyzer.reclaimable_bytes(conn, [src])

    if shutil.disk_usage(dest_dir).free < reclaimable:
      raise OSError(f"Not enough free space on {dest_dir} for offload.")

    # copy
    if is_dir:
      shutil.copytree(src, dest)
    else:
      shutil.copy2(src, dest)

    verified = False
    #verify
    if is_dir:
       verified = (_get_size(src) == _get_size(dest))
    else:
       verified = filecmp.cmp(src, dest, shallow=False)

    #commit or rollback
    if verified:
      move_to_trash(src)
      return dest
    else:
      if is_dir:
         shutil.rmtree(dest)
      else:
         os.remove(dest)
      raise IOError("Offload verification failed. Original file is untouched.")



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
        src = action["undo_token"]  # the external drive copy
        dest = action["path"]       # the original location
        is_dir = action["is_dir"]

        if os.path.exists(dest):
            raise FileExistsError(f"Cannot undo: a file already exists at {dest}")

        if is_dir:
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)

        verified = False
        if is_dir:
            verified = (_get_size(src) == _get_size(dest))
        else:
            verified = filecmp.cmp(src, dest, shallow=False)

        if verified:
            move_to_trash(src)
        else:
            if is_dir:
                shutil.rmtree(dest)
            else:
                os.remove(dest)
            raise IOError("Undo verification failed. External copy is untouched.")
    else:
        raise ValueError(f"Unknown action kind for undo: {action['kind']}")

    database.complete_action(action_id, status="undone", completed_at=int(time.time()))

