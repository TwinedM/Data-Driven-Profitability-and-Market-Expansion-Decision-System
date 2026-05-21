"""
models.py — Database table definitions
Three tables: User, Subscription, Report
SQLAlchemy maps these Python classes to SQLite tables automatically.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"

    id           = Column(Integer, primary_key=True, index=True)
    email        = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow)

    # Relationships — lets you do user.subscriptions, user.reports
    subscriptions = relationship("Subscription", back_populates="user")
    reports       = relationship("Report", back_populates="user")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan       = Column(String, nullable=False)  # "monthly" or "sixmonth"
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date   = Column(DateTime, nullable=False)
    status     = Column(String, default="active")  # "active" or "expired"

    user = relationship("User", back_populates="subscriptions")


class Report(Base):
    __tablename__ = "reports"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename   = Column(String, nullable=False)
    report_id  = Column(String, nullable=False)  # the 8-char ID like "a3f9c1b2"
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="reports")