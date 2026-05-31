"""create strategy_subscriptions table

One row per user-level strategy signal subscription. The
``strategies.dispatch_subscriptions`` Celery beat task scans this table
every 5 minutes and pushes a card to the configured bot channel for any
subscription whose cron schedule is due.

Revision ID: 20260530_0008
Revises: 20260530_0007
Create Date: 2026-05-30 12:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20260530_0008"
down_revision = "20260530_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_subscriptions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("strategy_key", sa.String(length=80), nullable=False),
        sa.Column("params_json", sa.Text(), nullable=True),
        sa.Column("bot_channel_id", sa.String(length=128), nullable=False),
        sa.Column(
            "schedule",
            sa.String(length=64),
            nullable=False,
            server_default="0 30 9 * * 1",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("last_dispatched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_strategy_subscriptions_user_id",
        "strategy_subscriptions",
        ["user_id"],
    )
    op.create_index(
        "ix_strategy_subscriptions_strategy_key",
        "strategy_subscriptions",
        ["strategy_key"],
    )
    op.create_index(
        "ix_strategy_subscriptions_user_strategy",
        "strategy_subscriptions",
        ["user_id", "strategy_key"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_strategy_subscriptions_user_strategy",
        table_name="strategy_subscriptions",
    )
    op.drop_index(
        "ix_strategy_subscriptions_strategy_key",
        table_name="strategy_subscriptions",
    )
    op.drop_index(
        "ix_strategy_subscriptions_user_id",
        table_name="strategy_subscriptions",
    )
    op.drop_table("strategy_subscriptions")
