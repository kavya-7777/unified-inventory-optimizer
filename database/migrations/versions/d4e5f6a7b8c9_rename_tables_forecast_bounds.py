"""rename_tables_forecast_bounds

Consistent plural table names, plus columns used by the database-driven pipeline:
policy processing time, forecast prediction intervals, per-result demand inputs and
a run summary.

Revision ID: d4e5f6a7b8c9
Revises: c1a2e3f4b5d6
Create Date: 2026-10-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c1a2e3f4b5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RENAMES = [
    ("inventory_snapshot", "inventory_snapshots", ["location_id", "product_id"], True),
    ("demand_forecast", "demand_forecasts", ["pipeline_run_id", "location_id", "product_id"], True),
    ("location_product_policy", "location_product_policies", ["location_id", "product_id"], False),
]


def _rename(old: str, new: str, fk_columns: list, has_sequence: bool) -> None:
    op.rename_table(old, new)
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f"ALTER TABLE {new} RENAME CONSTRAINT {old}_pkey TO {new}_pkey")
    for col in fk_columns:
        op.execute(f"ALTER TABLE {new} RENAME CONSTRAINT {old}_{col}_fkey TO {new}_{col}_fkey")
    if has_sequence:
        op.execute(f"ALTER SEQUENCE {old}_id_seq RENAME TO {new}_id_seq")


def upgrade() -> None:
    for old, new, fks, seq in RENAMES:
        _rename(old, new, fks, seq)

    op.add_column(
        "location_product_policies",
        sa.Column("processing_time", sa.Integer(), nullable=True, server_default="1"),
    )
    op.add_column("demand_forecasts", sa.Column("lower_bound", sa.Float(), nullable=True))
    op.add_column("demand_forecasts", sa.Column("upper_bound", sa.Float(), nullable=True))
    op.add_column("optimization_results", sa.Column("demand_mean", sa.Float(), nullable=True))
    op.add_column("optimization_results", sa.Column("demand_std", sa.Float(), nullable=True))
    op.add_column("optimization_results", sa.Column("service_level", sa.Float(), nullable=True))
    op.add_column("pipeline_runs", sa.Column("summary", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("pipeline_runs", "summary")
    op.drop_column("optimization_results", "service_level")
    op.drop_column("optimization_results", "demand_std")
    op.drop_column("optimization_results", "demand_mean")
    op.drop_column("demand_forecasts", "upper_bound")
    op.drop_column("demand_forecasts", "lower_bound")
    op.drop_column("location_product_policies", "processing_time")
    for old, new, fks, seq in reversed(RENAMES):
        _rename(new, old, fks, seq)
