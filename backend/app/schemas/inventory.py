"""Pydantic schemas for inventory domain (request/response contracts)."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


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
    """A transportation lane, denormalized with its endpoints' names/types
    for direct display (source_id/target_id alone aren't human-readable)."""
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
    """A location-product inventory policy, denormalized with location/product
    display fields for the Policies grid."""
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
    """PATCH body for a single policy row — every field optional (partial update)."""
    service_level: Optional[float] = None
    min_s_out: Optional[int] = None
    max_s_out: Optional[int] = None
    holding_cost: Optional[float] = None
    ordering_cost: Optional[float] = None
    review_period: Optional[int] = None
