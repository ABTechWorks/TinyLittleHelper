from datetime import datetime
from fastapi import FastAPI, Request, Form, Cookie, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uuid
import subprocess
import re
import sqlite3
from db import init_db, get_db  # db.py contains init_db() and get_db()

# -------------------------
# Initialize
# -------------------------
app = FastAPI()
init_db()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


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


# -------------------------
# Root route
# -------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# -------------------------
# Signup
# -------------------------
@app.post("/signup", response_class=HTMLResponse)
async def signup(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO users (username, email, password, created_at) VALUES (?, ?, ?, ?)",
            (username, email, password, datetime.utcnow().isoformat())
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Username already exists"}
        )
    finally:
        conn.close()

    return RedirectResponse("/login", status_code=302)


# -------------------------
# Login
# -------------------------
@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, password)
    )
    user = cur.fetchone()

    if not user:
        conn.close()
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid credentials"}
        )

    session_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO sessions (session_id, username, created_at) VALUES (?, ?, ?)",
        (session_id, username, datetime.utcnow().isoformat())
    )

    conn.commit()
    conn.close()

    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie("session", session_id, httponly=True)
    return response


# -------------------------
# Dashboard
# -------------------------
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, session: str = Cookie(None)):
    if not session:
        return RedirectResponse("/login", status_code=303)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT username FROM sessions WHERE session_id=?", (session,))
    result = cur.fetchone()
    if not result:
        conn.close()
        return RedirectResponse("/login", status_code=303)

    username = result[0]

    cur.execute("SELECT device_name, ip, mac, status, last_seen FROM devices WHERE username=?", (username,))
    rows = cur.fetchall()
    conn.close()

    devices = {}
    now = datetime.utcnow()
    for row in rows:
        device_name, ip, mac, status, last_seen = row
        # mark offline if last_seen > 60 sec
        if last_seen:
            delta = now - datetime.fromisoformat(last_seen)
            if delta.total_seconds() > 60:
                status = "offline"
        devices[device_name] = {
            "ip": ip,
            "mac": mac,
            "status": status,
            "last_seen": last_seen
        }

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "username": username, "devices": devices}
    )


# -------------------------
# Add device (basic)
# -------------------------
@app.post("/add_device")
async def add_device(
    request: Request,
    device_name: str = Form(...),
    ip: str = Form(None),
    mac: str = Form(None),
    session: str = Cookie(None)
):
    if not session:
        return RedirectResponse("/login", status_code=303)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT username FROM sessions WHERE session_id=?", (session,))
    result = cur.fetchone()
    if not result:
        conn.close()
        return RedirectResponse("/login", status_code=303)
    username = result[0]

    cur.execute("""
        INSERT INTO devices (username, device_name, ip, mac, status, last_seen)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(username, device_name) DO UPDATE SET
            ip=excluded.ip,
            mac=excluded.mac,
            status=excluded.status,
            last_seen=excluded.last_seen
    """, (
        username,
        device_name,
        ip,
        mac,
        "online",
        datetime.utcnow().isoformat()
    ))

    conn.commit()
    conn.close()
    return RedirectResponse("/dashboard", status_code=303)


# -------------------------
# Device heartbeat
# -------------------------
@app.post("/device_heartbeat")
async def device_heartbeat(request: Request):
    data = await request.json()
    token = data.get("token")

    conn = get_db()
    cur = conn.cursor()

    # Find username based on device token
    cur.execute("SELECT username, device_name FROM devices WHERE device_name=?", (token,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return JSONResponse(status_code=401, content={"error": "Invalid token"})

    username, device_name = row

    ip = data.get("ip")
    mac = data.get("mac")

    # Resolve MAC if missing
    if ip and (not mac or mac == "pending"):
        mac = get_mac_from_ip(ip)
        if not mac:
            mac = "pending"

    cur.execute("""
        UPDATE devices SET ip=?, mac=?, status=?, last_seen=? 
        WHERE username=? AND device_name=?
    """, (ip, mac, "online", datetime.utcnow().isoformat(), username, device_name))

    conn.commit()
    conn.close()
    return JSONResponse({"status": "heartbeat received"})


# -------------------------
# Download helper
# -------------------------
@app.get("/download/helper")
async def download_helper(session: str = Cookie(None)):
    if not session:
        return RedirectResponse("/login")

    # Dropbox direct download link
    return RedirectResponse(
        "https://www.dropbox.com/scl/fi/qugsh2z1srk1u6fz9mbqq/tiny_helper.exe?rlkey=13977e0oe18p289mhwzy4029u&dl=1"
    )
