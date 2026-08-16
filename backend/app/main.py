from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(
    title="MEIO Platform API",
    version="1.0.0",
)

# CORS configuration
if settings.CORS_ORIGINS:
    origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/health/ready")
def health_ready():
    # In a real app, verify database connection here
    try:
        from app.db.session import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        return {"status": "unhealthy", "detail": str(e)}

# Stubs for required API endpoints
@app.get("/api/v1/products")
def get_products():
    return []

@app.get("/api/v1/locations")
def get_locations():
    return []

@app.post("/api/v1/forecast/run")
def run_forecast():
    return {"status": "accepted", "pipeline_run_id": "mock-run-id"}

@app.post("/api/v1/optimization/run")
def run_optimization():
    return {"status": "accepted", "pipeline_run_id": "mock-run-id"}

@app.post("/api/v1/transportation/run")
def run_transportation():
    return {"status": "accepted", "pipeline_run_id": "mock-run-id"}
