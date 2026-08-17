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
    """Return the directory to scan — the caller's request, or the home dir."""

    if requested:
        return os.path.expanduser(requested)
    return os.path.expanduser("~")


def get_disk_usage(path: str) -> tuple[int, int]:
    """Return (free_bytes, total_bytes) for the volume containing `path`."""

    usage = shutil.disk_usage(path)
    return (usage.free, usage.total)


def is_low_space(free_bytes: int, total_bytes: int,
                 fraction: float = LOW_SPACE_FRACTION) -> bool:
    """True when free space is at or below `fraction` of the volume."""

    if total_bytes == 0:
        return False

    return free_bytes <= (total_bytes * fraction)
