import requests
import socket
import uuid
import platform
import subprocess
import re
import time
import sys

# =====================================================
# CONFIG (TOKEN IS EMBEDDED BY BACKEND BEFORE DOWNLOAD)
# =====================================================

BACKEND_BASE = "http://127.0.0.1:8000"

REGISTER_ENDPOINT = f"{BACKEND_BASE}/add_device_advanced"
HEARTBEAT_ENDPOINT = f"{BACKEND_BASE}/device_heartbeat"

# 🔐 This token should be injected by your backend
# Example replacement before download:
# DEVICE_TOKEN = "abc123"
DEVICE_TOKEN = "REPLACE_ME"

HEARTBEAT_INTERVAL = 30  # seconds


# =====================================================
# DEVICE INFO FUNCTIONS
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
        "ip": get_local_ip(),
        "mac": get_mac(),
        "os": get_os(),
    }

    try:
        r = requests.post(REGISTER_ENDPOINT, json=payload, timeout=10)
        if r.status_code == 200:
            print("✅ Device registered successfully")
            return True
        else:
            print("❌ Registration failed:", r.text)
            return False
    except Exception as e:
        print("❌ Backend unreachable:", e)
        return False


def send_heartbeat():
    payload = {
        "token": DEVICE_TOKEN,
        "device_name": get_device_name(),
        "ip": get_local_ip(),
        "mac": get_mac(),
    }

    try:
        requests.post(HEARTBEAT_ENDPOINT, json=payload, timeout=5)
    except Exception:
        pass


# =====================================================
# MAIN LOOP
# =====================================================

def main():
    if DEVICE_TOKEN == "REPLACE_ME":
        print("❌ Invalid helper build: token not injected")
        sys.exit(1)

    if not register_device():
        sys.exit(1)

    while True:
        send_heartbeat()
        time.sleep(HEARTBEAT_INTERVAL)


# =====================================================
# ENTRY POINT (REQUIRED FOR ONEFILE)
# =====================================================

if __name__ == "__main__":
    main()
