"""Pydantic schemas for pipeline runs and optimization results."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class NodeSchema(BaseModel):
    id: str = Field(min_length=1)
    type: str
    processing_time: int = Field(ge=0)
    demand_mean: float = Field(default=0.0, ge=0)
    demand_std: float = Field(default=0.0, ge=0)
    holding_cost: float = Field(default=0.0, ge=0)
    ordering_cost: float = Field(default=0.0, ge=0)
    max_s_out: int = Field(default=30, ge=0)
    min_s_out: int = Field(default=0, ge=0)
    service_level: float = Field(default=0.95, gt=0, lt=1)
    location_id: Optional[str] = None
    product_id: Optional[str] = None

    @model_validator(mode="after")
    def check_service_bounds(self) -> "NodeSchema":
        if self.min_s_out > self.max_s_out:
            raise ValueError("min_s_out must not exceed max_s_out")
        return self


class EdgeSchema(BaseModel):
    source: str
    target: str
    transit_time: int = Field(ge=0)
    cost_per_unit: float = Field(default=1.0, ge=0)
    capacity: Optional[float] = Field(default=None, gt=0)


class ItemHistorySchema(BaseModel):
    id: str
    history: List[float] = Field(default_factory=list)
    has_trend: bool = False


class OptimizationRunRequest(BaseModel):
    run_type: str = "manual"
    nodes: Optional[List[NodeSchema]] = None
    edges: Optional[List[EdgeSchema]] = None
    max_service_time: int = Field(default=30, ge=0, le=365)
    node_capacities: Optional[Dict[str, float]] = None


class PipelineRunRequest(OptimizationRunRequest):
    run_type: str = "daily_batch"
    items_history: Optional[List[ItemHistorySchema]] = None
    horizon: int = Field(default=4, ge=1, le=365)


class ForecastRunRequest(BaseModel):
    items: List[ItemHistorySchema]
    horizon: int = Field(default=4, ge=1, le=365)


class NodeResult(BaseModel):
    s_in: int
    s_out: int
    net_replenishment_time: int
    safety_stock: float
    reorder_point: float
    order_quantity: float
    safety_stock_cost: float
    location_id: Optional[str] = None
    product_id: Optional[str] = None


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


class PipelineRunResponse(BaseModel):
    pipeline_run_id: str
    status: str
    stages: Dict[str, Dict[str, Any]]
    node_results: Dict[str, NodeResult]


class ForecastResult(BaseModel):
    id: str
    forecast: List[float]
    method: str
    pattern: str
    demand_std: float


class ForecastRunResponse(BaseModel):
    forecasts: List[ForecastResult]
    count: int


class PipelineRunOut(BaseModel):
    id: str
    run_type: str
    status: str
    solver: Optional[str]
    fallback_used: Optional[bool]
    started_at: datetime
    finished_at: Optional[datetime]
    duration_seconds: Optional[float]
    error: Optional[str]

    model_config = {"from_attributes": True}


class OptimizationResultOut(BaseModel):
    id: int
    pipeline_run_id: str
    location_id: Optional[str]
    product_id: Optional[str]
    s_in: Optional[int]
    s_out: Optional[int]
    net_replenishment_time: Optional[int]
    safety_stock: Optional[float]
    reorder_point: Optional[float]
    order_quantity: Optional[float]
    objective_value: Optional[float]

    model_config = {"from_attributes": True}


class AlertOut(BaseModel):
    id: int
    pipeline_run_id: Optional[str]
    location_id: Optional[str]
    product_id: Optional[str]
    alert_type: str
    severity: str
    message: str
    resolved: bool
    created_at: datetime

    model_config = {"from_attributes": True}
