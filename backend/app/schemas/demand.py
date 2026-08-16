"""Schemas for Demand History Ingestion and Retrieval."""
from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field


class DemandRecord(BaseModel):
    location_id: str
    product_id: str
    date: date
    quantity: float = Field(ge=0.0, description="Demand quantity cannot be negative")


class DemandIngestRequest(BaseModel):
    records: List[DemandRecord]


class DemandIngestResponse(BaseModel):
    inserted_count: int
    updated_count: int
    ignored_count: int
    errors: List[str]


class DemandHistoryOut(BaseModel):
    id: int
    location_id: str
    product_id: str
    date: date
    quantity: float

    model_config = {"from_attributes": True}
