"""extend strategy KPI snapshots and add user_strategies

Revision ID: 20260530_0009
Revises: 20260530_0008
Create Date: 2026-05-30 12:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20260530_0009"
down_revision = "20260530_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen the snapshot key column so "custom:{uuid}" entries fit (uuid4 is
    # 36 chars + 7 chars prefix = 43, plus headroom).
    op.alter_column(
        "strategy_kpi_snapshots",
        "key",
        existing_type=sa.String(length=50),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.add_column(
        "strategy_kpi_snapshots",
        sa.Column("sortino_ratio", sa.Float(), nullable=True),
    )
    op.add_column(
        "strategy_kpi_snapshots",
        sa.Column("calmar_ratio", sa.Float(), nullable=True),
    )
    op.add_column(
        "strategy_kpi_snapshots",
        sa.Column("turnover_pct", sa.Float(), nullable=True),
    )
    op.add_column(
        "strategy_kpi_snapshots",
        sa.Column("monthly_returns_json", sa.Text(), nullable=True),
    )
    op.add_column(
        "strategy_kpi_snapshots",
        sa.Column("benchmark_equity_sparkline_json", sa.Text(), nullable=True),
    )
    op.add_column(
        "strategy_kpi_snapshots",
        sa.Column("alpha_pct", sa.Float(), nullable=True),
    )

    op.create_table(
        "user_strategies",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_template", sa.String(length=50), nullable=False),
        sa.Column("params_json", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_user_strategies_owner", "user_strategies", ["owner"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_strategies_owner", table_name="user_strategies")
    op.drop_table("user_strategies")
    op.drop_column("strategy_kpi_snapshots", "alpha_pct")
    op.drop_column("strategy_kpi_snapshots", "benchmark_equity_sparkline_json")
    op.drop_column("strategy_kpi_snapshots", "monthly_returns_json")
    op.drop_column("strategy_kpi_snapshots", "turnover_pct")
    op.drop_column("strategy_kpi_snapshots", "calmar_ratio")
    op.drop_column("strategy_kpi_snapshots", "sortino_ratio")
    op.alter_column(
        "strategy_kpi_snapshots",
        "key",
        existing_type=sa.String(length=64),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
