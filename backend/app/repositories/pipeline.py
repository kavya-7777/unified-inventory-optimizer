"""Repository: Data access layer for pipeline runs and optimization results."""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.inventory import PipelineRun, OptimizationResult, Alert


class PipelineRunRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, run_id: str, run_type: str, parameters: dict) -> PipelineRun:
        run = PipelineRun(
            id=run_id,
            run_type=run_type,
            status="running",
            parameters=parameters,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def complete(self, run_id: str, status: str, solver: str, fallback_used: bool, duration: float) -> None:
        run = self.db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if run:
            run.status = status
            run.solver = solver
            run.fallback_used = fallback_used
            run.finished_at = datetime.utcnow()
            run.duration_seconds = duration
            self.db.commit()

    def fail(self, run_id: str, error: str) -> None:
        run = self.db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if run:
            run.status = "failed"
            run.error = error
            run.finished_at = datetime.utcnow()
            self.db.commit()

    def get_recent(self, limit: int = 10) -> List[PipelineRun]:
        return (
            self.db.query(PipelineRun)
            .order_by(PipelineRun.started_at.desc())
            .limit(limit)
            .all()
        )

    def get_by_id(self, run_id: str) -> Optional[PipelineRun]:
        return self.db.query(PipelineRun).filter(PipelineRun.id == run_id).first()


class OptimizationResultRepository:
    def __init__(self, db: Session):
        self.db = db

    def bulk_save(self, pipeline_run_id: str, node_results: dict, location_product_map: dict) -> None:
        """
        Persist solver output per node. 
        location_product_map maps node_id → (location_id, product_id).
        """
        records = []
        for node_id, result in node_results.items():
            loc_id, prod_id = location_product_map.get(node_id, (node_id, None))
            record = OptimizationResult(
                pipeline_run_id=pipeline_run_id,
                location_id=loc_id,
                product_id=prod_id,
                s_in=result.get("s_in"),
                s_out=result.get("s_out"),
                net_replenishment_time=result.get("net_replenishment_time"),
                safety_stock=result.get("safety_stock"),
                reorder_point=result.get("reorder_point"),
            )
            records.append(record)
        self.db.add_all(records)
        self.db.commit()


class AlertRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, alert_type: str, message: str, severity: str = "WARNING",
               pipeline_run_id: str = None, location_id: str = None, product_id: str = None) -> Alert:
        alert = Alert(
            pipeline_run_id=pipeline_run_id,
            location_id=location_id,
            product_id=product_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
        )
        self.db.add(alert)
        self.db.commit()
        return alert

    def get_unresolved(self) -> List[Alert]:
        return self.db.query(Alert).filter(Alert.resolved == False).all()
