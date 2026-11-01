"""
Unified Inventory Optimizer — FastAPI Application Entry Point.
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import (
    auth,
    dashboard,
    data,
    demand,
    inventory,
    optimization,
    policies,
    transportation,
    users,
)
from app.core.config import settings
from app.core.security import get_current_user
from app.db.deps import get_db
from app.db.session import SessionLocal
from app.services.users import ensure_bootstrap_admin

logging.basicConfig(level=settings.LOG_LEVEL)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        with SessionLocal() as db:
            ensure_bootstrap_admin(db)
    except Exception:
        log.exception("Could not check for the first admin account at startup")
    yield


app = FastAPI(
    title="Unified Inventory Optimizer API",
    version="1.0.0",
    description="Unified Inventory Optimization Platform",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start_time
        log.info(f"{request.method} {request.url.path} - {response.status_code} - {elapsed:.4f}s")
        return response


app.add_middleware(RequestLoggingMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled exception on {request.method} {request.url.path}", exc_info=exc)
    content = {"detail": "Internal Server Error"}
    if settings.DEBUG:
        content["message"] = str(exc)
    return JSONResponse(status_code=500, content=content)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    log.warning(f"Validation error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation Error", "errors": jsonable_errors(exc)},
    )


def jsonable_errors(exc: RequestValidationError) -> list:
    return [{k: v for k, v in err.items() if k != "ctx"} for err in exc.errors()]


# Every data route needs a signed-in user; routes that change data also check the role.
signed_in = [Depends(get_current_user)]
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(data.router)
app.include_router(inventory.router, dependencies=signed_in)
app.include_router(optimization.router, dependencies=signed_in)
app.include_router(demand.router, dependencies=signed_in)
app.include_router(policies.router, dependencies=signed_in)
app.include_router(dashboard.router, dependencies=signed_in)
app.include_router(transportation.router, dependencies=signed_in)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def health_ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        log.exception("Readiness check failed")
        return JSONResponse(status_code=503, content={"status": "unhealthy"})
