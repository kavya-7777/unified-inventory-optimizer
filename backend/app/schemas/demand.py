"""Schemas for Demand History Ingestion and Retrieval."""
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


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

    @field_validator("date", mode="before")
    @classmethod
    def _coerce_datetime_to_date(cls, value):
        # DemandHistory.date is a DB DateTime column; the normal ingest path always
        # writes midnight so this is a no-op there, but any row written with a
        # real time-of-day (a bulk import, a fixture, a manual insert) would
        # otherwise fail Pydantic's strict date validation for the WHOLE response
        # list, not just that row. Truncate defensively instead.
        if isinstance(value, datetime):
            return value.date()
        return value
