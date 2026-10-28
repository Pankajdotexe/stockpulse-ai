"""Create initial tables for Phase 1 data ingestion.

Revision ID: 001_initial_data_tables
Revises:
Create Date: 2026-10-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_data_tables"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Pipeline Runs table
    op.create_table(
        "pipeline_runs",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("pipeline_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_processed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_index("idx_pipeline_runs_pipeline_name", "pipeline_runs", ["pipeline_name"])
    op.create_index(
        "idx_pipeline_runs_started_at",
        "pipeline_runs",
        [sa.text("started_at DESC")],
    )

    # 2. Daily OHLCV table
    op.create_table(
        "ohlcv_daily",
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("high", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("low", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("close", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("adj_close", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("ticker", "date", name="pk_ohlcv_daily"),
        sa.CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0 AND adj_close > 0",
            name="chk_positive_prices",
        ),
        sa.CheckConstraint("high >= low", name="chk_high_low"),
        sa.CheckConstraint("volume >= 0", name="chk_positive_volume"),
    )
    op.create_index("idx_ohlcv_daily_ticker", "ohlcv_daily", ["ticker"])
    op.create_index(
        "idx_ohlcv_daily_date",
        "ohlcv_daily",
        [sa.text("date DESC")],
    )

    # 3. Data Quality Log table
    op.create_table(
        "data_quality_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.run_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("check_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "check_timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_data_quality_log_ticker", "data_quality_log", ["ticker"])
    op.create_index(
        "idx_data_quality_log_check_timestamp",
        "data_quality_log",
        [sa.text("check_timestamp DESC")],
    )


def downgrade() -> None:
    op.drop_table("data_quality_log")
    op.drop_table("ohlcv_daily")
    op.drop_table("pipeline_runs")
