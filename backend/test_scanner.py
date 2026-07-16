"""
test_scanner.py — tests for the filesystem walk.
"""

import pytest
from backend.scanner import scan_directory

def _collect(target_path) -> list:
    """Helper: drain the batch generator into one flat list of rows."""

    results = []
    for batch in scan_directory(target_path):
        results.extend(batch)

    return results


def test_finds_all_files(tmp_path):
    """A flat directory of N files yields N rows."""
    (tmp_path / "file1.txt").touch()
    (tmp_path / "file2.txt").touch()
    (tmp_path / "file3.txt").touch()

    rows = _collect(str(tmp_path))
    
    assert len(rows) == 3


def test_recurses_into_subdirectories(tmp_path):
    """Files in nested subfolders are found too (proves recursion)."""
    subfolder = tmp_path / "subfolder"
    subfolder.mkdir()
    deep_file = subfolder / "deep.txt"
    deep_file.touch()

    rows = _collect(str(tmp_path))

    assert len(rows) == 1
    assert rows[0][0] == str(deep_file)


def test_captures_metadata(tmp_path):
    """Each row carries size and timestamps, not just the path."""
    test_file = tmp_path / "data.txt"
    test_file.write_text("Hello World!")

    rows = _collect(str(tmp_path))
    assert len(rows) == 1

    filepath, size_bytes, mtime, atime, is_symlink, inode = rows[0]

    assert filepath == str(test_file)
    assert size_bytes == 12
    assert mtime > 0
    assert is_symlink == 0


def test_skips_unreadable_entries_without_crashing(tmp_path):
    """A permission error on one entry must not abort the whole scan."""
    good_file = tmp_path / "good.txt"
    good_file.touch()
    
    bad_dir = tmp_path / "bad_dir"
    bad_dir.mkdir()
    (bad_dir / "hidden.txt").touch()
    bad_dir.chmod(0o000) # removes all read/write/execute permissions

    try:
        rows = _collect(str(tmp_path))
        assert len(rows) == 1
        assert rows[0][0] == str(good_file)
    finally:
        bad_dir.chmod(0o777) # restore perms


def test_invalid_path_is_handled(tmp_path):
    """Scanning a nonexistent path fails clearly (no traceback to the user)."""
    bad_path = tmp_path / "does_not_exist"

    with pytest.raises(ValueError, match="not a valid directory"):
        list(scan_directory(str(bad_path)))

