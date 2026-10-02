"""
MEIO Platform — FastAPI Application Entry Point.
"""
import logging
import time

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import demand, inventory, optimization
from app.core.config import settings
from app.db.deps import get_db

logging.basicConfig(level=settings.LOG_LEVEL)
log = logging.getLogger(__name__)

app = FastAPI(
    title="MEIO Platform API",
    version="1.0.0",
    description="Multi-Echelon Inventory Optimization Platform",
)

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


app.include_router(inventory.router)
app.include_router(optimization.router)
app.include_router(demand.router)


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
