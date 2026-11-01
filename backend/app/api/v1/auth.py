"""API v1 router — Login and the signed-in user's own account."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    CurrentUser,
    create_access_token,
    get_current_user,
    hash_password,
    login_limiter,
    verify_password,
)
from app.db.deps import get_db
from app.models.base import utcnow
from app.models.users import User
from app.schemas.users import ChangePasswordRequest, LoginRequest, LoginResponse, UserOut
from app.services.users import get_by_email, record_event

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Checked against when the email is unknown, so response time doesn't reveal which
# emails have accounts.
_DUMMY_HASH = hash_password("timing-equaliser")


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    key = f"{client_ip}|{payload.email}"
    wait = login_limiter.retry_after(key)
    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Try again in {max(1, wait // 60)} minute(s).",
            headers={"Retry-After": str(wait)},
        )

    user = get_by_email(db, payload.email)
    valid = verify_password(payload.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not valid:
        login_limiter.record_failure(key)
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")

    login_limiter.reset(key)
    user.last_login_at = utcnow()
    db.commit()
    db.refresh(user)
    return {
        "access_token": create_access_token(user),
        "expires_in": settings.JWT_EXPIRE_MINUTES * 60,
        "user": user,
    }


@router.get("/me", response_model=UserOut)
def me(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.get(User, current.id)
    if user is None:  # the machine API key has no user row
        return UserOut(id=current.id, email=current.email, name=current.name,
                       role=current.role, is_active=True)
    return user


@router.post("/change-password", status_code=204)
def change_password(
    payload: ChangePasswordRequest,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, current.id)
    if user is None:
        raise HTTPException(status_code=400, detail="This account has no password")
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400,
                            detail="New password must differ from the current one")
    user.password_hash = hash_password(payload.new_password)
    record_event(db, current, "user.change_password", "user", user.id, commit=False)
    db.commit()
