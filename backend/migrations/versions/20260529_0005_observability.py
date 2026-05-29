"""create observability tables: sync_runs and bot_command_logs

Revision ID: 20260529_0005
Revises: 20260529_0004
Create Date: 2026-05-29 14:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20260529_0005"
down_revision = "20260529_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("job_name", sa.String(length=50), nullable=False),
        sa.Column("target", sa.String(length=50), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="running",
        ),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("synced_count", sa.Integer(), nullable=True),
        sa.Column("error", sa.String(length=1000), nullable=True),
        sa.Column("meta_json", sa.Text(), nullable=True),
    )
    op.create_index("ix_sync_runs_job_name", "sync_runs", ["job_name"])
    op.create_index("ix_sync_runs_status", "sync_runs", ["status"])

    op.create_table(
        "bot_command_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("chat_id", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=True),
        sa.Column("command", sa.String(length=50), nullable=False),
        sa.Column("args_text", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.String(length=1000), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_bot_command_logs_created_at", "bot_command_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_bot_command_logs_created_at", table_name="bot_command_logs")
    op.drop_table("bot_command_logs")

    op.drop_index("ix_sync_runs_status", table_name="sync_runs")
    op.drop_index("ix_sync_runs_job_name", table_name="sync_runs")
    op.drop_table("sync_runs")
