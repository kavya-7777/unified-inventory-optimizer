"""
Phase 1 Database Models — Full Schema.
Covers: Locations, Products, Lanes, Demand History, Lead Times,
        Forecasts, Inventory, Pipeline Runs, Optimization Results, Alerts.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, Text,
    ForeignKey, UniqueConstraint, Index, JSON
)
from sqlalchemy.orm import relationship
from app.models.base import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.utcnow()


# ─────────────────────────────────────────────
# Core Master Data
# ─────────────────────────────────────────────

class Location(Base):
    __tablename__ = "locations"

    id          = Column(String, primary_key=True, default=_uuid)
    name        = Column(String, nullable=False)
    type        = Column(String, nullable=False)   # Supplier | DC | Store
    region      = Column(String)
    created_at  = Column(DateTime, default=_now)
    updated_at  = Column(DateTime, default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_locations_type", "type"),
    )


class Product(Base):
    __tablename__ = "products"

    id          = Column(String, primary_key=True, default=_uuid)
    name        = Column(String, nullable=False)
    sku         = Column(String, unique=True)
    category    = Column(String)
    unit_cost   = Column(Float, default=0.0)
    created_at  = Column(DateTime, default=_now)
    updated_at  = Column(DateTime, default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_products_sku", "sku"),
    )


class Lane(Base):
    """Represents a transportation lane between two locations."""
    __tablename__ = "lanes"

    id              = Column(String, primary_key=True, default=_uuid)
    source_id       = Column(String, ForeignKey("locations.id"), nullable=False)
    target_id       = Column(String, ForeignKey("locations.id"), nullable=False)
    transit_time    = Column(Integer, nullable=False)   # Days
    cost_per_unit   = Column(Float, default=0.0)
    created_at      = Column(DateTime, default=_now)

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
    __tablename__ = "location_product_policy"

    id                  = Column(String, primary_key=True, default=_uuid)
    location_id         = Column(String, ForeignKey("locations.id"), nullable=False)
    product_id          = Column(String, ForeignKey("products.id"), nullable=False)
    service_level       = Column(Float, default=0.95)
    max_s_out           = Column(Integer, default=30)   # GSM max outbound service time
    min_s_out           = Column(Integer, default=0)
    holding_cost        = Column(Float, default=1.0)
    ordering_cost       = Column(Float, default=50.0)
    review_period       = Column(Integer, default=1)    # Days
    created_at          = Column(DateTime, default=_now)
    updated_at          = Column(DateTime, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("location_id", "product_id", name="uq_policy_loc_prod"),
    )


# ─────────────────────────────────────────────
# Demand & Lead Time History
# ─────────────────────────────────────────────

class DemandHistory(Base):
    __tablename__ = "demand_history"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    location_id = Column(String, ForeignKey("locations.id"), nullable=False)
    product_id  = Column(String, ForeignKey("products.id"), nullable=False)
    date        = Column(DateTime, nullable=False)
    quantity    = Column(Float, nullable=False)
    created_at  = Column(DateTime, default=_now)

    __table_args__ = (
        UniqueConstraint("location_id", "product_id", "date", name="uq_demand_loc_prod_date"),
        Index("ix_demand_history_loc_prod", "location_id", "product_id"),
        Index("ix_demand_history_date", "date"),
    )


class LeadTimeObservation(Base):
    __tablename__ = "lead_time_observations"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    lane_id         = Column(String, ForeignKey("lanes.id"), nullable=False)
    product_id      = Column(String, ForeignKey("products.id"), nullable=False)
    order_date      = Column(DateTime, nullable=False)
    receipt_date    = Column(DateTime, nullable=False)
    planned_lt      = Column(Integer)   # Days planned
    actual_lt       = Column(Integer)   # Days actual
    created_at      = Column(DateTime, default=_now)

    __table_args__ = (
        Index("ix_lt_obs_lane", "lane_id"),
    )


# ─────────────────────────────────────────────
# Forecasting
# ─────────────────────────────────────────────

class DemandForecast(Base):
    __tablename__ = "demand_forecast"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id = Column(String, ForeignKey("pipeline_runs.id"), nullable=False)
    location_id     = Column(String, ForeignKey("locations.id"), nullable=False)
    product_id      = Column(String, ForeignKey("products.id"), nullable=False)
    forecast_date   = Column(DateTime, nullable=False)
    quantity        = Column(Float, nullable=False)
    method          = Column(String)    # SES | Holt-DES | Croston-SBA
    pattern         = Column(String)    # smooth | intermittent | lumpy | erratic
    created_at      = Column(DateTime, default=_now)

    __table_args__ = (
        Index("ix_forecast_run_loc_prod", "pipeline_run_id", "location_id", "product_id"),
    )


# ─────────────────────────────────────────────
# Inventory
# ─────────────────────────────────────────────

class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshot"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    location_id     = Column(String, ForeignKey("locations.id"), nullable=False)
    product_id      = Column(String, ForeignKey("products.id"), nullable=False)
    snapshot_date   = Column(DateTime, nullable=False, default=_now)
    on_hand         = Column(Float, default=0.0)
    on_order        = Column(Float, default=0.0)
    in_transit      = Column(Float, default=0.0)
    version         = Column(Integer, default=1)    # Optimistic locking

    __table_args__ = (
        UniqueConstraint("location_id", "product_id", "snapshot_date", name="uq_inv_snapshot"),
        Index("ix_inv_snapshot_loc_prod", "location_id", "product_id"),
    )


# ─────────────────────────────────────────────
# Pipeline Runs (Audit Trail)
# ─────────────────────────────────────────────

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id              = Column(String, primary_key=True, default=_uuid)
    run_type        = Column(String, nullable=False)    # manual | scheduled
    status          = Column(String, nullable=False)    # running | success | failed
    solver          = Column(String)                    # cp-sat | lp-fallback
    fallback_used   = Column(Boolean, default=False)
    started_at      = Column(DateTime, default=_now)
    finished_at     = Column(DateTime)
    duration_seconds= Column(Float)
    parameters      = Column(JSON)      # Input parameters snapshot
    error           = Column(Text)      # Error message if failed
    created_at      = Column(DateTime, default=_now)

    optimization_results = relationship("OptimizationResult", back_populates="run")
    forecasts            = relationship("DemandForecast", back_populates=None)

    __table_args__ = (
        Index("ix_pipeline_runs_status", "status"),
        Index("ix_pipeline_runs_started_at", "started_at"),
    )


# ─────────────────────────────────────────────
# Optimization Results
# ─────────────────────────────────────────────

class OptimizationResult(Base):
    __tablename__ = "optimization_results"

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id         = Column(String, ForeignKey("pipeline_runs.id"), nullable=False)
    location_id             = Column(String, ForeignKey("locations.id"), nullable=True)
    product_id              = Column(String, ForeignKey("products.id"), nullable=True)
    s_in                    = Column(Integer)       # GSM inbound service time
    s_out                   = Column(Integer)       # GSM outbound service time
    net_replenishment_time  = Column(Integer)       # T = s_in + p - s_out
    safety_stock            = Column(Float)
    reorder_point           = Column(Float)
    order_quantity          = Column(Float)         # EOQ
    objective_value         = Column(Float)         # Solver objective contribution
    created_at              = Column(DateTime, default=_now)

    run = relationship("PipelineRun", back_populates="optimization_results")

    __table_args__ = (
        Index("ix_opt_results_run", "pipeline_run_id"),
        Index("ix_opt_results_loc_prod", "location_id", "product_id"),
    )


# ─────────────────────────────────────────────
# Alerts
# ─────────────────────────────────────────────

class Alert(Base):
    __tablename__ = "alerts"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id = Column(String, ForeignKey("pipeline_runs.id"))
    location_id     = Column(String, ForeignKey("locations.id"))
    product_id      = Column(String, ForeignKey("products.id"))
    alert_type      = Column(String, nullable=False)    # CAPACITY_EXCEEDED | SOLVER_TIMEOUT | etc.
    severity        = Column(String, default="WARNING") # INFO | WARNING | CRITICAL
    message         = Column(Text, nullable=False)
    resolved        = Column(Boolean, default=False)
    created_at      = Column(DateTime, default=_now)

    __table_args__ = (
        Index("ix_alerts_unresolved", "resolved", "severity"),
    )
