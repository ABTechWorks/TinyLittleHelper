import sqlite3
import os
from pathlib import Path

# --------------------------------------------------
# DATABASE PATH
# --------------------------------------------------
DB_PATH = Path("data/tinylittlehelper.db")
os.makedirs(DB_PATH.parent, exist_ok=True)

# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------
def get_db():
    """
    Returns a SQLite connection with Row factory for dict-like access.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# --------------------------------------------------
# INITIALIZE DATABASE
# --------------------------------------------------
def init_db():
    """
    Creates all necessary tables for the backend:
    - users
    - sessions
    - devices
    """
    conn = get_db()
    cur = conn.cursor()

    # USERS table (for web login)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # SESSIONS table (for web login)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # DEVICES table (works for web + helper exe)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,                 -- nullable for token-based devices
            device_key TEXT NOT NULL,        -- token or MAC/user key
            device_name TEXT NOT NULL,
            ip TEXT,
            mac TEXT,
            os TEXT,
            status TEXT,
            last_seen TEXT,
            recent_sites TEXT,
            UNIQUE(user_id, device_key)      -- prevents duplicates per user/device
        )
    """)

    conn.commit()
    conn.close()

# --------------------------------------------------
# OPTIONAL: UTILITY FUNCTION TO CLEAR DB (FOR DEV)
# --------------------------------------------------
def reset_db():
    """
    Deletes the database file (dev only)
    """
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Deleted {DB_PATH}")
    else:
        print(f"No database found at {DB_PATH}")
