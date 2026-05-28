"""
models.py — MongoDB document helpers
Replaces SQLAlchemy ORM classes with plain Python dataclasses + helper
functions that read/write directly to PyMongo collections.

Three collections: users, subscriptions, reports

All IDs are MongoDB ObjectIds (stored as strings in session cookies
so we don't have to serialise bson.ObjectId objects ourselves).

Usage pattern:
    db = get_database()

    # Create a user
    user = create_user(db, email="a@b.com", password_hash="hashed")

    # Fetch a user
    user = get_user_by_email(db, "a@b.com")
    user = get_user_by_id(db, "64f1a2b3c4d5e6f7a8b9c0d1")

    # Subscriptions
    sub  = create_subscription(db, user_id=..., plan="monthly", end_date=...)
    ok   = is_subscription_active(db, user_id=...)

    # Reports
    rep  = create_report(db, user_id=..., filename="sales.csv", report_id="a3f9c1b2")
"""

from datetime import datetime
from bson import ObjectId
from pymongo.database import Database


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _str_id(doc: dict) -> dict:
    """
    Convert MongoDB's _id (ObjectId) → plain string "id"
    so the rest of the app never has to import bson.
    """
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


# ─────────────────────────────────────────────────────────────────────────────
# Users  (collection: users)
# ─────────────────────────────────────────────────────────────────────────────
#
# Document shape:
#   {
#     _id:           ObjectId,
#     email:         str  (unique),
#     password_hash: str,
#     created_at:    datetime
#   }

def create_user(db: Database, email: str, password_hash: str) -> dict | None:
    """
    Insert a new user. Returns the created document (with "id" key)
    or None if the email already exists.
    """

    normalized_email = email.lower().strip()

    # Explicit duplicate check
    existing = db.users.find_one({
        "email": normalized_email
    })

    if existing:
        return None

    result = db.users.insert_one({
        "email": normalized_email,
        "password_hash": password_hash,
        "created_at": datetime.utcnow(),
    })

    return get_user_by_id(db, str(result.inserted_id))


def get_user_by_email(db: Database, email: str) -> dict | None:
    """Fetch a user by email. Returns dict with 'id' key, or None."""
    doc = db.users.find_one({"email": email.lower().strip()})
    return _str_id(doc) if doc else None


def get_user_by_id(db: Database, user_id: str) -> dict | None:
    """Fetch a user by their string ObjectId. Returns dict with 'id' key, or None."""
    try:
        doc = db.users.find_one({"_id": ObjectId(user_id)})
        return _str_id(doc) if doc else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Subscriptions  (collection: subscriptions)
# ─────────────────────────────────────────────────────────────────────────────
#
# Document shape:
#   {
#     _id:        ObjectId,
#     user_id:    str  (stringified ObjectId of the user),
#     plan:       str  ("monthly" | "sixmonth"),
#     start_date: datetime,
#     end_date:   datetime,
#     status:     str  ("active" | "expired")
#   }

def create_subscription(
    db: Database,
    user_id: str,
    plan: str,
    end_date: datetime,
) -> dict:
    """Insert a new subscription and return it."""
    result = db.subscriptions.insert_one({
        "user_id":    user_id,
        "plan":       plan,
        "start_date": datetime.utcnow(),
        "end_date":   end_date,
        "status":     "active",
    })
    doc = db.subscriptions.find_one({"_id": result.inserted_id})
    return _str_id(doc)


def is_subscription_active(db: Database, user_id: str) -> bool:
    """
    Returns True if the user has at least one active subscription
    whose end_date is in the future.
    """
    doc = db.subscriptions.find_one({
        "user_id": user_id,
        "status":  "active",
        "end_date": {"$gt": datetime.utcnow()},
    })
    return doc is not None


def expire_old_subscriptions(db: Database, user_id: str) -> None:
    """
    Mark all expired subscriptions as 'expired'.
    Optional — call from a background job or at login time.
    """
    db.subscriptions.update_many(
        {
            "user_id": user_id,
            "status":  "active",
            "end_date": {"$lte": datetime.utcnow()},
        },
        {"$set": {"status": "expired"}},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Reports  (collection: reports)
# ─────────────────────────────────────────────────────────────────────────────
#
# Document shape:
#   {
#     _id:        ObjectId,
#     user_id:    str,
#     filename:   str,
#     report_id:  str  (short 8-char slug like "a3f9c1b2"),
#     created_at: datetime
#   }

def create_report(
    db: Database,
    user_id: str,
    filename: str,
    report_id: str,
) -> dict:
    """Insert a report record and return it."""
    result = db.reports.insert_one({
        "user_id":    user_id,
        "filename":   filename,
        "report_id":  report_id,
        "created_at": datetime.utcnow(),
    })
    doc = db.reports.find_one({"_id": result.inserted_id})
    return _str_id(doc)


def get_report_by_id(db: Database, report_id: str) -> dict | None:
    """Fetch a report by its short slug."""
    doc = db.reports.find_one({"report_id": report_id})
    return _str_id(doc) if doc else None


def get_reports_for_user(db: Database, user_id: str) -> list[dict]:
    """Return all reports for a user, newest first."""
    cursor = db.reports.find(
        {"user_id": user_id},
        sort=[("created_at", -1)],
    )
    return [_str_id(doc) for doc in cursor]
