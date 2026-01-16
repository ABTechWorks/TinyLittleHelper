import sqlite3
import os

DB_FILE = "tinyhelper.db"

def init_db():
    """Initialize the SQLite database and tables."""
    db_exists = os.path.exists(DB_FILE)
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Sessions table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Devices table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            device_name TEXT NOT NULL,
            ip TEXT,
            mac TEXT,
            status TEXT,
            last_seen TEXT,
            UNIQUE(username, device_name)
        )
    """)

    conn.commit()
    conn.close()


def get_db():
    """Return a new connection to the database."""
    conn = sqlite3.connect(DB_FILE)
    return conn
