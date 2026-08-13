"""
disk.py — scan-target resolution and disk-space measurement.

Phase 4 removes the typed path: the app decides *what* to scan (the home
directory by default) and measures *how full* the disk is so it can flag low
space. This module owns both concerns so main.py stays a thin dispatcher.
"""

import os
import shutil

# Below this fraction of free space, the disk is considered "low" and the UI
# should flag it. Tunable later (Phase 5 goals may make it user-configurable).
LOW_SPACE_FRACTION = 0.10  # 10% free


def resolve_scan_target(requested: str | None = None) -> str:
    """Return the directory to scan — the caller's request, or the home dir.

    TODO:
      - If `requested` is a non-empty path, expanduser() it and return it (keeps
        the door open for user-added roots later, e.g. an external SSD).
      - Otherwise default to the user's home directory
        (os.path.expanduser("~")).
      - Do NOT validate existence here — scanner.scan_directory already raises on
        a bad path; keep this function's job to "decide the target," not to stat.
    Design note (DESIGN.md §5): home is the default, not "/". Whole-disk scans
    drag in system files the app must never touch.
    """
    if requested:
        return os.path.expanduser(requested)
    return os.path.expanduser("~")


def get_disk_usage(path: str) -> tuple[int, int]:
    """Return (free_bytes, total_bytes) for the volume containing `path`.

    TODO:
      - Use shutil.disk_usage(path) -> (total, used, free); return (free, total).
      - This measures the whole VOLUME the path lives on, which is what "how full
        is my disk" means — distinct from the scanned bytes total_bytes, which is
        only the sum of files under the scan root.
    """
    # TODO: implement
    raise NotImplementedError


def is_low_space(free_bytes: int, total_bytes: int,
                 fraction: float = LOW_SPACE_FRACTION) -> bool:
    """True when free space is at or below `fraction` of the volume.

    TODO:
      - Guard total_bytes == 0 (avoid divide-by-zero) -> return False.
      - Return free_bytes <= total_bytes * fraction.
    """
    # TODO: implement
    raise NotImplementedError
