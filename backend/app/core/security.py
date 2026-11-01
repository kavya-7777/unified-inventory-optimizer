"""
Authentication and role-based access.

People log in with email + password and get a signed JWT (Bearer token). The optional
API_KEY is a machine token for scheduled jobs and acts as a planner called "system".
"""
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Deque, Dict, Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.deps import get_db
from app.models.users import User

JWT_ALGORITHM = "HS256"
ROLE_RANK = {"viewer": 1, "planner": 2, "admin": 3}
SYSTEM_EMAIL = "system"


# ── Passwords ────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# ── Tokens ───────────────────────────────────────────────────────────────────

def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str
    name: str
    role: str

    def has_role(self, minimum: str) -> bool:
        return ROLE_RANK.get(self.role, 0) >= ROLE_RANK[minimum]


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized()

    if settings.API_KEY and secrets.compare_digest(token, settings.API_KEY):
        return CurrentUser(id=SYSTEM_EMAIL, email=SYSTEM_EMAIL, name="Scheduled job",
                           role="planner")

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Session expired, please log in again") from None
    except jwt.InvalidTokenError:
        raise _unauthorized("Invalid token") from None

    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise _unauthorized("Account not found or deactivated")
    return CurrentUser(id=user.id, email=user.email, name=user.name, role=user.role)


def require_role(minimum: str) -> Callable[..., CurrentUser]:
    """Dependency: the caller must have at least this role (viewer < planner < admin)."""
    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.has_role(minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action needs the {minimum} role or higher",
            )
        return user
    return dependency


# ── Login rate limiting ──────────────────────────────────────────────────────

class LoginRateLimiter:
    """
    In-memory sliding window of failed logins per (client IP, email). Good enough for a
    single backend instance; a multi-instance deployment would keep this in Redis.
    """

    def __init__(self, max_failures: int = 5, window_seconds: int = 15 * 60):
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> Deque[float]:
        q = self._failures[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def retry_after(self, key: str) -> int:
        """Seconds until another attempt is allowed; 0 when not blocked."""
        with self._lock:
            now = time.monotonic()
            q = self._prune(key, now)
            if len(q) < self.max_failures:
                return 0
            return max(1, int(self.window - (now - q[0])))

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._prune(key, time.monotonic()).append(time.monotonic())

    def reset(self, key: Optional[str] = None) -> None:
        with self._lock:
            if key is None:
                self._failures.clear()
            else:
                self._failures.pop(key, None)


login_limiter = LoginRateLimiter()
