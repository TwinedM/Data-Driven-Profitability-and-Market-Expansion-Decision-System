"""
dependencies.py — Auth + Subscription checks
Rewritten for MongoDB. Logic is identical to the SQLAlchemy version —
only the database calls have changed.

These functions are called at the start of protected routes.
"""

from fastapi import Request
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature
import os

from database import get_database
from models import get_user_by_id, is_subscription_active

SECRET_KEY = os.environ.get("SECRET_KEY", "revenue-intel-secret-key-change-in-production")
serializer = URLSafeTimedSerializer(SECRET_KEY)


def get_current_user(request: Request) -> dict | None:
    """
    Reads the session cookie and returns the user document (dict with "id" key).
    Returns None if not logged in or cookie is invalid/expired.
    """
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        data    = serializer.loads(token, max_age=60 * 60 * 24 * 7)  # 7 days
        user_id = data.get("user_id")
    except BadSignature:
        return None

    db = get_database()
    return get_user_by_id(db, user_id)


def require_login(request: Request):
    """
    Call at the start of any login-protected route.
    Returns the user dict if logged in, or a RedirectResponse to /login.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return user


def require_subscription(request: Request):
    """
    Call at the start of any route that needs an active subscription.
    Returns the user dict if logged in + subscribed.
    Redirects to /login if not logged in.
    Redirects to /pricing if logged in but no active subscription.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_database()
    if not is_subscription_active(db, user["id"]):
        return RedirectResponse(
            url="/pricing?message=Subscribe to access reports",
            status_code=302,
        )
    return user
