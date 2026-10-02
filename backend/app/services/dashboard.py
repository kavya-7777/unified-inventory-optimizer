"""Aggregates several domains into the Dashboard 'control tower' summary."""
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.inventory import Product
from app.repositories.inventory import InventoryRepository, PolicyRepository
from app.repositories.pipeline import (
    AlertRepository,
    OptimizationResultRepository,
    PipelineRunRepository,
)


def build_dashboard_summary(db: Session) -> Dict[str, Any]:
    snapshots = InventoryRepository(db).get_all_latest_snapshots()
    unit_costs = {pid: cost or 0.0 for pid, cost in db.query(Product.id, Product.unit_cost)}
    inventory_value = sum((s.on_hand or 0.0) * unit_costs.get(s.product_id, 0.0) for s in snapshots)

    on_hand: Dict[Tuple[Optional[str], Optional[str]], float] = {
        (s.location_id, s.product_id): s.on_hand or 0.0 for s in snapshots
    }
    measured = above = 0
    for r in OptimizationResultRepository(db).get_all_latest():
        key = (r.location_id, r.product_id)
        if key not in on_hand or r.safety_stock is None:
            continue
        measured += 1
        if on_hand[key] >= r.safety_stock:
            above += 1

    policy_repo = PolicyRepository(db)
    run_repo = PipelineRunRepository(db)
    # The control tower reflects the database-driven network runs, not sandbox experiments.
    recent = (run_repo.get_recent(limit=1, run_types=["network", "scheduled"])
              or run_repo.get_recent(limit=1))
    last_run = None
    if recent:
        run = recent[0]
        last_run = {
            "id": run.id,
            "status": run.status,
            "solver": run.solver,
            "fallback_used": bool(run.fallback_used),
            "started_at": run.started_at,
        }

    return {
        "inventory_value": round(inventory_value, 2),
        "avg_service_level": policy_repo.avg_service_level(),
        "total_policies": policy_repo.count(),
        "fill_rate": above / measured if measured else None,
        "at_risk_count": measured - above,
        "measured_pairs": measured,
        "open_alerts": AlertRepository(db).count_unresolved(),
        "last_run": last_run,
    }
