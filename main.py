from fastapi import FastAPI, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from pathlib import Path
from datetime import datetime
import json, smtplib
from email.message import EmailMessage
import secrets

# -----------------------------
# Config
# -----------------------------
DATA_FILE = Path("accounts.json")
GMAIL_ADDRESS = "your_email@gmail.com"
GMAIL_APP_PASSWORD = "your_16_char_app_password"

if not DATA_FILE.exists():
    DATA_FILE.write_text(json.dumps({"accounts": {}}))

# -----------------------------
# Helper Functions
# -----------------------------
def generate_token():
    return secrets.token_hex(16)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def send_email(to_email: str, subject: str, body: str):
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
        print(f"Email failed: {e}")

# -----------------------------
# FastAPI App
# -----------------------------
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# -----------------------------
# Models
# -----------------------------
class Account(BaseModel):
    name: str
    email: EmailStr
    token: str

class Heartbeat(BaseModel):
    account_token: str
    device_name: str
    status: str

# -----------------------------
# Routes
# -----------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request, "error": ""})

@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request, "error": ""})

@app.post("/signup")
def signup(name: str = Form(...), email: str = Form(...)):
    data = load_data()

    # Prevent duplicate email
    for acc in data["accounts"].values():
        if acc["email"] == email:
            raise HTTPException(status_code=400, detail="Email already registered")

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
        "Your Monitoring Token",
        f"""
Hi {name},

Your monitoring account has been created.

Your login token:
{token}

Keep this safe.
"""
    )

    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(key="account_token", value=token)
    return response

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})

@app.post("/login")
def login(request: Request, email: str = Form(...), token: str = Form(...)):
    data = load_data()
    for acc in data["accounts"].values():
        if acc["email"] == email and acc["token"] == token:
            response = RedirectResponse("/dashboard", status_code=302)
            response.set_cookie(key="account_token", value=token)
            return response
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid email or token"})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    token = request.cookies.get("account_token")
    if not token:
        return RedirectResponse("/")
    return templates.TemplateResponse("dashboard.html", {"request": request, "token": token})

@app.get("/accounts")
def get_accounts():
    return load_data()

@app.post("/accounts")
def create_account(account: Account):
    data = load_data()
    if account.token in data["accounts"]:
        raise HTTPException(status_code=400, detail="Token already exists")
    data["accounts"][account.token] = {
        "name": account.name,
        "email": account.email,
        "token": account.token,
        "devices": {}
    }
    save_data(data)
    send_email(account.email, "Welcome!", f"Hi {account.name}, your account has been created!")
    return {"message": "Account created successfully"}

@app.post("/heartbeat")
def heartbeat(hb: Heartbeat):
    data = load_data()
    account = data["accounts"].get(hb.account_token)
    if not account:
        raise HTTPException(status_code=404, detail="Invalid token")
    
    devices = account.setdefault("devices", {})
    last_status = devices.get(hb.device_name)
    notify = False
    if hb.status.lower() == "online" and last_status != "online":
        notify = True
    
    devices[hb.device_name] = hb.status.lower()
    save_data(data)
    
    if notify:
        send_email(account["email"],
                   f"Device Online: {hb.device_name}",
                   f"{hb.device_name} checked in at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return {"status": "ok", "notify_sent": notify}
