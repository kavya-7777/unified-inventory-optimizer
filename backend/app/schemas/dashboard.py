"""Schemas for the Dashboard 'control tower' summary."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LastRunOut(BaseModel):
    id: str
    status: str
    solver: Optional[str] = None
    fallback_used: bool
    started_at: datetime


class DashboardSummaryOut(BaseModel):
    inventory_value: float               # sum(on_hand * unit_cost) over latest snapshots
    avg_service_level: Optional[float]   # avg policy service level (0-1)
    total_policies: int
    fill_rate: Optional[float]           # share of measured pairs with on_hand >= safety_stock
    at_risk_count: int                   # measured pairs with on_hand < safety_stock
    measured_pairs: int                  # pairs with both a snapshot and an optimization result
    open_alerts: int
    last_run: Optional[LastRunOut] = None
