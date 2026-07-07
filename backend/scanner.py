from pathlib import Path
from datetime import datetime
from database import save_file_metadata

def scan_directory(target_path: str):
    # scans target dir and returns a list containing file metadata
    path = Path(target_path)
    scanned_files = []

    if not path.exists() or not path.is_dir():
        print(f"Error: {target_path} is not a valid directory.")
        return []

    files = path.rglob("*")

    for file in files:
        if file.is_file():
            size_bytes = file.stat().st_size
            last_modified = int(file.stat().st_mtime)
            last_accessed = int(file.stat().st_atime)

            scanned_files.append((str(file), size_bytes, last_modified, last_accessed))
    
    return scanned_files

