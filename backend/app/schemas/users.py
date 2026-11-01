"""Schemas for login, users and the activity log."""
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator

Role = Literal["admin", "planner", "viewer"]
PASSWORD_MIN = 8


def _clean_email(value: str) -> str:
    value = value.strip().lower()
    local, _, domain = value.partition("@")
    if not local or "." not in domain or " " in value:
        raise ValueError("Enter a valid email address")
    return value


class LoginRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=200)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.strip().lower()


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserOut


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=200)


class UserCreate(BaseModel):
    email: str = Field(max_length=255)
    name: str = Field(min_length=1, max_length=120)
    role: Role = "viewer"
    password: str = Field(min_length=PASSWORD_MIN, max_length=200)

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        return _clean_email(v)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name is required")
        return v.strip()


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    role: Optional[Role] = None
    is_active: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=200)


class AuditEventOut(BaseModel):
    id: int
    user_email: str
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}
