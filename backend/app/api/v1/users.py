"""API v1 router — User management and the activity log (admin only)."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, hash_password, require_role
from app.db.deps import get_db
from app.models.users import AuditEvent, User
from app.schemas.users import (
    AuditEventOut,
    ResetPasswordRequest,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.services.users import active_admin_count, create_user, get_by_email, record_event

router = APIRouter(prefix="/api/v1", tags=["users"])
admin_only = require_role("admin")


@router.get("/users", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), _: CurrentUser = Depends(admin_only)):
    return db.query(User).order_by(User.created_at).all()


@router.post("/users", response_model=UserOut, status_code=201)
def add_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(admin_only),
):
    if get_by_email(db, payload.email):
        raise HTTPException(status_code=409, detail="A user with this email already exists")
    user = create_user(db, payload.email, payload.name, payload.role, payload.password)
    record_event(db, current, "user.create", "user", user.id,
                 {"email": user.email, "role": user.role})
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(admin_only),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)

    removes_admin = user.role == "admin" and user.is_active and (
        changes.get("role", "admin") != "admin" or changes.get("is_active") is False
    )
    if removes_admin:
        if user.id == current.id:
            raise HTTPException(status_code=400,
                                detail="You can't remove your own admin access or deactivate "
                                       "yourself. Ask another admin.")
        if active_admin_count(db) <= 1:
            raise HTTPException(status_code=400, detail="At least one active admin must remain")

    for field, value in changes.items():
        setattr(user, field, value)
    record_event(db, current, "user.update", "user", user.id, {"email": user.email, **changes},
                 commit=False)
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/reset-password", status_code=204)
def reset_password(
    user_id: str,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(admin_only),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(payload.new_password)
    record_event(db, current, "user.reset_password", "user", user.id, {"email": user.email},
                 commit=False)
    db.commit()


@router.get("/audit", response_model=List[AuditEventOut])
def list_audit_events(
    action: Optional[str] = None,
    user_email: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(admin_only),
):
    query = db.query(AuditEvent)
    if action:
        query = query.filter(AuditEvent.action.like(f"{action}%"))
    if user_email:
        query = query.filter(AuditEvent.user_email == user_email.strip().lower())
    return (query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .offset(skip).limit(limit).all())
