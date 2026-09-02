"""
volumes.py — detect external volumes usable as offload destinations (Phase 7).

The user offloads cold files to an external disk (e.g. an SSD). This module
finds candidate destinations — mounted volumes that are NOT the startup disk —
so the UI can offer a place to move things to.
"""

import shutil

# macOS mounts non-boot volumes under /Volumes. The boot disk also appears here
# as a symlink/entry, so it must be excluded as a destination.
VOLUMES_ROOT = "/Volumes"


def list_volumes() -> list[dict]:
    """Return mounted external volumes available as offload destinations.

    Each dict: {name, path, free_bytes, total_bytes, free_human}.

    TODO:
      - Enumerate entries under /Volumes (os.scandir). For each, skip:
          * the startup/boot volume (resolve which /Volumes entry is `/` — e.g.
            compare os.stat(entry).st_dev to os.stat("/").st_dev and exclude the
            match) — never offer the boot disk as a destination.
          * anything not a real mount (broken symlinks, unreadable).
      - For each remaining volume, shutil.disk_usage(path) -> free/total; reuse
        analyzer._human_size (or a shared formatter) for free_human.
      - Return [] when nothing external is mounted (UI shows "connect a drive").
    Non-macOS: fine to return [] (offload is a macOS feature); don't raise here.
    Design note: only volumes with enough free space to hold a given cohort are
    valid targets — the *filtering* by required size happens at offload time,
    not here; this just lists what's connected.
    """
    # TODO: implement
    raise NotImplementedError
