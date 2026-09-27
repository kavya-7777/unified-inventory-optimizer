"""API v1 router — Dashboard 'control tower' summary."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.deps import get_db
from app.schemas.dashboard import DashboardSummaryOut
from app.services.dashboard import build_dashboard_summary

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/dashboard/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(db: Session = Depends(get_db)):
    return build_dashboard_summary(db)
