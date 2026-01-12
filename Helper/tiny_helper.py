import requests
import socket
import uuid
import platform
import subprocess
import re

# === CONFIG ===
BACKEND_URL = "http://localhost:8000/add_device_advanced"  # Change to your server URL
SESSION_ID = input("Enter your dashboard session cookie: ")  # For now user inputs session cookie

# === Helper functions ===

def get_device_name():
    """Get the hostname of the device."""
    return socket.gethostname()

def get_local_ip():
    """Get the local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return None

def get_mac_from_ip(ip_address=None):
    """
    Get MAC address of the device.
    If ip_address is provided, try to get MAC from ARP table.
    If not, get local MAC.
    """
    # Local MAC
    if not ip_address:
        mac_num = hex(uuid.getnode()).replace("0x", "").upper()
        mac = ":".join(mac_num[i:i+2] for i in range(0, 12, 2))
        return mac
    # MAC from IP
    try:
        # Ping the device first
        subprocess.run(["ping", "-c", "1", ip_address], check=True, stdout=subprocess.DEVNULL)
        arp_output = subprocess.check_output(["arp", "-n", ip_address]).decode()
        match = re.search(r"(([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2}))", arp_output)
        if match:
            return match.group(0)
    except:
        return "pending"
    return "pending"

# === Main ===

device_name = get_device_name()
device_ip = get_local_ip()
device_mac = get_mac_from_ip(device_ip)

payload = {
    "device_ip": device_ip,
    "device_mac": device_mac
}

cookies = {"session": SESSION_ID}

try:
    response = requests.post(BACKEND_URL, data=payload, cookies=cookies)
    if response.status_code == 200:
        print(f"✅ Device '{device_name}' registered successfully!")
    else:
        print(f"❌ Failed to register device: {response.json()}")
except Exception as e:
    print(f"❌ Error connecting to backend: {e}")

import socket
import uuid
import requests
import time
import os

BACKEND_URL = "http://127.0.0.1:8000/device_heartbeat"
USERNAME = "YOUR_USERNAME"  # <-- replace or inject later

def get_device_name():
    return socket.gethostname()

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

def get_mac():
    mac = uuid.getnode()
    return ":".join(f"{(mac >> ele) & 0xff:02x}" for ele in range(40, -1, -8))

while True:
    payload = {
        "username": USERNAME,
        "device_name": get_device_name(),
        "ip": get_ip(),
        "mac": get_mac()
    }

    try:
        requests.post(BACKEND_URL, json=payload, timeout=5)
    except Exception:
        pass

    time.sleep(30)  # heartbeat every 30 seconds
