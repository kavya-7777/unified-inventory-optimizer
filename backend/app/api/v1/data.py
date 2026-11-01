"""API v1 router — Excel import/export, first-run setup status and demo data."""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import CurrentUser, get_current_user, require_role
from app.db.deps import get_db
from app.demo.seed import seed
from app.models.inventory import (
    DemandHistory,
    InventorySnapshot,
    Lane,
    Location,
    LocationProductPolicy,
    PipelineRun,
    Product,
)
from app.models.users import DataImport
from app.repositories.pipeline import PipelineRunRepository
from app.services.data_export import build_results_workbook
from app.services.data_import import ImportFileError, build_template, run_import
from app.services.users import record_event

router = APIRouter(prefix="/api/v1", tags=["data"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(content: bytes, filename: str) -> Response:
    return Response(content, media_type=XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/setup/status")
def setup_status(db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    """What's loaded so far; the UI shows a first-run screen while has_data is false."""
    counts = {
        "locations": db.query(func.count(Location.id)).scalar() or 0,
        "products": db.query(func.count(Product.id)).scalar() or 0,
        "lanes": db.query(func.count(Lane.id)).scalar() or 0,
        "policies": db.query(func.count(LocationProductPolicy.id)).scalar() or 0,
        "inventory_rows": db.query(func.count(InventorySnapshot.id)).scalar() or 0,
        "demand_rows": db.query(func.count(DemandHistory.id)).scalar() or 0,
        "runs": db.query(func.count(PipelineRun.id)).scalar() or 0,
    }
    return {**counts, "has_data": counts["policies"] > 0}


@router.get("/imports/template")
def download_template(
    include_data: bool = False,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    """The blank template, or (include_data=true) the current data in the same layout."""
    if include_data:
        return _xlsx(build_template(db), "inventory-data-current.xlsx")
    return _xlsx(build_template(), "inventory-import-template.xlsx")


@router.post("/imports")
async def upload_import(
    file: UploadFile = File(...),
    dry_run: bool = Query(True, description="Validate and preview only; nothing is saved"),
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_role("planner")),
) -> Dict[str, Any]:
    content = await file.read(settings.IMPORT_MAX_BYTES + 1)
    if len(content) > settings.IMPORT_MAX_BYTES:
        mb = settings.IMPORT_MAX_BYTES // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"File is larger than {mb} MB")
    try:
        return run_import(db, content, file.filename or "upload.xlsx", current, dry_run)
    except ImportFileError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


class ImportOut(BaseModel):
    id: str
    filename: str
    user_email: str
    summary: Any = None
    created_at: Any

    model_config = {"from_attributes": True}


@router.get("/imports", response_model=List[ImportOut])
def list_imports(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_role("planner")),
):
    return db.query(DataImport).order_by(DataImport.created_at.desc()).limit(limit).all()


@router.get("/exports/results")
def export_results(db: Session = Depends(get_db),
                   current: CurrentUser = Depends(get_current_user)):
    """Targets, inventory positions, transport plan and open alerts as one workbook."""
    content, filename = build_results_workbook(db, current.email)
    return _xlsx(content, filename)


class DemoDataRequest(BaseModel):
    reset: bool = False


@router.post("/admin/demo-data")
def load_demo_data(
    payload: DemoDataRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_role("admin")),
):
    """
    Loads the synthetic South-India network (28 locations, 50 SKUs, 120 days of sales
    ending yesterday). reset=true wipes all planning data and run history first.
    """
    if PipelineRunRepository(db).active_network_run():
        raise HTTPException(status_code=409,
                            detail="A pipeline run is in progress; try again when it finishes")
    counts = seed(db, reset=payload.reset)
    record_event(db, current, "data.demo_load", details={"reset": payload.reset, **counts})
    return counts
