import sqlite3
from pathlib import Path

DB_PATH = "storage_advisor.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():

    table_creation_query = """
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filepath TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        last_modified INTEGER NOT NULL,
        last_accessed INTEGER NOT NULL
    );
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(table_creation_query)

    conn.commit()
    conn.close()

def save_file_metadata(files_list):
    # Save file metadata to the database
    insert_query = """
    INSERT INTO files (filepath, size_bytes, last_modified, last_accessed)
    VALUES (?, ?, ?, ?);
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executemany(insert_query,files_list)

    conn.commit()
    conn.close()

   