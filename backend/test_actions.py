"""
test_actions.py — the safe-action framework (Phase 6/7).

This is the code that moves and deletes real user files, so the tests focus on
the safety contract, not the happy path:
  - the original survives when verification fails or a copy is interrupted
  - deletion goes through the Trash (never rm), so it's reversible
  - offload is copy -> verify -> delete, in that order

`move_to_trash` needs macOS + PyObjC, so we monkeypatch it to move the item into
a fake "trash" dir — that keeps the tests hermetic and cross-platform while still
exercising the real perform_action / offload_to_volume / undo logic.
"""

import os

import pytest

from backend import database, actions


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated DB + a fake Trash so move_to_trash doesn't need macOS."""
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    database.init_db()

    trash = tmp_path / "Trash"
    trash.mkdir()

    def fake_trash(path):
        import shutil
        dest = str(trash / os.path.basename(path))
        shutil.move(path, dest)
        return dest  # undo_token — where it now lives

    monkeypatch.setattr(actions, "move_to_trash", fake_trash)
    # Offload's dataless check would hit the real FS; force it False.
    monkeypatch.setattr(actions.analyzer, "is_dataless", lambda p: False)
    return tmp_path


# --- move to trash -----------------------------------------------------------

def test_trash_records_done_and_moves_file(env):
    """A trash action moves the file and records a 'done' row with an undo token."""
    f = env / "junk.txt"
    f.write_text("bye")
    result = actions.perform_action("trash", str(f), False, size_bytes=3)
    assert result["status"] == "done"
    assert result["undo_token"] is not None
    assert not f.exists()  # moved to (fake) Trash
    row = database.get_action(result["action_id"])
    assert row["status"] == "done"


def test_trash_undo_restores_file(env):
    """Undo moves the trashed file back to its original path."""
    f = env / "junk.txt"
    f.write_text("bye")
    result = actions.perform_action("trash", str(f), False, size_bytes=3)
    actions.undo_action(result["action_id"])
    assert f.exists()
    assert f.read_text() == "bye"
    assert database.get_action(result["action_id"])["status"] == "undone"


# --- offload: copy -> verify -> delete ---------------------------------------

def test_offload_file_copies_then_trashes_original(env, monkeypatch):
    """A file offload copies to dest, verifies, and only then trashes the source."""
    monkeypatch.setattr(actions.analyzer, "reclaimable_bytes", lambda conn, paths: 0)
    src = env / "movie.bin"
    src.write_bytes(b"\0" * 1000)
    dest_dir = env / "ExternalSSD"
    dest_dir.mkdir()

    result = actions.perform_action("offload", str(src), False,
                                    dest_path=str(dest_dir), size_bytes=1000)
    assert result["status"] == "done"
    copied = dest_dir / "movie.bin"
    assert copied.exists() and copied.stat().st_size == 1000  # copy is intact
    assert not src.exists()  # original trashed only after verify


def test_offload_verification_failure_leaves_original(env, monkeypatch):
    """If the copy doesn't match, the original MUST survive and dest is cleaned up."""
    monkeypatch.setattr(actions.analyzer, "reclaimable_bytes", lambda conn, paths: 0)
    # Force verification to fail regardless of the actual copy.
    monkeypatch.setattr(actions, "_verify_copy", lambda src, dest, is_dir: False)
    src = env / "precious.bin"
    src.write_bytes(b"important")
    dest_dir = env / "ExternalSSD"
    dest_dir.mkdir()

    with pytest.raises(IOError):
        actions.perform_action("offload", str(src), False,
                               dest_path=str(dest_dir), size_bytes=9)

    assert src.exists()                       # original untouched
    assert not (dest_dir / "precious.bin").exists()  # partial dest removed


def test_offload_interrupted_copy_leaves_original(env, monkeypatch):
    """If the copy raises (e.g. volume disconnect), the original is never deleted."""
    monkeypatch.setattr(actions.analyzer, "reclaimable_bytes", lambda conn, paths: 0)
    import shutil
    def boom(*a, **k):
        raise OSError("volume disconnected")
    monkeypatch.setattr(shutil, "copy2", boom)
    src = env / "precious.bin"
    src.write_bytes(b"important")
    dest_dir = env / "ExternalSSD"
    dest_dir.mkdir()

    with pytest.raises(OSError):
        actions.perform_action("offload", str(src), False,
                               dest_path=str(dest_dir), size_bytes=9)

    assert src.exists()  # original safe

    # And the action row is recorded 'failed', not 'done'.
    with database.get_db_connection() as conn:
        rows = conn.execute("SELECT status FROM actions ORDER BY id DESC LIMIT 1").fetchall()
    assert rows[0]["status"] == "failed"


def test_offload_refuses_existing_destination(env, monkeypatch):
    """Never clobber an existing file at the destination."""
    monkeypatch.setattr(actions.analyzer, "reclaimable_bytes", lambda conn, paths: 0)
    src = env / "movie.bin"
    src.write_bytes(b"\0" * 100)
    dest_dir = env / "ExternalSSD"
    dest_dir.mkdir()
    (dest_dir / "movie.bin").write_text("already here")

    with pytest.raises(Exception):
        actions.perform_action("offload", str(src), False,
                               dest_path=str(dest_dir), size_bytes=100)
    assert src.exists()  # original untouched


# --- verify helper -----------------------------------------------------------

def test_verify_copy_detects_folder_mismatch(env):
    """Folder verify catches a same-total-size-but-different-contents copy."""
    a = env / "a"
    (a / "sub").mkdir(parents=True)
    (a / "sub" / "x.txt").write_bytes(b"1234")
    b = env / "b"
    (b / "sub").mkdir(parents=True)
    # same total size (4 bytes) but a different file name -> must NOT verify
    (b / "sub" / "y.txt").write_bytes(b"1234")
    assert actions._verify_copy(str(a), str(b), True) is False
