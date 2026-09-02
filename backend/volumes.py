"""
volumes.py — detect external volumes usable as offload destinations (Phase 7).

The user offloads cold files to an external disk (e.g. an SSD). This module
finds candidate destinations — mounted volumes that are NOT the startup disk —
so the UI can offer a place to move things to.
"""

import os
import sys
import shutil
import analyzer

# macOS mounts non-boot volumes under /Volumes. The boot disk also appears here
# as a symlink/entry, so it must be excluded as a destination.
VOLUMES_ROOT = "/Volumes"


def list_volumes() -> list[dict]:
    """Return mounted external volumes available as offload destinations.
    """

    if sys.platform != "darwin":
      return []

    if not os.path.exists(VOLUMES_ROOT):
        return []

    try:
        boot_dev = os.stat("/").st_dev
    except OSError:
        boot_dev = None

    results = []

    try:
        for entry in os.scandir(VOLUMES_ROOT):
          #skip hidden files
          if entry.name.startswith("."):
            continue

          try:
              stat_info = os.stat(entry.path)

              if boot_dev is not None and stat_info.st_dev == boot_dev:
                  continue

              usage = shutil.disk_usage(entry.path)

              results.append({
                  "name": entry.name,
                  "path": entry.path,
                  "free_bytes": usage.free,
                  "total_bytes": usage.total,
                  "free_human": analyzer._human_size(usage.free)
              })
          except OSError:
            continue

    except OSError:
      pass

    return results



