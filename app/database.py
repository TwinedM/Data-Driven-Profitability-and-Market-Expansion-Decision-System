"""
database.py — PostgreSQL database initialization
Switched from SQLite to PostgreSQL for persistence across server restarts.
SQLAlchemy handles both identically — only the connection URL changes.

Local dev:  set DATABASE_URL in your .env file
Production: set DATABASE_URL as environment variable on Render
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# PostgreSQL on Render, SQLite fallback for local dev without env var
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    # Local fallback — SQLite so local dev still works without Postgres
    f"sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'revenue_intel.db')}"
)

# Render gives URLs starting with "postgres://" — SQLAlchemy needs "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Engine — connect_args only needed for SQLite
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    """
    Creates all tables if they don't exist.
    Called once on FastAPI startup.
    On PostgreSQL this is safe to call every restart — skips existing tables.
    """
    import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — one DB session per request, auto-closed after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()