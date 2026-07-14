"""
scanner.py — recursive filesystem walk that produces file metadata.

Walks a directory tree and, for each file, records (path, size, mtime, atime,
is_symlink, inode). Streams results to the database in batches instead of
returning one giant list, so a big home directory doesn't blow up memory.

"""

import os

# Batch size for streaming rows to the DB.
BATCH_SIZE = 2000

# Directory names to skip entirely
SKIP_DIRS: set[str] = {
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
                                st.st_size,
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
