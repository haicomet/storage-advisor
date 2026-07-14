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
    ".Trash",
    "node_modules",
    ".git",
    "Caches",
    "System Volume Information"
}


def scan_directory(target_path: str, progress_callback=None):
    """Recursively walk `target_path`, yielding batches of file-metadata tuples.

    Yields lists of tuples shaped for `database.insert_file_batch`:
        (filepath, size_bytes, last_modified, last_accessed, is_symlink, inode)
"""
    if not os.path.exists(target_path) or not os.path.isdir(target_path):
        raise ValueError(f"Target path '{target_path}' is not a valid directory.")

    batch = []
    files_seen = 0

    dirs_to_visit = [target_path]

    while dirs_to_visit:
        curr_dir = dirs_to_visit.pop()

        try:
            with os.scandir(curr_dir) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name not in SKIP_DIRS:
                                dirs_to_visit.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            st = entry.stat(follow_symlinks=False)

                            file_row = (
                                entry.path,
                                int(st.st_mtime),
                                int(st.st_atime),
                                1 if entry.is_symlink() else 0,
                                st.st_ino
                            )

                            batch.append(file_row)
                            files_seen += 1

                            if len(batch) >= BATCH_SIZE:
                                yield batch
                                batch = []

                            if progress_callback and files_seen % 500 == 0:
                                progress_callback({
                                    "files_seen": files_seen,
                                    "curr_dir": curr_dir
                                })
                    except OSError:
                        continue
        except OSError:
            continue

    if batch:
        yield batch

    if progress_callback:
      progress_callback({
          "files_seen": files_seen,
          "curr_dir": "Finished"
        })
