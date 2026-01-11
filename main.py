# main.py
from fastapi import FastAPI, Request, Form, Cookie, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
import os
import uuid
import hashlib
import aiosmtplib
from email.message import EmailMessage

app = FastAPI()

# Static + templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# In-memory storage (MVP)
accounts = {}
sessions = {}

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Email env vars
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")


# ------------------------
# UTILS
# ------------------------
def normalize_password(password: str) -> str:
    """Normalize password using SHA256 before hashing with bcrypt"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


async def send_verification_email(to_email: str, token: str):
    """Send verification email asynchronously using Gmail SMTP"""
    msg = EmailMessage()
    msg["Subject"] = "Verify Your Account"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_email
    msg.set_content(
        f"Hello!\n\nClick the link below to verify your account:\n\n"
        f"http://127.0.0.1:8000/verify?token={token}\n\n"
        "If you didn't sign up, ignore this email."
    )

    await aiosmtplib.send(
        msg,
        hostname="smtp.gmail.com",
        port=465,
        username=GMAIL_ADDRESS,
        password=GMAIL_APP_PASSWORD,
        use_tls=True
    )


# ------------------------
# LANDING PAGE
# ------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ------------------------
# SIGNUP
# ------------------------
@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})


@app.post("/signup")
async def signup(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    # Check if username or email exists
    if username in accounts or any(acc['email'] == email for acc in accounts.values()):
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Username or email already exists"}
        )

    # Hash password
    normalized = normalize_password(password)
    hashed_password = pwd_context.hash(normalized)

    # Generate email verification token
    token = str(uuid.uuid4())

    # Store account with 'verified' flag
    accounts[username] = {
        "email": email,
        "password": hashed_password,
        "verified": False,
        "token": token,
        "devices": {"Laptop": "online", "Phone": "offline"}
    }

    # Send verification email
    await send_verification_email(email, token)

    return templates.TemplateResponse(
        "signup.html",
        {"request": request, "message": "Check your email to verify your account!"}
    )


# ------------------------
# EMAIL VERIFICATION
# ------------------------
@app.get("/verify", response_class=HTMLResponse)
async def verify_account(request: Request, token: str):
    for username, account in accounts.items():
        if account.get("token") == token:
            account["verified"] = True
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "message": "Your account is verified! You can log in now."}
            )

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid verification token"}
    )


# ------------------------
# LOGIN
# ------------------------
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    user = accounts.get(username)

    if not user or not user.get("verified"):
        return templates.TemplateResponse(
            "login.html",
            {"request": {}, "error": "Invalid username or account not verified"}
        )

    if not pwd_context.verify(normalize_password(password), user["password"]):
        return templates.TemplateResponse(
            "login.html",
            {"request": {}, "error": "Invalid password"}
        )

    # Create session
    session_token = str(uuid.uuid4())
    sessions[session_token] = username

    response = RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie("session", session_token, httponly=True)
    return response


# ------------------------
# DASHBOARD (PROTECTED)
# ------------------------
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, session: str = Cookie(None)):
    if not session or session not in sessions:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    username = sessions[session]
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "username": username}
    )


# ------------------------
# API: ACCOUNT DATA (for dashboard JS)
# ------------------------
@app.get("/accounts")
async def get_account(session: str = Cookie(None)):
    if not session or session not in sessions:
        return JSONResponse(status_code=401, content={"error": "Not logged in"})

    username = sessions[session]
    account = accounts.get(username)

    return {
        "name": username,
        "devices": account["devices"]
    }
