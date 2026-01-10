from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uuid

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Fake in-memory DB (replace later)
accounts = {}
sessions = {}

# ------------------------
# LANDING PAGE
# ------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request
    })

# ------------------------
# SIGNUP
# ------------------------
@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {
        "request": request
    })

@app.post("/signup")
async def signup(
    username: str = Form(...),
    password: str = Form(...)
):
    if username in accounts:
        raise HTTPException(status_code=400, detail="User already exists")

    accounts[username] = {
        "password": password,
        "devices": {
            "Laptop": "online",
            "Phone": "offline"
        }
    }

    return RedirectResponse("/login", status_code=302)

# ------------------------
# LOGIN
# ------------------------
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request
    })

@app.post("/login")
async def login(
    username: str = Form(...),
    password: str = Form(...)
):
    user = accounts.get(username)
    if not user or user["password"] != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = str(uuid.uuid4())
    sessions[token] = username

    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie("session", token, httponly=True)
    return response

# ------------------------
# DASHBOARD
# ------------------------
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {
        "request": request
    })

# ------------------------
# API: ACCOUNTS (NO 500)
# ------------------------
@app.get("/accounts")
async def get_account(request: Request):
    token = request.cookies.get("session")

    if not token or token not in sessions:
        return JSONResponse(status_code=401, content={"error": "Not logged in"})

    username = sessions[token]
    account = accounts.get(username)

    return {
        "name": username,
        "devices": account["devices"]
    }
