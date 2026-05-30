"""create strategy_kpi_snapshots table

One-row-per-strategy cache populated daily by the
``strategies.compute_kpi_snapshots`` Celery beat task. The list endpoint
joins this cache against the static strategy catalog so the admin UI can
render KPI cards (annualized return, Sharpe, max drawdown, win rate,
equity sparkline) without re-running the walk-forward backtest on every
request.

Revision ID: 20260530_0007
Revises: 20260529_0006
Create Date: 2026-05-30 09:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20260530_0007"
down_revision = "20260529_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_kpi_snapshots",
        sa.Column("key", sa.String(length=50), primary_key=True),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("lookback_days", sa.Integer(), nullable=False),
        sa.Column("annualized_return_pct", sa.Float(), nullable=True),
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("max_drawdown_pct", sa.Float(), nullable=True),
        sa.Column("win_rate_pct", sa.Float(), nullable=True),
        sa.Column("total_return_pct", sa.Float(), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=False),
        sa.Column("equity_sparkline_json", sa.Text(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("strategy_kpi_snapshots")
