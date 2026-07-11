"""
scanner.py — recursive filesystem walk that produces file metadata.

Walks a directory tree and, for each file, records (path, size, mtime, atime,
is_symlink, inode). Streams results to the database in batches instead of
returning one giant list, so a big home directory doesn't blow up memory.

MENTOR NOTES
------------
- Use `os.scandir`, not `pathlib.rglob`. `os.scandir` yields DirEntry objects
  that carry stat info from the original syscall, so `entry.stat()` usually costs
  nothing extra. The old scanner called `.stat()` THREE times per file — that's
  the bug this rewrite fixes.
- The filesystem is hostile: permission errors, broken symlinks, files deleted
  mid-walk, and (on macOS) iCloud placeholders. A single unguarded `.stat()` can
  kill the whole scan. Guard per-entry and keep going.
- `os.scandir` does not recurse. You recurse yourself (a stack/queue or a
  recursive generator). This is deliberate — it lets you skip directories you
  don't want to descend into (e.g. .Trash, caches) BEFORE walking them.
- Yield batches, don't accumulate. The `progress_callback` lets the caller report
  "files_seen" to the UI without the scanner knowing anything about the UI.
"""

import os

# Batch size for streaming rows to the DB. Tune later; a few thousand is a fine
# starting point (small enough for flat memory, large enough that inserts aren't
# chatty).
BATCH_SIZE = 2000

# Directory names to skip entirely (never descend). Start small; grow as you see
# what pollutes results on a real machine.
SKIP_DIRS: set[str] = {
    # TODO: decide what belongs here, e.g. ".Trash", "node_modules", caches.
}


def scan_directory(target_path: str, progress_callback=None):
    """Recursively walk `target_path`, yielding batches of file-metadata tuples.

    Yields lists of tuples shaped for `database.insert_file_batch`:
        (filepath, size_bytes, last_modified, last_accessed, is_symlink, inode)

    `progress_callback`, if given, is called periodically with a dict like
    {"files_seen": int, "current_dir": str} — the caller decides what to do with
    it (print, or later forward as a protocol `progress` message).

    A generator (yield) is suggested so the caller can insert each batch as it
    arrives — but returning a list is acceptable while you're learning; just note
    the memory tradeoff.

    TODO — the core algorithm:
      1. validate target_path exists and is a directory (return/raise clearly if not)
      2. walk recursively using os.scandir:
           - for each entry, guard with try/except (PermissionError,
             FileNotFoundError, OSError) and `continue` on failure
           - if entry.is_dir(follow_symlinks=False):
               skip if name in SKIP_DIRS, else recurse
           - if entry.is_file(follow_symlinks=False):
               st = entry.stat()               # ONE stat call
               build the tuple from st.st_size, st.st_mtime, st.st_atime,
               st.st_ino, and whether it's a symlink
               append to the current batch
      3. when the batch reaches BATCH_SIZE, yield it and start a fresh one
      4. call progress_callback occasionally (not every file — too chatty)
      5. yield any final partial batch

    Think about (don't necessarily solve yet):
      - symlink loops (follow_symlinks=False avoids the worst of it)
      - do you count directory sizes, or only files? (files only, per DESIGN.md)
    """
    # TODO: implement
    raise NotImplementedError
