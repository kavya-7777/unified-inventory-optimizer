"""User accounts, the first-admin bootstrap and the activity log."""
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import CurrentUser, hash_password
from app.models.users import AuditEvent, User

log = logging.getLogger(__name__)


def record_event(
    db: Session,
    user: CurrentUser,
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    commit: bool = True,
) -> None:
    """Append to the activity log. Pass commit=False to join the caller's transaction."""
    db.add(AuditEvent(user_email=user.email, action=action, entity_type=entity_type,
                      entity_id=entity_id, details=details))
    if commit:
        db.commit()


def get_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.strip().lower()).first()


def create_user(db: Session, email: str, name: str, role: str, password: str) -> User:
    user = User(email=email.strip().lower(), name=name.strip(), role=role,
                password_hash=hash_password(password), is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def active_admin_count(db: Session) -> int:
    return db.query(User).filter(User.role == "admin", User.is_active.is_(True)).count()


def ensure_bootstrap_admin(db: Session) -> Optional[User]:
    """
    Create the first admin from ADMIN_EMAIL / ADMIN_PASSWORD when no users exist yet,
    so a fresh deployment can be logged into. Does nothing once any user exists.
    """
    if db.query(User.id).first() is not None:
        return None
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        log.warning("No users exist and ADMIN_EMAIL/ADMIN_PASSWORD are not set: "
                    "nobody can log in until they are.")
        return None
    user = create_user(db, settings.ADMIN_EMAIL, settings.ADMIN_NAME, "admin",
                       settings.ADMIN_PASSWORD)
    log.info(f"Created first admin account {user.email}")
    return user
