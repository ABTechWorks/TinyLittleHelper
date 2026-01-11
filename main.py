from fastapi import FastAPI, Request, Form, Cookie, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
import hashlib
import uuid

app = FastAPI()

# Static + templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# In-memory storage
accounts = {}
sessions = {}

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ------------------------
# HELPERS
# ------------------------
def normalize_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

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
    if username in accounts or any(acc["email"] == email for acc in accounts.values()):
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Username or email already exists"}
        )

    normalized = normalize_password(password)
    hashed_password = pwd_context.hash(normalized)

    accounts[username] = {
        "email": email,
        "password": hashed_password,
        "devices": {
            "Laptop": "online",
            "Phone": "offline"
        }
    }

    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

# ------------------------
# LOGIN
# ------------------------
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    user = accounts.get(username)

    if not user or not pwd_context.verify(
        normalize_password(password),
        user["password"]
    ):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password"}
        )

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

    return templates.TemplateResponse("dashboard.html", {"request": request})

# ------------------------
# API: ACCOUNT DATA
# ------------------------
@app.get("/accounts")
async def get_account(session: str = Cookie(None)):
    if not session or session not in sessions:
        return JSONResponse(status_code=401, content={"error": "Not logged in"})

    username = sessions[session]
    account = accounts[username]

    return {
        "name": username,
        "devices": account["devices"]
    }
