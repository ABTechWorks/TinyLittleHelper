from datetime import datetime
from fastapi import FastAPI, Request, Form, Cookie, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uuid
import subprocess
import re
import os

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# -------------------------
# In-memory storage (replace later with DB)
# -------------------------
accounts = {}
sessions = {}

# -------------------------
# Utility: Resolve MAC from IP (Windows-safe)
# -------------------------
def get_mac_from_ip(ip_address: str):
    try:
        # Ping once (Windows)
        subprocess.run(
            ["ping", ip_address, "-n", "1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Read ARP table
        arp_output = subprocess.check_output(["arp", "-a"], text=True)

        match = re.search(rf"{re.escape(ip_address)}\s+([a-fA-F0-9:-]+)", arp_output)
        if match:
            return match.group(1)

    except Exception:
        pass

    return None

# Offline Utility Function
def mark_offline_devices(timeout_seconds=60):
    now = datetime.utcnow()

    for user in accounts.values():
        for device in user["devices"].values():
            last_seen = device.get("last_seen")
            if last_seen:
                delta = now - datetime.fromisoformat(last_seen)
                if delta.total_seconds() > timeout_seconds:
                    device["status"] = "offline"


# -------------------------
# Routes
# -------------------------

# Root route → landing page with signup/login options
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# -------------------------
# Signup
# -------------------------

# GET route to show signup form
@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

# POST route to handle signup form submission
@app.post("/signup")
async def signup(username: str = Form(...), password: str = Form(...)):
    if username in accounts:
        return JSONResponse(status_code=400, content={"error": "User already exists"})

    accounts[username] = {
        "password": password,
        "devices": {}  # unified device schema
    }

    # unique account token
    accounts[username]["token"] = str(uuid.uuid4())

    return RedirectResponse("/login", status_code=303)  # send user to login after signup

# -------------------------
# Login
# -------------------------

# GET route to show login form
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# POST route to handle login form submission
@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    if username not in accounts or accounts[username]["password"] != password:
        return JSONResponse(status_code=401, content={"error": "Invalid credentials"})

    # create session
    session_id = str(uuid.uuid4())
    sessions[session_id] = username

    # redirect to dashboard and set cookie
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie("session", session_id, httponly=True)
    return response


# -------------------------
# Dashboard
# -------------------------

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, session: str = Cookie(None)):
    # check if session is valid
    if not session or session not in sessions:
        return RedirectResponse("/login", status_code=303)

    username = sessions[session]
    devices = accounts[username].get("devices", {})

    # mark offline devices
    mark_offline_devices()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "username": username,
            "devices": devices
        }
    )
@app.post("/add_device")
async def add_device(
    request: Request,
    device_name: str = Form(...),
    ip: str = Form(None),
    mac: str = Form(None),
    session: str = Cookie(None)
):
    if not session or session not in sessions:
        return RedirectResponse("/login", status_code=303)

    username = sessions[session]

    if not device_name or (not ip and not mac):
        return JSONResponse({"error": "Device name + IP or MAC required"}, status_code=400)

    device_key = mac if mac else device_name
    accounts[username].setdefault("devices", {})[device_key] = {
        "status": "online",
        "ip": ip,
        "mac": mac,
        "last_seen": datetime.utcnow().isoformat()
    }

    return RedirectResponse("/dashboard", status_code=303)


# -------------------------
# Device Heartbeat
# -------------------------

@app.post("/device_heartbeat")
async def device_heartbeat(request: Request):
    data = await request.json()

    token = data.get("token")
    # Find username based on token
    username = next((u for u, a in accounts.items() if a.get("token") == token), None)

    if not username:
        return JSONResponse(status_code=401, content={"error": "Invalid token"})

    device_name = data.get("device_name")
    ip = data.get("ip")
    mac = data.get("mac")

    if not username or username not in accounts:
        return JSONResponse(status_code=401, content={"error": "Invalid user"})

    accounts[username].setdefault("devices", {})

    # Try to resolve pending MAC
    if ip and (not mac or mac == "pending"):
        resolved_mac = get_mac_from_ip(ip)
        if resolved_mac:
            mac = resolved_mac

    device_key = mac if mac else device_name

    accounts[username]["devices"][device_key] = {
        "status": "online",
        "ip": ip,
        "mac": mac,
        "last_seen": datetime.utcnow().isoformat()
    }

    return JSONResponse({"status": "heartbeat received"})


# -------------------------
# OLD MANUAL DEVICE ADD
# -------------------------
@app.post("/add_device")
async def add_device(
    device_name: str = Form(...),
    session: str = Cookie(None)
):
    if not session or session not in sessions:
        return JSONResponse(status_code=401, content={"error": "Not logged in"})

    username = sessions[session]
    accounts[username].setdefault("devices", {})

    accounts[username]["devices"][device_name] = {
        "status": "online",
        "ip": None,
        "mac": None
    }

    return RedirectResponse("/dashboard", status_code=303)

# -------------------------
# ADVANCED DEVICE ADD (IP / MAC)
# -------------------------
@app.post("/add_device_advanced")
async def add_device_advanced(request: Request, session: str = Cookie(None)):
    if not session or session not in sessions:
        return JSONResponse(status_code=401, content={"error": "Not logged in"})

    form = await request.form()
    device_ip = form.get("device_ip")
    device_mac = form.get("device_mac")
    username = sessions[session]

    accounts[username].setdefault("devices", {})

    # If only IP provided → attempt MAC resolution
    if device_ip and not device_mac:
        device_mac = get_mac_from_ip(device_ip)
        if not device_mac:
            device_mac = "pending"

    if not device_ip and not device_mac:
        return JSONResponse(status_code=400, content={"error": "IP or MAC required"})

    device_key = device_mac if device_mac != "pending" else device_ip

    accounts[username]["devices"][device_key] = {
        "status": "online" if device_mac != "pending" else "offline",
        "ip": device_ip,
        "mac": device_mac,
	"last_seen": datetime.utcnow().isoformat()
    }

    return RedirectResponse("/dashboard", status_code=303)

# -------------------------
# HELPER DOWNLOAD (EXE FILE)
# -------------------------
@app.get("/download/helper")
async def download_helper(session: str = Cookie(None)):
    # Check login session
    if not session or session not in sessions:
        return RedirectResponse("/login")

    # Build the correct path relative to main.py
    # file_path = os.path.join(os.path.dirname(__file__), "dist", "tiny_helper.exe")

    # Serve the file for download
    return FileResponse(
	path="static/dist/tiny_helper.exe",  # relative path inside repo
        filename="tiny_helper.exe",  # name browser sees
        media_type="application/octet-stream"
    )
