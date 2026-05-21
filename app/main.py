import uuid
import os
import tempfile
import json
import razorpay
import hmac
import hashlib
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
from fastapi.requests import Request
from pathlib import Path
from typing import Any



from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import pandas as pd

# Your existing modules — untouched
import kpi_engine
import insights as ins_module
import ai_insights as ai_module

from itsdangerous import URLSafeTimedSerializer, BadSignature
from fastapi.responses import RedirectResponse
from fastapi import Form as FastAPIForm
import bcrypt
from database import get_db, SessionLocal
from models import User, Subscription, Report
from sqlalchemy.orm import Session

# Secret key for signing cookies — change this to a random string in production
SECRET_KEY = "revenue-intel-secret-key-change-in-production"
serializer = URLSafeTimedSerializer(SECRET_KEY)

# ── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Revenue Intelligence API",
    description="Upload any sales CSV → get automated KPI analysis + AI-ready insights",
    version="2.0.0",
)
from database import init_db
init_db()

# In-memory store: { report_id: { "kpis": ..., "insights": ..., "filename": ... } }
# Note: this resets on server restart. Phase 3 will add a real DB.
REPORT_STORE: dict[str, dict] = {}

# ── Helpers ──────────────────────────────────────────────────────────────────

def kpis_to_json_safe(kpis: dict) -> dict:
    """
    kpi_engine returns pandas DataFrames inside the dict.
    JSON can't serialize DataFrames, so we convert them to list-of-dicts.
    Scalar values (float, int) pass through unchanged.
    """
    result = {}
    for key, val in kpis.items():
        if isinstance(val, pd.DataFrame):
            result[key] = val.to_dict(orient="records")
        elif isinstance(val, float) and pd.isna(val):
            result[key] = None
        else:
            result[key] = val
    return result


def insights_to_dicts(insight_list) -> list:
    """Convert list of Insight dataclasses → list of plain dicts for JSON."""
    return [
        {
            "title":        i.title,
            "detail":       i.detail,
            "impact":       i.impact,
            "action":       i.action,
            "category":     i.category,
            "metric_value": i.metric_value,
        }
        for i in insight_list
    ]


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """
    Railway and other platforms ping this to check if the app is alive.
    Always returns 200 OK with a simple status message.
    """
    return {"status": "ok", "version": "2.0.0"}

@app.get("/upload", response_class=HTMLResponse)
def upload_page_direct(request: Request):
    from dependencies import require_subscription
    result = require_subscription(request)
    if isinstance(result, RedirectResponse):
        return result
    return templates.TemplateResponse(request, "upload.html")

@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """
    Accept a CSV file upload.
    Runs kpi_engine + insights on it.
    Stores results in memory.
    Returns a report_id you use to fetch results.

    Why async? FastAPI is built on async Python (ASGI).
    File I/O should be async so the server doesn't block on large uploads.
    """
    # Validate file type
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    # Save uploaded file to a temp location so kpi_engine can read it
    contents = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        # Run your existing KPI engine — zero changes to kpi_engine.py
        kpis, df = kpi_engine.run(tmp_path)
        insight_list = ai_module.generate_ai_insights(kpis, file.filename)
    except Exception as e:
        os.unlink(tmp_path)  # clean up temp file
        raise HTTPException(status_code=422, detail=f"Failed to process CSV: {str(e)}")
    finally:
        # Always clean up the temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # Generate a unique ID for this report
    report_id = str(uuid.uuid4())[:8]  # short 8-char ID, e.g. "a3f9c1b2"

    # Store results
    REPORT_STORE[report_id] = {
        "kpis":     kpis,           # raw (with DataFrames) — for dashboard rendering
        "kpis_json": kpis_to_json_safe(kpis),  # serialized — for /report endpoint
        "insights": insight_list,
        "filename": file.filename,
    }

    return {
        "report_id":    report_id,
        "filename":     file.filename,
        "total_orders": int(kpis["total_orders"]),
        "total_revenue": round(float(kpis["total_revenue"]), 2),
        "insight_count": len(insight_list),
        "endpoints": {
            "report":    f"/report/{report_id}",
            "dashboard": f"/dashboard/{report_id}",
        }
    }


