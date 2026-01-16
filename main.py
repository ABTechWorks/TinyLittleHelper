from datetime import datetime
from fastapi import FastAPI, Request, Form, Cookie, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uuid
import subprocess
import re
import os
import sqlite3
from db import init_db, get_db

# --- Email ---
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()  # Load .env file

app = FastAPI()
init_db()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# -------------------------
# Utility: Resolve MAC from IP (Windows-safe)
# -------------------------
def get_mac_from_ip(ip_address: str):
    try:
        subprocess.run(
            ["ping", ip_address, "-n", "1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        arp_output = subprocess.check_output(["arp", "-a"], text=True)
        match = re.search(rf"{re.escape(ip_address)}\s+([a-fA-F0-9:-]+)", arp_output)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None

def mark_offline_devices(timeout_seconds=60):
    now = datetime.utcnow()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users")
    users = cur.fetchall()
    for user_id, in users:
        cur.execute("SELECT device_key, last_seen FROM devices WHERE user_id=?", (user_id,))
        for device_key, last_seen in cur.fetchall():
            if last_seen:
                delta = now - datetime.fromisoformat(last_seen)
                if delta.total_seconds() > timeout_seconds:
                    cur.execute(
                        "UPDATE devices SET status='offline' WHERE user_id=? AND device_key=?",
                        (user_id, device_key)
                    )
    conn.commit()
    conn.close()

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

    # --- Send Welcome Email ---
    try:
        SMTP_HOST = os.getenv("SMTP_HOST")
        SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
        SMTP_USER = os.getenv("SMTP_USER")
        SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
        FROM_EMAIL = os.getenv("FROM_EMAIL")
        DOMAIN = os.getenv("DOMAIN")
        APP_NAME = os.getenv("APP_NAME", "Tiny Little Helper")

        subject = f"Welcome to {APP_NAME}!"
        body = f"""
Hi {username},

Your {APP_NAME} account has been successfully created!

You can now log in at {DOMAIN}/login

Thanks for joining!
"""

        msg = MIMEMultipart()
        msg["From"] = FROM_EMAIL
        msg["To"] = email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print("Error sending email:", e)

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
        "SELECT id FROM users WHERE username=? AND password=?",
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
    user = cur.fetchone()
    if not user:
        conn.close()
        return RedirectResponse("/login", status_code=303)
    username = user[0]
    cur.execute(
        "SELECT device_name, status, ip, mac, last_seen FROM devices WHERE username=?",
        (username,)
    )
    devices = {
        device_name: {"status": status, "ip": ip, "mac": mac, "last_seen": last_seen}
        for device_name, status, ip, mac, last_seen in cur.fetchall()
    }
    conn.close()
    mark_offline_devices()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "username": username, "devices": devices}
    )

# -------------------------
# Add Device (advanced)
# -------------------------
@app.post("/add_device_advanced")
async def add_device_advanced(request: Request, session: str = Cookie(None)):
    if not session:
        return JSONResponse(status_code=401, content={"error": "Not logged in"})
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT username FROM sessions WHERE session_id=?", (session,))
    user = cur.fetchone()
    if not user:
        conn.close()
        return JSONResponse(status_code=401, content={"error": "Invalid session"})
    username = user[0]

    form = await request.form()
    device_ip = form.get("device_ip")
    device_mac = form.get("device_mac")
    device_name = form.get("device_name")

    if not device_name or (not device_ip and not device_mac):
        conn.close()
        return JSONResponse({"error": "Device name + IP or MAC required"}, status_code=400)

    if device_ip and not device_mac:
        resolved_mac = get_mac_from_ip(device_ip)
        device_mac = resolved_mac if resolved_mac else "pending"

    device_key = device_mac if device_mac != "pending" else device_name
    cur.execute("""
        INSERT OR REPLACE INTO devices (username, device_key, device_name, ip, mac, status, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (username, device_key, device_name, device_ip, device_mac,
          "online" if device_mac != "pending" else "offline",
          datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return RedirectResponse("/dashboard", status_code=303)

# -------------------------
# Helper Download
# -------------------------
@app.get("/download/helper")
async def download_helper(session: str = Cookie(None)):
    if not session:
        return RedirectResponse("/login")
    return RedirectResponse(
        "https://www.dropbox.com/scl/fi/qugsh2z1srk1u6fz9mbqq/tiny_helper.exe?rlkey=13977e0oe18p289mhwzy4029u&st=0hr2cpur&dl=1"
    )
