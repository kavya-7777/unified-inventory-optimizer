"""Pydantic schemas for pipeline runs and optimization results."""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class OptimizationRunRequest(BaseModel):
    run_type: str = "manual"
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    max_service_time: int = 30
    node_capacities: Optional[Dict[str, float]] = None


class NodeSchema(BaseModel):
    id: str
    type: str
    processing_time: int
    demand_mean: float = 0.0
    demand_std: float = 0.0
    holding_cost: float = 0.0
    max_s_out: int = 30
    min_s_out: int = 0
    service_level: float = 0.95

class EdgeSchema(BaseModel):
    source: str
    target: str
    transit_time: int
    cost_per_unit: float = 1.0
    capacity: Optional[float] = None

class ItemHistorySchema(BaseModel):
    id: str
    history: List[float]
    has_trend: bool = False

class PipelineRunRequest(BaseModel):
    run_type: str = "daily_batch"
    nodes: Optional[List[NodeSchema]] = None
    edges: Optional[List[EdgeSchema]] = None
    items_history: Optional[List[ItemHistorySchema]] = None
    horizon: int = 4
    max_service_time: int = 30
class NodeResult(BaseModel):
    s_in: int
    s_out: int
    net_replenishment_time: int
    safety_stock: float
    reorder_point: float


class OptimizationRunResponse(BaseModel):
    pipeline_run_id: str
    run_type: str
    status: str
    solver: str
    fallback_used: bool
    objective_value: Optional[float]
    solver_duration_seconds: float
    total_duration_seconds: float
    capacity_violations: List[str]
    node_results: Dict[str, NodeResult]


class PipelineRunOut(BaseModel):
    id: str
    run_type: str
    status: str
    solver: Optional[str]
    fallback_used: bool
    started_at: datetime
    finished_at: Optional[datetime]
    duration_seconds: Optional[float]
    error: Optional[str]

    model_config = {"from_attributes": True}


class ForecastRunRequest(BaseModel):
    items: List[Dict[str, Any]]
    horizon: int = 4


class AlertOut(BaseModel):
    id: int
    alert_type: str
    severity: str
    message: str
    resolved: bool
    created_at: datetime

    model_config = {"from_attributes": True}
