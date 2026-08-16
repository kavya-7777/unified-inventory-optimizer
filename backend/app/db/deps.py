"""Database dependency injection — shared across all API routers."""
from app.db.session import SessionLocal


def get_db():
    """FastAPI dependency that yields a SQLAlchemy session and ensures it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
