"""convert daily_bars to timescaledb hypertable

Revision ID: 20260529_0004
Revises: 20260528_0003
Create Date: 2026-05-29 11:45:00
"""

from alembic import op

revision = "20260529_0004"
down_revision = "20260528_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    # TimescaleDB requires the partitioning column (trade_date) to be part of
    # every UNIQUE constraint, including the primary key. The original schema
    # had id-only PK; promote to composite (id, trade_date).
    op.execute("ALTER TABLE daily_bars DROP CONSTRAINT IF EXISTS daily_bars_pkey;")
    op.execute("ALTER TABLE daily_bars ADD PRIMARY KEY (id, trade_date);")
    op.execute(
        "SELECT create_hypertable('daily_bars', 'trade_date', "
        "if_not_exists => TRUE, migrate_data => TRUE);"
    )


def downgrade() -> None:
    # Hypertable conversion is not safely reversible: TimescaleDB does not
    # provide an in-place "demote to regular table" operation, and rolling
    # back would require recreating the table and copying data, risking
    # loss of chunked partitions. Intentionally a no-op.
    pass
