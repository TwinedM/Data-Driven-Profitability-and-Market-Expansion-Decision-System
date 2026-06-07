"""
local dev: set MONGODB_URI in your .env file
Production: set MONGODB_URL as env variable on Render/Atlas

Install:
    pip install pymongo[srv] python-dotenv
Atlas URI format:
    mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/revenue_intel?retryWrites=true&w=majority

Local URI format:
    mongodb://localhost:27017

"""

import os
from pymongo import MongoClient
from pymongo.database import Database
from typing import Generator

# Connection uri

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.environ.get("MONGODB_DB","revenue_intel")

# Module-level client
_client: MongoClient | None = None

def get_client() -> MongoClient:
    """
    Returns the shared MongoClient instance
    Creates it on first call(lazy init)
    """
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI)
    return _client

def get_database() -> Database:
    return get_client()[DB_NAME]

def init_db() -> None:
    
    db = get_database()

    db.users.create_index("email",unique = True)
    db.subscriptions.create_index("user_id")
    db.subscriptions.create_index([("user_id", 1), ("status", 1), ("end_date", 1)])
    # reports — lookup by user and by report_id
    db.reports.create_index("user_id")
    db.reports.create_index("report_id", unique=True)

    print(f"[DB] MongoDB connected · database='{DB_NAME}'")

def get_db() -> Generator[Database,None,None]:
    """
    FastAPI dependency — yields the database for a request.

    Usage in a route:
        from fastapi import Depends
        from database import get_db
        from pymongo.database import Database

        @app.get("/example")
        def example(db: Database = Depends(get_db)):
            ...
    """
    yield get_database()     