@app.get("/report/{report_id}")
def get_report(report_id: str):
    """
    Returns full KPI data as JSON for a given report_id.
    This is what a frontend app or data pipeline would consume.
    """
    if report_id not in REPORT_STORE:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")

    data = REPORT_STORE[report_id]
    return JSONResponse(content={
        "report_id": report_id,
        "filename":  data["filename"],
        "kpis":      data["kpis_json"],
        "insights":  insights_to_dicts(data["insights"]),
    })


@app.get("/dashboard/{report_id}", response_class=HTMLResponse)
def get_dashboard(report_id: str):
    """
    Renders the full HTML dashboard for a given report.
    Re-uses all the Plotly chart functions from dashboard.py.
    """
    if report_id not in REPORT_STORE:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")

    # Import dashboard rendering functions
    # We import here (not at top) to avoid circular issues
    import dashboard as dash_module

    data = REPORT_STORE[report_id]
    kpis = data["kpis"]
    insight_list = data["insights"]

    # Build the HTML using dashboard.py's existing functions
    html = dash_module.render_dashboard(
        kpis=kpis,
        insights=insight_list,
    )
    return HTMLResponse(content=html)
from fastapi import Form
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
import json

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    from dependencies import get_current_user
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/upload", status_code=302)
    return templates.TemplateResponse(request, "index.html")


@app.post("/detect-columns")
async def detect_columns(file: UploadFile = File(...)):
    """
    Step 1 of Phase 3 upload flow.
    Reads CSV headers, runs fuzzy matching, returns suggested mapping + confidence scores.
    The frontend uses this to render the column mapping UI.
    """
    from column_mapper import auto_detect_columns, FIELD_ALIASES
    from difflib import SequenceMatcher

    contents = await file.read()
    # Only need the first line — much faster than reading whole file
    first_line = contents.decode("utf-8", errors="ignore").split("\n")[0]
    headers = [h.strip().strip('"') for h in first_line.split(",")]

    mapping = auto_detect_columns(headers)

    # Also return confidence scores so frontend can color-code them
    confidence = {}
    for field, matched_header in mapping.items():
        if matched_header is None:
            confidence[field] = 0.0
        else:
            from column_mapper import FIELD_ALIASES, _similarity
            aliases = FIELD_ALIASES.get(field, [])
            norm = matched_header.lower().strip().replace("-", " ").replace("_", " ")
            confidence[field] = max((_similarity(norm, a) for a in aliases), default=0.0)

    return {
        "headers": headers,
        "mapping": mapping,
        "confidence": confidence,
    }


@app.post("/upload-mapped")
async def upload_mapped(
    file: UploadFile = File(...),
    mapping: str = Form(...)   # JSON string from the frontend
):
    """
    Step 2 of Phase 3 upload flow.
    Receives the CSV + confirmed column mapping.
    Applies mapping, runs kpi_engine with renamed columns, stores report.
    """
    import json
    from column_mapper import apply_mapping, get_missing_required

    col_map = json.loads(mapping)

    # Validate required fields are mapped
    missing = get_missing_required(col_map)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Required columns not mapped: {', '.join(missing)}"
        )

    contents = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        import pandas as pd
        df_raw = pd.read_csv(tmp_path)
        df_raw.columns = df_raw.columns.str.strip()
        df_mapped = apply_mapping(df_raw, col_map)
        df_processed = kpi_engine.load_data_from_df(df_mapped)
        if "status" not in df_processed.columns:
            df_processed["status"] = "Shipped"
        kpis = kpi_engine.compute_kpis(df_processed)
        insight_list = ai_module.generate_ai_insights(kpis, file.filename)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to process CSV: {str(e)}")
    finally:
        for p in [tmp_path]:
            if os.path.exists(p): os.unlink(p)

    report_id = str(uuid.uuid4())[:8]
    REPORT_STORE[report_id] = {
        "kpis":      kpis,
        "kpis_json": kpis_to_json_safe(kpis),
        "insights":  insight_list,
        "filename":  file.filename,
    } 

    return {
        "report_id":     report_id,
        "filename":      file.filename,
        "total_orders":  int(kpis["total_orders"]),
        "total_revenue": round(float(kpis["total_revenue"]), 2),
        "insight_count": len(insight_list),
    }
  

