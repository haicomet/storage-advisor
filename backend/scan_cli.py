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
    # Run one full scan of `target_path` and return the new scan_id.

    init_db()
    started = int(time.time())
    scan_id = create_scan(target_path, started)
    total_bytes = 0

    try:
        for batch in scan_directory(target_path, progress_callback=_print_progress):
            if batch:
                insert_file_batch(scan_id, batch)
                total_bytes += sum(row[1] for row in batch) # batch is a list of tuples with size_bytes at idx 1

            finish_scan(scan_id, int(time.time()), total_bytes, status="complete")
            print("", file=sys.stderr)

    except Exception as e:
        finish_scan(scan_id, int(time.time()), total_bytes, status=f"failed: {str(e)}")
        print(f"\nScan failed: {e}", file=sys.stderr)
        raise
    finally:
        prune_old_scans()

    return scan_id



def _print_progress(update: dict) -> None:
    # Simple progress printer for CLI use.

    files_seen = update.get("files_seen", 0)
    curr_dir = update.get("curr_dir", "")

    sys.stderr.write(f"\r Scanned {files_seen:,} files...(Current: {curr_dir[-40:]}) ")
    sys.stderr.flush()


def main(argv: list[str]) -> int:
    # Parse args, run the scan, print a summary. Returns a process exit code.

    if len(argv) != 1:
        print("Usage: python -m backend.scan_cli <target_path>", file=sys.stderr)
        return 2

    target_path = argv[0]

    print(f"Starting scan of '{target_path}'...", file=sys.stderr)

    try:
        start_time = time.time()
        scan_id = run_scan(target_path)
        elapsed = time.time() - start_time

        print(f"Scan complete! ID: {scan_id} (Took {elapsed:.2f}s)", file=sys.stderr)
        return 0
    except KeyboardInterrupt:
        print("\nScan canceled by user.", file=sys.stderr)
        return 130
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
