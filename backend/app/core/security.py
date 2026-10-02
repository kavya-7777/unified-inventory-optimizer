import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    """Bearer-token guard for mutating endpoints. Disabled when API_KEY is unset."""
    if not settings.API_KEY:
        return
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(token, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
