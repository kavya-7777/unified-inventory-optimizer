"""Schemas for Demand History Ingestion and Retrieval."""
from datetime import date, datetime
from typing import Dict, List, Optional

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


class SeriesPoint(BaseModel):
    date: date
    quantity: float


class ForecastPoint(BaseModel):
    date: date
    forecast: float
    lower: float
    upper: float


class BacktestPoint(BaseModel):
    date: date
    actual: float
    forecast: float


class ModelScore(BaseModel):
    method: str
    params: Dict[str, float]
    mae: Optional[float] = None
    rmse: Optional[float] = None
    mape: Optional[float] = None
    mase: Optional[float] = None
    bias: Optional[float] = None
    selected: bool


class ForecastMetrics(BaseModel):
    mae: Optional[float] = None
    rmse: Optional[float] = None
    mape: Optional[float] = None
    mase: Optional[float] = None
    bias: Optional[float] = None


class DemandForecastOut(BaseModel):
    location_id: str
    product_id: str
    pattern: str
    adi: Optional[float]
    cv2: Optional[float]
    mean: float
    std: float
    zero_share: float
    method: str
    params: Dict[str, float]
    metrics: Optional[ForecastMetrics]
    demand_mean: float
    demand_std: float
    leaderboard: List[ModelScore]
    history: List[SeriesPoint]
    backtest: List[BacktestPoint]
    forecast: List[ForecastPoint]
