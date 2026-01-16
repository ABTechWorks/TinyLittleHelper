from datetime import datetime
from fastapi import FastAPI, Request, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uuid
import subprocess
import re
import os
import sqlite3
from db import init_db, get_db

# Email
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
init_db()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --------------------------------------------------
# Utilities
# --------------------------------------------------
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

    for (user_id,) in users:
        cur.execute(
            "SELECT device_key, last_seen FROM devices WHERE user_id=?",
            (user_id,)
        )
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

# --------------------------------------------------
# INDEX
# --------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# --------------------------------------------------
# SIGNUP (GET)
# --------------------------------------------------
@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

# --------------------------------------------------
# SIGNUP (POST)
# --------------------------------------------------
@app.post("/signup")
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
        conn.close()
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Username already exists"}
        )

    # Send welcome email
    try:
        msg = MIMEMultipart()
        msg["From"] = os.getenv("FROM_EMAIL")
        msg["To"] = email
        msg["Subject"] = f"Welcome to {os.getenv('APP_NAME','Tiny Little Helper')}"

        body = f"""
Hi {username},

Your account has been created successfully.

Log in here:
{os.getenv('DOMAIN')}/login
"""
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", 587))) as server:
            server.starttls()
            server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
            server.send_message(msg)
    except Exception as e:
        print("Email error:", e)

    conn.close()
    return RedirectResponse("/login", status_code=302)

# --------------------------------------------------
# LOGIN (GET)  <-- FIXES METHOD NOT ALLOWED
# --------------------------------------------------
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# --------------------------------------------------
# LOGIN (POST)
# --------------------------------------------------
@app.post("/login")
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

# --------------------------------------------------
# DASHBOARD (FIXED)
# --------------------------------------------------
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, session: str = Cookie(None)):
    if not session:
        return RedirectResponse("/login", status_code=303)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT username FROM sessions WHERE session_id=?", (session,))
    session_row = cur.fetchone()
    if not session_row:
        conn.close()
        return RedirectResponse("/login", status_code=303)

    username = session_row[0]

    cur.execute("SELECT id FROM users WHERE username=?", (username,))
    user_row = cur.fetchone()
    if not user_row:
        conn.close()
        return RedirectResponse("/login", status_code=303)

    user_id = user_row[0]

    cur.execute(
        "SELECT device_name, status, ip, mac, last_seen FROM devices WHERE user_id=?",
        (user_id,)
    )

    devices = {
        name: {
            "status": status,
            "ip": ip,
            "mac": mac,
            "last_seen": last_seen
        }
        for name, status, ip, mac, last_seen in cur.fetchall()
    }

    conn.close()
    mark_offline_devices()

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "username": username, "devices": devices}
    )

# --------------------------------------------------
# ADD DEVICE
# --------------------------------------------------
@app.post("/add_device_advanced")
async def add_device_advanced(request: Request, session: str = Cookie(None)):
    if not session:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT username FROM sessions WHERE session_id=?", (session,))
    session_row = cur.fetchone()
    if not session_row:
        conn.close()
        return JSONResponse({"error": "Invalid session"}, status_code=401)

    username = session_row[0]

    cur.execute("SELECT id FROM users WHERE username=?", (username,))
    user_id = cur.fetchone()[0]

    form = await request.form()
    device_name = form.get("device_name")
    device_ip = form.get("device_ip")
    device_mac = form.get("device_mac")

    if device_ip and not device_mac:
        device_mac = get_mac_from_ip(device_ip) or "pending"

    device_key = device_mac if device_mac != "pending" else device_name

    cur.execute("""
        INSERT OR REPLACE INTO devices
        (user_id, device_key, device_name, ip, mac, status, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        device_key,
        device_name,
        device_ip,
        device_mac,
        "online" if device_mac != "pending" else "offline",
        datetime.utcnow().isoformat()
    ))

    conn.commit()
    conn.close()

    return RedirectResponse("/dashboard", status_code=303)

# --------------------------------------------------
# DOWNLOAD HELPER
# --------------------------------------------------
@app.get("/download/helper")
async def download_helper(session: str = Cookie(None)):
    if not session:
        return RedirectResponse("/login")

    return RedirectResponse(
        "https://www.dropbox.com/scl/fi/6fa3e9w3vt9dc3d335jmj/tiny_helper.exe?rlkey=b5kc7stp53fksr2ffo9eavkwx&st=shkur0jo&dl=1"
    )

# --------------------------------------------------
# LOGOUT
# --------------------------------------------------
@app.get("/logout")
async def logout(session: str = Cookie(None)):
    if session:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE session_id=?", (session,))
        conn.commit()
        conn.close()

    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("session")
    return response

# --------------------------------------------------
# CHANGE PASSWORD (GET)
# --------------------------------------------------
@app.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request, session: str = Cookie(None)):
    if not session:
        return RedirectResponse("/login", status_code=303)

    return templates.TemplateResponse(
        "change_password.html",
        {"request": request}
    )

# --------------------------------------------------
# CHANGE PASSWORD (POST)
# --------------------------------------------------
@app.post("/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    session: str = Cookie(None)
):
    if not session:
        return RedirectResponse("/login", status_code=303)

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT username FROM sessions WHERE session_id=?",
        (session,)
    )
    session_row = cur.fetchone()
    if not session_row:
        conn.close()
        return RedirectResponse("/login", status_code=303)

    username = session_row[0]

    cur.execute(
        "SELECT password FROM users WHERE username=?",
        (username,)
    )
    row = cur.fetchone()

    if not row or row[0] != current_password:
        conn.close()
        return templates.TemplateResponse(
            "change_password.html",
            {
                "request": request,
                "error": "Current password is incorrect"
            }
        )

    cur.execute(
        "UPDATE users SET password=? WHERE username=?",
        (new_password, username)
    )

    conn.commit()
    conn.close()

    return RedirectResponse("/dashboard", status_code=302)