# ── Auth Routes ───────────────────────────────────────────────────────────────

@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse(request, "signup.html", {})

@app.post("/signup")
def signup(
    request: Request,
    email: str = FastAPIForm(...),
    password: str = FastAPIForm(...)
):
    db = SessionLocal()
    try:
        # Check if email already exists
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return templates.TemplateResponse(request, "signup.html", {
                "error": "Email already registered. Please log in."
            })

        # Hash the password — never store plain text
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        # Create new user
        user = User(email=email, password_hash=password_hash)
        db.add(user)
        db.commit()

        # Redirect to login with success message
        return RedirectResponse(url="/login?message=Account created! Please log in.", status_code=302)
    finally:
        db.close()


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, message: str = None):
    return templates.TemplateResponse(request, "login.html", {"message": message})


@app.post("/login")
def login(
    request: Request,
    email: str = FastAPIForm(...),
    password: str = FastAPIForm(...)
):
    db = SessionLocal()
    try:
        # Find user by email
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return templates.TemplateResponse(request, "login.html", {
                "error": "No account found with that email."
            })

        # Check password
        if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            return templates.TemplateResponse(request, "login.html", {
                "error": "Incorrect password."
            })

        # Create signed session cookie with user ID
        token = serializer.dumps({"user_id": user.id})

        response = RedirectResponse(url="/upload", status_code=302)
        response.set_cookie(
            key="session",
            value=token,
            httponly=True,   # JS can't read this cookie — security
            max_age=60*60*24*7  # 7 days
        )
        return response
    finally:
        db.close()


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session")
    return response



# ── Payment Routes ────────────────────────────────────────────────────────────

@app.get("/pricing", response_class=HTMLResponse)
def pricing_page(request: Request, message: str = None):
    return templates.TemplateResponse(request, "pricing.html", {"message": message})


@app.post("/create-order")
async def create_order(request: Request):
    from dependencies import get_current_user
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")

    body = await request.json()
    plan   = body.get("plan")
    amount = body.get("amount")  # in paise (₹2999 = 299900 paise)

    if plan not in ["monthly", "sixmonth"]:
        raise HTTPException(status_code=400, detail="Invalid plan")

    key_id     = os.environ.get("RAZORPAY_KEY_ID")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET")

    client = razorpay.Client(auth=(key_id, key_secret))

    order = client.order.create({
        "amount":   amount,
        "currency": "INR",
        "payment_capture": 1
    })

    return {
        "order_id":       order["id"],
        "amount":         amount,
        "razorpay_key_id": key_id,
        "email":          user.email,
    }


@app.post("/verify-payment")
async def verify_payment(request: Request):
    from dependencies import get_current_user
    from datetime import timedelta

    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")

    body = await request.json()
    order_id   = body.get("razorpay_order_id")
    payment_id = body.get("razorpay_payment_id")
    signature  = body.get("razorpay_signature")
    plan       = body.get("plan")

    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")

    # Verify signature — this proves Razorpay actually sent this
    # If someone fakes a payment, this check catches them
    message = f"{order_id}|{payment_id}"
    expected = hmac.new(
        key_secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    if expected != signature:
        return {"success": False, "detail": "Invalid signature"}

    # Activate subscription in database
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        end_date = now + timedelta(days=30 if plan == "monthly" else 180)

        # Expire any existing subscriptions
        existing = db.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.status == "active"
        ).all()
        for sub in existing:
            sub.status = "expired"

        # Create new subscription
        new_sub = Subscription(
            user_id    = user.id,
            plan       = plan,
            start_date = now,
            end_date   = end_date,
            status     = "active"
        )
        db.add(new_sub)
        db.commit()

        return {"success": True}
    finally:
        db.close()

# ── Dev server entry point ────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)