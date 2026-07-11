"""
scan_cli.py — command-line entry point for a scan.

The point of this file: exercise the whole ingestion pipeline (scanner + database)
from the terminal, WITHOUT any UI or sidecar wiring. This is what makes Phase 1 a
runnable milestone — you prove the backend works before Phase 2's harder
integration.

    python -m backend.scan_cli /Users/me/Downloads

It's deliberately thin. It orchestrates; the real work lives in scanner.py and
database.py.

MENTOR NOTE
-----------
Keep the "glue" logic (create scan -> stream batches -> finish -> prune) here and
in one function you can later reuse from the sidecar. Don't duplicate this
sequence in main.py in Phase 2 — call into it.
"""

import sys
import time

from database import init_db, create_scan, finish_scan, insert_file_batch, prune_old_scans
from scanner import scan_directory


def run_scan(target_path: str) -> int:
    """Run one full scan of `target_path` and return the new scan_id.

    Orchestration outline (implement the steps):

    TODO:
      1. init_db()                          # ensure schema exists
      2. started = int(time.time())
      3. scan_id = create_scan(target_path, started)
      4. total_bytes = 0
         for batch in scan_directory(target_path, progress_callback=...):
             insert_file_batch(scan_id, batch)
             total_bytes += sum(sizes in batch)
      5. finish_scan(scan_id, int(time.time()), total_bytes)
      6. prune_old_scans()
      7. return scan_id

    Wrap the loop so a failure marks the scan status appropriately rather than
    leaving it 'running' forever.
    """
    # TODO: implement
    raise NotImplementedError


def _print_progress(update: dict) -> None:
    """Simple progress printer for CLI use.

    In Phase 2 the sidecar will replace this with a protocol `progress` message
    (docs/protocol.md). For now, a human-readable line is fine.

    NOTE: CLI progress can go to stdout, but get in the habit now — logs to
    stderr, data to stdout — so Phase 2's stdio channel stays clean.

    TODO: print something like "  scanned 12,000 files..." to stderr
    """
    # TODO: implement
    raise NotImplementedError


def main(argv: list[str]) -> int:
    """Parse args, run the scan, print a summary. Returns a process exit code.

    TODO:
      - require exactly one arg (the path); print usage to stderr + return 2 if not
      - call run_scan(path)
      - print a short summary (scan_id, elapsed) to stderr
      - return 0 on success
    """
    # TODO: implement
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
