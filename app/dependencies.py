"""
dependencies.py — Auth + Subscription checks
These functions are called at the start of protected routes.
"""

from fastapi import Request
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature
from database import SessionLocal
from models import User, Subscription
from datetime import datetime

SECRET_KEY = "revenue-intel-secret-key-change-in-production"
serializer = URLSafeTimedSerializer(SECRET_KEY)


def get_current_user(request: Request):
    """
    Reads the session cookie and returns the User object.
    Returns None if not logged in or cookie is invalid.
    """
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        data = serializer.loads(token, max_age=60*60*24*7)  # 7 days
        user_id = data.get("user_id")
    except BadSignature:
        return None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        return user
    finally:
        db.close()


def is_subscription_active(user_id: int) -> bool:
    """
    Returns True if user has an active subscription that hasn't expired.
    Returns False if no subscription or subscription expired.
    """
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.end_date > datetime.utcnow()
        ).first()
        return sub is not None
    finally:
        db.close()


def require_login(request: Request):
    """
    Call this at the start of any protected route.
    Returns the User if logged in, or a RedirectResponse to /login.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return user


def require_subscription(request: Request):
    """
    Call this at the start of any route that needs an active subscription.
    Returns the User if logged in + subscribed.
    Redirects to /login if not logged in.
    Redirects to /pricing if logged in but no active subscription.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if not is_subscription_active(user.id):
        return RedirectResponse(
            url="/pricing?message=Subscribe to access reports",
            status_code=302
        )
    return user