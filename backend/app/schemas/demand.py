"""Schemas for Demand History Ingestion and Retrieval."""
from datetime import date, datetime
from typing import List

from pydantic import BaseModel, Field, field_validator


class DemandRecord(BaseModel):
    location_id: str
    product_id: str
    date: date
    quantity: float = Field(ge=0.0, description="Demand quantity cannot be negative")


class DemandIngestRequest(BaseModel):
    records: List[DemandRecord] = Field(max_length=100_000)


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

    @field_validator("date", mode="before")
    @classmethod
    def strip_time(cls, v):
        return v.date() if isinstance(v, datetime) else v
