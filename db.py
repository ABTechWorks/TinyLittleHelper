import sqlite3
import os
from pathlib import Path

# --------------------------------------------------
# DATABASE PATH (ABSOLUTE – FIXES SQLITE BUGS)
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "tinylittlehelper.db"

os.makedirs(DB_PATH.parent, exist_ok=True)

print("DB FILE LOCATION:", DB_PATH)

# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    print("RUNTIME DB USING:", DB_PATH)
    return conn


# --------------------------------------------------
# INITIALIZE DATABASE
# --------------------------------------------------
def init_db():
    conn = get_db()
    print("INIT DB USING:", DB_PATH)

    cur = conn.cursor()

    # USERS (web login)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # SESSIONS (browser login)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # DEVICES (helper exe + web)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            device_key TEXT NOT NULL,
            device_name TEXT NOT NULL,
            ip TEXT,
            mac TEXT,
            os TEXT,
            status TEXT DEFAULT 'offline',
            last_seen TEXT,
            recent_sites TEXT,
            UNIQUE(user_id, device_key)
        )
    """)

    # DEVICE HEARTBEATS (helper polling)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS device_heartbeats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_key TEXT NOT NULL,
            ip TEXT,
            last_seen TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
