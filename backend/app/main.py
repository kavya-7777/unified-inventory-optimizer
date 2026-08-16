"""
MEIO Platform — FastAPI Application Entry Point.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.api.v1 import inventory, optimization

logging.basicConfig(level=settings.LOG_LEVEL)
log = logging.getLogger(__name__)

app = FastAPI(
    title="MEIO Platform API",
    version="1.0.0",
    description="Multi-Echelon Inventory Optimization Platform",
)

# ─── CORS ────────────────────────────────────────────────────────────────────
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(inventory.router)
app.include_router(optimization.router)


# ─── Health ──────────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def health_ready():
    try:
        from app.db.session import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        log.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "detail": str(e)}
