# schemas.py

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, ConfigDict


# =============================================================================
# Base Schema
# =============================================================================

class BaseSchema(BaseModel):

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )


# =============================================================================
# User Schemas
# =============================================================================

class UserSignup(BaseSchema):

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )


class UserLogin(BaseSchema):

    email: EmailStr
    password: str


class UserResponse(BaseSchema):

    id: str

    email: EmailStr

    created_at: datetime


# =============================================================================
# Subscription Schemas
# =============================================================================

class SubscriptionCreate(BaseSchema):

    user_id: str

    plan: Literal[
        "monthly",
        "sixmonth",
    ]

    end_date: datetime


class SubscriptionResponse(BaseSchema):

    id: str

    user_id: str

    plan: str

    start_date: datetime
    end_date: datetime

    status: Literal[
        "active",
        "expired",
    ]


# =============================================================================
# Report Schemas
# =============================================================================

class ReportCreate(BaseSchema):

    user_id: str

    filename: str = Field(
        min_length=1,
        max_length=255,
    )

    report_id: str = Field(
        min_length=8,
        max_length=32,
    )


class ReportResponse(BaseSchema):

    id: str

    user_id: str

    filename: str

    report_id: str

    created_at: datetime


# =============================================================================
# Generic API Responses
# =============================================================================

class MessageResponse(BaseSchema):

    message: str


class ErrorResponse(BaseSchema):

    error: str