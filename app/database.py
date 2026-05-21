"""
database.py — Database initialization
Creates the SQLite file and all tables on startup.
SessionLocal is used in every route to talk to the database.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# SQLite file will be created at app/revenue_intel.db
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'revenue_intel.db')}"

# Engine = the connection to the database file
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # needed for SQLite with FastAPI
)

# SessionLocal = factory for database sessions (one per request)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base = parent class for all our models
Base = declarative_base()


def init_db():
    """
    Creates all tables in the database if they don't exist yet.
    Called once when the FastAPI app starts.
    """
    # Import models here so Base knows about them before creating tables
    import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI dependency — gives each route a database session.
    Automatically closes the session when the request is done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()