from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json
import smtplib
from email.message import EmailMessage
from pathlib import Path
from datetime import datetime

app = FastAPI()
DATA_FILE = Path("accounts.json")
GMAIL_ADDRESS = "your_email@gmail.com"
GMAIL_APP_PASSWORD = "your_16_char_app_password"

# Load or create data storage
if not DATA_FILE.exists():
    DATA_FILE.write_text(json.dumps({"accounts": {}}))

def save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2))

def send_email(to_email, subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_email
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)

class Heartbeat(BaseModel):
    account_token: str
    device_name: str
    status: str

@app.post("/heartbeat")
def heartbeat(data: Heartbeat):
    storage = json.loads(DATA_FILE.read_text())
    accounts = storage["accounts"]

    # Find account by token
    account = None
    for acc_id, acc in accounts.items():
        if acc["token"] == data.account_token:
            account = acc
            break
    if not account:
        raise HTTPException(status_code=404, detail="Invalid token")

    devices = account.setdefault("devices", {})
    last_status = devices.get(data.device_name)

    # Only notify if status changed to online
    notify = False
    if data.status.lower() == "online" and last_status != "online":
        notify = True

    devices[data.device_name] = data.status
    save_data(storage)

    if notify:
        send_email(
            account["email"],
            f"Device Online: {data.device_name}",
            f"{data.device_name} checked in at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    return {"status": "ok", "notify_sent": notify}
