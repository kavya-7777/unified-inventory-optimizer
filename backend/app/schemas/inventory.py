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
