from fastapi import FastAPI, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from pathlib import Path
from datetime import datetime
import json
import smtplib
import secrets
from email.message import EmailMessage

# -----------------------------
# Config
# -----------------------------
DATA_FILE = Path("accounts.json")
GMAIL_ADDRESS = "your_email@gmail.com"
GMAIL_APP_PASSWORD = "your_16_char_app_password"

if not DATA_FILE.exists():
    DATA_FILE.write_text(json.dumps({"accounts": {}}))

# -----------------------------
# Helpers
# -----------------------------
def load_data():
    return json.loads(DATA_FILE.read_text())

def save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2))

def generate_token():
    return secrets.token_hex(16)

def send_email(to_email, subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_email

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        print("Email error:", e)

# -----------------------------
# App setup
# -----------------------------
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# -----------------------------
# Models
# -----------------------------
class Heartbeat(BaseModel):
    account_token: str
    device_name: str
    status: str

# -----------------------------
# Routes
# -----------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request, "error": ""})

@app.post("/signup")
def signup(name: str = Form(...), email: EmailStr = Form(...)):
    data = load_data()

    for acc in data["accounts"].values():
        if acc["email"] == email:
            return templates.TemplateResponse(
                "signup.html",
                {"request": {}, "error": "Email already registered"}
            )

    token = generate_token()

    data["accounts"][token] = {
        "name": name,
        "email": email,
        "token": token,
        "devices": {}
    }

    save_data(data)

    send_email(
        email,
        "Your Device Monitor Token",
        f"Welcome {name}\n\nYour login token:\n{token}"
    )

    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie("account_token", token, httponly=True)
    return response

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})

@app.post("/login")
def login(request: Request, email: EmailStr = Form(...), token: str = Form(...)):
    data = load_data()

    for acc in data["accounts"].values():
        if acc["email"] == email and acc["token"] == token:
            response = RedirectResponse("/dashboard", status_code=302)
            response.set_cookie("account_token", token, httponly=True)
            return response

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid email or token"}
    )

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    token = request.cookies.get("account_token")
    if not token:
        return RedirectResponse("/login")
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/accounts")
def get_account(request: Request):
    token = request.cookies.get("account_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not logged in")

    data = load_data()
    account = data["accounts"].get(token)

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return account

@app.post("/heartbeat")
def heartbeat(hb: Heartbeat):
    data = load_data()
    account = data["accounts"].get(hb.account_token)

    if not account:
        raise HTTPException(status_code=404, detail="Invalid token")

    devices = account["devices"]
    devices[hb.device_name] = hb.status.lower()
    save_data(data)

    return {"status": "ok"}
