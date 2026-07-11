"""
test_scanner.py — tests for the filesystem walk.

pytest's `tmp_path` fixture gives each test a fresh temp directory, so tests
never touch your real files. Build a little fake tree, scan it, assert on what
comes back.

Run:  pytest backend/test_scanner.py

MENTOR NOTE
-----------
Test the hostile cases, not just the happy path — that's where the real bugs
live and where a reviewer looks. Each stub below is a behavior worth pinning
down. Fill in the bodies as you implement scanner.py.
"""

from scanner import scan_directory


def _collect(target_path) -> list:
    """Helper: drain the batch generator into one flat list of rows.

    TODO: iterate scan_directory(target_path) and extend a list with each batch,
    so individual tests can just assert on the flat result.
    """
    # TODO: implement
    raise NotImplementedError


def test_finds_all_files(tmp_path):
    """A flat directory of N files yields N rows."""
    # TODO: create a couple files, scan, assert len == count
    raise NotImplementedError


def test_recurses_into_subdirectories(tmp_path):
    """Files in nested subfolders are found too (proves recursion)."""
    # TODO: make tmp_path/sub/deep.txt, scan tmp_path, assert it's included
    raise NotImplementedError


def test_captures_metadata(tmp_path):
    """Each row carries size and timestamps, not just the path."""
    # TODO: write known bytes to a file; assert the row's size_bytes matches
    raise NotImplementedError


def test_skips_unreadable_entries_without_crashing(tmp_path):
    """A permission error on one entry must not abort the whole scan."""
    # TODO: (harder / optional) chmod a file or dir to unreadable, scan, assert
    # the scan completes and returns the other files. Skippable while learning —
    # but this is THE robustness guarantee the product depends on.
    raise NotImplementedError


def test_invalid_path_is_handled(tmp_path):
    """Scanning a nonexistent path fails clearly (no traceback to the user)."""
    # TODO: scan tmp_path / "does_not_exist"; assert your chosen contract
    # (empty result, or a raised error you define — decide and test it)
    raise NotImplementedError
