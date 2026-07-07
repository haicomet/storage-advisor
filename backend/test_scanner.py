import pytest
from scanner import scan_directory

def test_scan_directory_finds_files(tmp_path):
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.txt"
    
    file1.touch()
    file2.touch()

    results = scan_directory(str(tmp_path))

    assert len(results) == 2, f"Expected 2 files, but found {len(results)}"
    assert isinstance(results, list), f"Expected results to be a list, but got {type(results)}"