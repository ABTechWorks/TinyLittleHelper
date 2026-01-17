import requests
import socket
import uuid
import platform
import time
import sys
import os
from pathlib import Path

# =====================================================
# CONFIG
# =====================================================

BACKEND_BASE = "https://mytinylittlehelper.com"
REGISTER_ENDPOINT = f"{BACKEND_BASE}/add_device_advanced_token"
HEARTBEAT_ENDPOINT = f"{BACKEND_BASE}/device_heartbeat"
HEARTBEAT_INTERVAL = 30  # seconds

APP_NAME = "TinyLittleHelper"

# =====================================================
# PATHS (macOS-safe, PyInstaller-safe)
# =====================================================

def get_app_support_dir():
    base = Path.home() / "Library" / "Application Support" / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base

APP_DIR = get_app_support_dir()
TOKEN_FILE = APP_DIR / "device_token.txt"
LOG_FILE = APP_DIR / "helper_debug.log"

# =====================================================
# LOGGING
# =====================================================

def log(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")
    except Exception:
        pass

# =====================================================
# DEVICE TOKEN
# =====================================================

def get_device_token():
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
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
# BACKEND COMMUNICATION
# =====================================================

def register_device():
    payload = {
        "token": DEVICE_TOKEN,
        "device_name": get_device_name(),
        "ip": get_ip(),
        "mac": get_mac(),
        "os": get_os(),
        "recent_sites": []  # intentionally empty on macOS
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
        "recent_sites": []
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
    log("=== TinyLittleHelper macOS started ===")

    if not register_device():
        log("Initial registration failed. Exiting.")
        sys.exit(1)

    while True:
        send_heartbeat()
        time.sleep(HEARTBEAT_INTERVAL)

if __name__ == "__main__":
    main()
