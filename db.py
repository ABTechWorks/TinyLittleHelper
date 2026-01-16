import sqlite3
import os

DB_PATH = "data/tinylittlehelper.db"

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # USERS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # SESSIONS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # DEVICES  <-- THIS WAS MISSING
    cur.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            device_key TEXT NOT NULL,
            device_name TEXT NOT NULL,
            ip TEXT,
            mac TEXT,
            status TEXT,
            last_seen TEXT,
            UNIQUE(user_id, device_key)
        )
    """)

    conn.commit()
    conn.close()
