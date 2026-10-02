from typing import Callable, Iterator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session_factory() -> Callable[[], Session]:
    """Session factory for background jobs, which outlive the request's session."""
    return SessionLocal
