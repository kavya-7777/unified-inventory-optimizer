"""
Database Models.
Covers: Locations, Products, Lanes, Demand History, Lead Times,
        Forecasts, Inventory, Pipeline Runs, Optimization Results, Alerts.
"""
import uuid
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import JSON, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow


def _uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────
# Core Master Data
# ─────────────────────────────────────────────

class Location(Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=_uuid)
    name: Mapped[str]
    type: Mapped[str]                                   # Supplier | DC | Store
    region: Mapped[Optional[str]]
    created_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("ix_locations_type", "type"),
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=_uuid)
    name: Mapped[str]
    sku: Mapped[Optional[str]] = mapped_column(unique=True)
    category: Mapped[Optional[str]]
    unit_cost: Mapped[Optional[float]] = mapped_column(default=0.0)
    created_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("ix_products_sku", "sku"),
    )


class Lane(Base):
    """Represents a transportation lane between two locations."""
    __tablename__ = "lanes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    target_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    transit_time: Mapped[int]                           # Days
    cost_per_unit: Mapped[Optional[float]] = mapped_column(default=0.0)
    capacity: Mapped[Optional[float]]                   # Max units/period; null = unconstrained
    created_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow)

    __table_args__ = (
        UniqueConstraint("source_id", "target_id", name="uq_lane_src_tgt"),
        Index("ix_lanes_source", "source_id"),
        Index("ix_lanes_target", "target_id"),
    )


# ─────────────────────────────────────────────
# Policy & Configuration
# ─────────────────────────────────────────────

class LocationProductPolicy(Base):
    """Per-SKU-per-Location inventory policy settings."""
    __tablename__ = "location_product_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    service_level: Mapped[Optional[float]] = mapped_column(default=0.95)
    max_s_out: Mapped[Optional[int]] = mapped_column(default=30)
    min_s_out: Mapped[Optional[int]] = mapped_column(default=0)
    holding_cost: Mapped[Optional[float]] = mapped_column(default=1.0)
    ordering_cost: Mapped[Optional[float]] = mapped_column(default=50.0)
    review_period: Mapped[Optional[int]] = mapped_column(default=1)   # Days
    processing_time: Mapped[Optional[int]] = mapped_column(default=1, server_default="1")
    created_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("location_id", "product_id", name="uq_policy_loc_prod"),
    )


# ─────────────────────────────────────────────
# Demand & Lead Time History
# ─────────────────────────────────────────────

class DemandHistory(Base):
    __tablename__ = "demand_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    date: Mapped[datetime]
    quantity: Mapped[float]
    created_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow)

    __table_args__ = (
        UniqueConstraint("location_id", "product_id", "date", name="uq_demand_loc_prod_date"),
        Index("ix_demand_history_loc_prod", "location_id", "product_id"),
        Index("ix_demand_history_date", "date"),
    )


class LeadTimeObservation(Base):
    __tablename__ = "lead_time_observations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lane_id: Mapped[str] = mapped_column(ForeignKey("lanes.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    order_date: Mapped[datetime]
    receipt_date: Mapped[datetime]
    planned_lt: Mapped[Optional[int]]                   # Days planned
    actual_lt: Mapped[Optional[int]]                    # Days actual
    created_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow)

    __table_args__ = (
        Index("ix_lt_obs_lane", "lane_id"),
    )


# ─────────────────────────────────────────────
# Forecasting
# ─────────────────────────────────────────────

class DemandForecast(Base):
    __tablename__ = "demand_forecasts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pipeline_run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id"))
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    forecast_date: Mapped[datetime]
    quantity: Mapped[float]
    lower_bound: Mapped[Optional[float]]                # 95% prediction interval
    upper_bound: Mapped[Optional[float]]
    method: Mapped[Optional[str]]                       # selected forecasting model
    pattern: Mapped[Optional[str]]                      # smooth | intermittent | lumpy | erratic
    created_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow)

    __table_args__ = (
        Index("ix_forecast_run_loc_prod", "pipeline_run_id", "location_id", "product_id"),
    )


