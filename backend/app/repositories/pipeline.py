"""Repository: Data access layer for pipeline runs and optimization results."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func, insert
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.inventory import Alert, DemandForecast, OptimizationResult, PipelineRun

BATCH_SIZE = 1000


class PipelineRunRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, run_id: str, run_type: str, parameters: dict) -> PipelineRun:
        run = PipelineRun(id=run_id, run_type=run_type, status="running", parameters=parameters)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def complete(
        self, run_id: str, status: str, solver: str, fallback_used: bool, duration: float
    ) -> None:
        run = self.db.get(PipelineRun, run_id)
        if run:
            run.status = status
            run.solver = solver
            run.fallback_used = fallback_used
            run.finished_at = utcnow()
            run.duration_seconds = duration
        self.db.commit()

    def fail(self, run_id: str, error: str) -> None:
        self.db.rollback()
        run = self.db.get(PipelineRun, run_id)
        if run:
            run.status = "failed"
            run.error = error
            run.finished_at = utcnow()
            if run.started_at:
                run.duration_seconds = (run.finished_at - run.started_at).total_seconds()
            self.db.commit()

    def get_recent(self, skip: int = 0, limit: int = 10) -> List[PipelineRun]:
        return (
            self.db.query(PipelineRun)
            .order_by(PipelineRun.started_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_id(self, run_id: str) -> Optional[PipelineRun]:
        return self.db.get(PipelineRun, run_id)


class OptimizationResultRepository:
    def __init__(self, db: Session):
        self.db = db

    def bulk_save(self, pipeline_run_id: str, node_results: Dict[str, dict]) -> int:
        """Stages solver output for nodes mapped to a location; committed by the caller."""
        rows = [
            {
                "pipeline_run_id": pipeline_run_id,
                "location_id": r["location_id"],
                "product_id": r.get("product_id"),
                "s_in": r.get("s_in"),
                "s_out": r.get("s_out"),
                "net_replenishment_time": r.get("net_replenishment_time"),
                "safety_stock": r.get("safety_stock"),
                "reorder_point": r.get("reorder_point"),
                "order_quantity": r.get("order_quantity"),
                "objective_value": r.get("safety_stock_cost"),
            }
            for r in node_results.values()
            if r.get("location_id")
        ]
        for i in range(0, len(rows), BATCH_SIZE):
            self.db.execute(insert(OptimizationResult), rows[i:i + BATCH_SIZE])
        return len(rows)

    def get_all_latest(self) -> List[OptimizationResult]:
        """Most recent result per (location_id, product_id) across all runs."""
        latest = (
            self.db.query(
                OptimizationResult.location_id,
                OptimizationResult.product_id,
                func.max(OptimizationResult.id).label("max_id"),
            )
            .filter(
                OptimizationResult.location_id.isnot(None),
                OptimizationResult.product_id.isnot(None),
            )
            .group_by(OptimizationResult.location_id, OptimizationResult.product_id)
            .subquery()
        )
        return (
            self.db.query(OptimizationResult)
            .join(latest, OptimizationResult.id == latest.c.max_id)
            .all()
        )

    def get_by_run(self, pipeline_run_id: str) -> List[OptimizationResult]:
        return (
            self.db.query(OptimizationResult)
            .filter(OptimizationResult.pipeline_run_id == pipeline_run_id)
            .order_by(OptimizationResult.id)
            .all()
        )


class ForecastRepository:
    def __init__(self, db: Session):
        self.db = db

    def bulk_save(
        self,
        pipeline_run_id: str,
        forecasts: List[dict],
        node_keys: Dict[str, tuple],
        start: datetime,
    ) -> int:
        """Stages forecasts for items that map to a (location, product); committed by caller."""
        rows = []
        for f in forecasts:
            key = node_keys.get(f["id"])
            if not key:
                continue
            for h, qty in enumerate(f["forecast"], start=1):
                rows.append({
                    "pipeline_run_id": pipeline_run_id,
                    "location_id": key[0],
                    "product_id": key[1],
                    "forecast_date": start + timedelta(days=h),
                    "quantity": qty,
                    "method": f["method"],
                    "pattern": f["pattern"],
                })
        for i in range(0, len(rows), BATCH_SIZE):
            self.db.execute(insert(DemandForecast), rows[i:i + BATCH_SIZE])
        return len(rows)


class AlertRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        alert_type: str,
        message: str,
        severity: str = "WARNING",
        pipeline_run_id: Optional[str] = None,
        location_id: Optional[str] = None,
        product_id: Optional[str] = None,
    ) -> Alert:
        """Stages an alert; committed by the caller."""
        alert = Alert(
            pipeline_run_id=pipeline_run_id,
            location_id=location_id,
            product_id=product_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
        )
        self.db.add(alert)
        return alert

    def list_alerts(
        self,
        resolved: Optional[bool] = None,
        pipeline_run_id: Optional[str] = None,
        skip: int = 0,
        limit: Optional[int] = 100,
    ) -> List[Alert]:
        query = self.db.query(Alert)
        if resolved is not None:
            query = query.filter(Alert.resolved.is_(resolved))
        if pipeline_run_id:
            query = query.filter(Alert.pipeline_run_id == pipeline_run_id)
        query = query.order_by(Alert.created_at.desc(), Alert.id.desc())
        return query.offset(skip).limit(limit).all()

    def get_unresolved(self) -> List[Alert]:
        return self.list_alerts(resolved=False, limit=None)

    def count_unresolved(self) -> int:
        return self.db.query(Alert).filter(Alert.resolved.is_(False)).count()

    def resolve(self, alert_id: int) -> Optional[Alert]:
        alert = self.db.get(Alert, alert_id)
        if alert:
            alert.resolved = True
            self.db.commit()
            self.db.refresh(alert)
        return alert
