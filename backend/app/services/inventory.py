"""Inventory positions: current stock compared with the latest optimized targets."""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.inventory import Location, Product
from app.repositories.inventory import InventoryRepository
from app.repositories.pipeline import OptimizationResultRepository

STATUS_ORDER = {"STOCKOUT_RISK": 0, "REORDER": 1, "EXCESS": 2, "HEALTHY": 3, "NO_PLAN": 4}


def classify_position(
    on_hand: float, position: float, safety_stock: Optional[float],
    reorder_point: Optional[float], order_quantity: Optional[float],
) -> str:
    """
    (s, Q) policy view: reorder when the inventory position falls to the reorder point s;
    the most stock you should normally hold is s + Q.
    """
    if safety_stock is None or reorder_point is None:
        return "NO_PLAN"
    if on_hand < safety_stock:
        return "STOCKOUT_RISK"
    if position <= reorder_point:
        return "REORDER"
    if order_quantity and on_hand > reorder_point + order_quantity:
        return "EXCESS"
    return "HEALTHY"


def list_positions(
    db: Session,
    location_type: Optional[str] = None,
    location_id: Optional[str] = None,
    product_id: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Dict[str, Any]:
    locations = {loc.id: loc for loc in db.query(Location)}
    products = {p.id: p for p in db.query(Product)}
    targets = {(r.location_id, r.product_id): r
               for r in OptimizationResultRepository(db).get_all_latest()}
    needle = (q or "").strip().lower()

    rows: List[Dict[str, Any]] = []
    for snap in InventoryRepository(db).get_all_latest_snapshots():
        loc = locations.get(snap.location_id)
        prod = products.get(snap.product_id)
        if loc is None or prod is None:
            continue
        if location_type and loc.type != location_type:
            continue
        if location_id and loc.id != location_id:
            continue
        if product_id and prod.id != product_id:
            continue
        if needle and not any(needle in (v or "").lower()
                              for v in (loc.name, prod.name, prod.sku, prod.category)):
            continue

        target = targets.get((snap.location_id, snap.product_id))
        on_hand = snap.on_hand or 0.0
        position = on_hand + (snap.on_order or 0.0) + (snap.in_transit or 0.0)
        ss = target.safety_stock if target else None
        rop = target.reorder_point if target else None
        eoq = target.order_quantity if target else None
        daily = target.demand_mean if target else None
        row_status = classify_position(on_hand, position, ss, rop, eoq)
        if status and row_status != status:
            continue

        recommended = 0.0
        if row_status in ("STOCKOUT_RISK", "REORDER") and rop is not None:
            recommended = max(eoq or 0.0, rop + (eoq or 0.0) - position)
        rows.append({
            "location_id": loc.id,
            "location_name": loc.name,
            "location_type": loc.type,
            "region": loc.region,
            "product_id": prod.id,
            "product_name": prod.name,
            "sku": prod.sku,
            "category": prod.category,
            "unit_cost": prod.unit_cost or 0.0,
            "on_hand": on_hand,
            "on_order": snap.on_order or 0.0,
            "in_transit": snap.in_transit or 0.0,
            "inventory_position": position,
            "safety_stock": ss,
            "reorder_point": rop,
            "order_quantity": eoq,
            "daily_demand": daily,
            "days_of_cover": round(on_hand / daily, 1) if daily else None,
            "recommended_order": round(recommended),
            "status": row_status,
            "snapshot_date": snap.snapshot_date,
        })

    counts: Dict[str, int] = {s: 0 for s in STATUS_ORDER}
    for row in rows:
        counts[row["status"]] += 1
    rows.sort(key=lambda r: (STATUS_ORDER[r["status"]], r["location_type"] != "Store",
                             r["location_name"], r["product_name"]))
    return {"total": len(rows), "counts": counts, "items": rows[skip:skip + limit]}