# ─────────────────────────────────────────────
# Inventory
# ─────────────────────────────────────────────

class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    snapshot_date: Mapped[datetime] = mapped_column(default=utcnow)
    on_hand: Mapped[Optional[float]] = mapped_column(default=0.0)
    on_order: Mapped[Optional[float]] = mapped_column(default=0.0)
    in_transit: Mapped[Optional[float]] = mapped_column(default=0.0)
    version: Mapped[Optional[int]] = mapped_column(default=1)

    __table_args__ = (
        UniqueConstraint("location_id", "product_id", "snapshot_date", name="uq_inv_snapshot"),
        Index("ix_inv_snapshot_loc_prod", "location_id", "product_id"),
    )


# ─────────────────────────────────────────────
# Pipeline Runs (Audit Trail)
# ─────────────────────────────────────────────

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    run_type: Mapped[str]                               # manual | scheduled | daily_batch
    status: Mapped[str]                                 # running | success | failed
    solver: Mapped[Optional[str]]                       # cp-sat | heuristic
    fallback_used: Mapped[Optional[bool]] = mapped_column(default=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow)
    finished_at: Mapped[Optional[datetime]]
    duration_seconds: Mapped[Optional[float]]
    parameters: Mapped[Optional[Any]] = mapped_column(JSON)
    error: Mapped[Optional[str]] = mapped_column(Text)
    summary: Mapped[Optional[Any]] = mapped_column(JSON)
    triggered_by: Mapped[Optional[str]] = mapped_column(String(255))  # user email or "system"
    created_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow)

    optimization_results: Mapped[List["OptimizationResult"]] = relationship(
        back_populates="run"
    )
    forecasts: Mapped[List["DemandForecast"]] = relationship(
        foreign_keys="DemandForecast.pipeline_run_id"
    )

    __table_args__ = (
        Index("ix_pipeline_runs_status", "status"),
        Index("ix_pipeline_runs_started_at", "started_at"),
    )


# ─────────────────────────────────────────────
# Optimization Results
# ─────────────────────────────────────────────

class OptimizationResult(Base):
    __tablename__ = "optimization_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pipeline_run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id"))
    location_id: Mapped[Optional[str]] = mapped_column(ForeignKey("locations.id"))
    product_id: Mapped[Optional[str]] = mapped_column(ForeignKey("products.id"))
    s_in: Mapped[Optional[int]]
    s_out: Mapped[Optional[int]]
    net_replenishment_time: Mapped[Optional[int]]       # T = s_in + p - s_out
    safety_stock: Mapped[Optional[float]]
    reorder_point: Mapped[Optional[float]]
    order_quantity: Mapped[Optional[float]]             # EOQ
    demand_mean: Mapped[Optional[float]]                # Daily demand used by the solver
    demand_std: Mapped[Optional[float]]
    service_level: Mapped[Optional[float]]
    objective_value: Mapped[Optional[float]]            # Safety stock holding cost
    created_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow)

    run: Mapped["PipelineRun"] = relationship(back_populates="optimization_results")

    __table_args__ = (
        Index("ix_opt_results_run", "pipeline_run_id"),
        Index("ix_opt_results_loc_prod", "location_id", "product_id"),
    )


# ─────────────────────────────────────────────
# Alerts
# ─────────────────────────────────────────────

class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pipeline_run_id: Mapped[Optional[str]] = mapped_column(ForeignKey("pipeline_runs.id"))
    location_id: Mapped[Optional[str]] = mapped_column(ForeignKey("locations.id"))
    product_id: Mapped[Optional[str]] = mapped_column(ForeignKey("products.id"))
    alert_type: Mapped[str]                 # CAPACITY_EXCEEDED | SOLVER_FALLBACK | ...
    severity: Mapped[Optional[str]] = mapped_column(default="WARNING")
    message: Mapped[str] = mapped_column(Text)
    resolved: Mapped[Optional[bool]] = mapped_column(default=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow)

    __table_args__ = (
        Index("ix_alerts_unresolved", "resolved", "severity"),
    )
