from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
import json
from pathlib import Path
from datetime import datetime
import smtplib
from email.message import EmailMessage

# -----------------------------
# Config
# -----------------------------
DATA_FILE = Path("accounts.json")
GMAIL_ADDRESS = "your_email@gmail.com"
GMAIL_APP_PASSWORD = "your_16_char_app_password"

# Create data file if it doesn't exist
if not DATA_FILE.exists():
    DATA_FILE.write_text(json.dumps({"accounts": {}}))

# -----------------------------
# Helper functions
# -----------------------------
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
        print(f"Failed to send email: {e}")

# -----------------------------
# FastAPI instance
# -----------------------------
app = FastAPI(title="TinyLittleHelper API")

# -----------------------------
# Pydantic models
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
@app.get("/")
def read_root():
    return {"message": "TinyLittleHelper API is running"}

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
    
    send_email(
        account.email,
        "Welcome to TinyLittleHelper!",
        f"Hi {account.name}, your account has been created with token {account.token}"
    )
    
    return {"message": "Account created successfully"}

@app.post("/heartbeat")
def heartbeat(hb: Heartbeat):
    data = load_data()
    account = data["accounts"].get(hb.account_token)
    
    if not account:
        raise HTTPException(status_code=404, detail="Invalid token")
    
    devices = account.setdefault("devices", {})
    last_status = devices.get(hb.device_name)
    
    # Only notify if status changed to online
    notify = False
    if hb.status.lower() == "online" and last_status != "online":
        notify = True
    
    devices[hb.device_name] = hb.status.lower()
    save_data(data)
    
    if notify:
        send_email(
            account["email"],
            f"Device Online: {hb.device_name}",
            f"{hb.device_name} checked in at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    
    return {"status": "ok", "notify_sent": notify}

@app.get("/accounts")
def get_accounts():
    data = load_data()
    return data
