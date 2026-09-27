"""Service layer: aggregates several domains into the Dashboard 'control tower' summary."""
from sqlalchemy.orm import Session
from app.repositories.inventory import InventoryRepository, ProductRepository, PolicyRepository
from app.repositories.pipeline import OptimizationResultRepository, PipelineRunRepository, AlertRepository


def build_dashboard_summary(db: Session) -> dict:
    inventory_repo = InventoryRepository(db)
    product_repo = ProductRepository(db)
    policy_repo = PolicyRepository(db)
    result_repo = OptimizationResultRepository(db)
    run_repo = PipelineRunRepository(db)
    alert_repo = AlertRepository(db)

    # Inventory value = sum(latest on_hand * unit_cost) across all (location, product) pairs.
    snapshots = inventory_repo.get_all_latest_snapshots()
    unit_costs = {p.id: (p.unit_cost or 0.0) for p in product_repo.get_all(skip=0, limit=100_000)}
    inventory_value = sum(s.on_hand * unit_costs.get(s.product_id, 0.0) for s in snapshots)

    # Fill rate / at-risk = compare latest on-hand to latest safety stock, per pair,
    # only where we actually have both a snapshot and an optimization result.
    snapshot_by_pair = {(s.location_id, s.product_id): s for s in snapshots}
    results = result_repo.get_all_latest()
    measured_pairs = 0
    above_safety = 0
    for r in results:
        snap = snapshot_by_pair.get((r.location_id, r.product_id))
        if snap is None or r.safety_stock is None:
            continue
        measured_pairs += 1
        if snap.on_hand >= r.safety_stock:
            above_safety += 1
    at_risk_count = measured_pairs - above_safety
    fill_rate = (above_safety / measured_pairs) if measured_pairs > 0 else None

    total_policies = policy_repo.count()
    avg_service_level = policy_repo.avg_service_level()

    open_alerts = len(alert_repo.get_unresolved())

    recent_runs = run_repo.get_recent(limit=1)
    last_run = None
    if recent_runs:
        run = recent_runs[0]
        last_run = {
            "id": run.id,
            "status": run.status,
            "solver": run.solver,
            "fallback_used": bool(run.fallback_used),
            "started_at": run.started_at,
        }

    return {
        "inventory_value": round(inventory_value, 2),
        "avg_service_level": avg_service_level,
        "total_policies": total_policies,
        "fill_rate": fill_rate,
        "at_risk_count": at_risk_count,
        "measured_pairs": measured_pairs,
        "open_alerts": open_alerts,
        "last_run": last_run,
    }
