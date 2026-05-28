"""add watchlist refresh fields

Revision ID: 20260528_0002
Revises: 20260527_0001
Create Date: 2026-05-28 11:20:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20260528_0002"
down_revision = "20260527_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("watchlists", sa.Column("screen_params_json", sa.Text(), nullable=True))
    op.add_column(
        "watchlists",
        sa.Column("auto_refresh", sa.String(length=10), nullable=False, server_default="manual"),
    )
    op.alter_column("watchlists", "auto_refresh", server_default=None)


def downgrade() -> None:
    op.drop_column("watchlists", "auto_refresh")
    op.drop_column("watchlists", "screen_params_json")
