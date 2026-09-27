"""Pydantic schemas for the Transportation plan endpoint."""
from typing import List, Optional
from pydantic import BaseModel


class LaneFlowOut(BaseModel):
    lane_id: str
    source_id: str
    source_name: str
    source_type: str
    target_id: str
    target_name: str
    target_type: str
    product_id: str
    sku: Optional[str] = None
    product_name: str
    quantity: float
    capacity: Optional[float] = None
    utilization: Optional[float] = None
    transit_time: Optional[int] = None
    cost: float


class TransportationPlanOut(BaseModel):
    status: str  # "OPTIMAL" | "INFEASIBLE" | "NO_EDGES" | "NO_DEMAND_DATA"
    message: Optional[str] = None
    planned_units: float = 0.0
    total_cost: float = 0.0
    capacity_utilization: Optional[float] = None
    active_lanes: int = 0
    lane_flows: List[LaneFlowOut] = []
