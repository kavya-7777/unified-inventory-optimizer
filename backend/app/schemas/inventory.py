"""Pydantic schemas for inventory domain (request/response contracts)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LocationOut(BaseModel):
    id: str
    name: str
    type: str
    region: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProductOut(BaseModel):
    id: str
    name: str
    sku: Optional[str] = None
    category: Optional[str] = None
    unit_cost: Optional[float] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InventorySnapshotOut(BaseModel):
    id: int
    location_id: str
    product_id: str
    snapshot_date: datetime
    on_hand: float
    on_order: float
    in_transit: float
    version: int

    model_config = {"from_attributes": True}


class LaneOut(BaseModel):
    id: str
    source_id: str
    source_name: str
    source_type: str
    source_region: Optional[str] = None
    target_id: str
    target_name: str
    target_type: str
    target_region: Optional[str] = None
    transit_time: int
    cost_per_unit: float
    capacity: Optional[float] = None
    created_at: Optional[datetime] = None


class PolicyOut(BaseModel):
    id: str
    location_id: str
    location_name: str
    location_type: str
    product_id: str
    product_name: str
    product_sku: Optional[str] = None
    service_level: float
    min_s_out: int
    max_s_out: int
    holding_cost: float
    ordering_cost: float
    review_period: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PolicyUpdate(BaseModel):
    """Partial update; omitted fields are left unchanged."""
    service_level: Optional[float] = Field(default=None, gt=0, lt=1)
    min_s_out: Optional[int] = Field(default=None, ge=0)
    max_s_out: Optional[int] = Field(default=None, ge=0)
    holding_cost: Optional[float] = Field(default=None, ge=0)
    ordering_cost: Optional[float] = Field(default=None, ge=0)
    review_period: Optional[int] = Field(default=None, ge=1)
