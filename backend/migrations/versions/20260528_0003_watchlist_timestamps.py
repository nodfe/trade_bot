"""add watchlist timestamps

Revision ID: 20260528_0003
Revises: 20260528_0002
Create Date: 2026-05-28 16:10:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20260528_0003"
down_revision = "20260528_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "watchlists",
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.add_column("watchlists", sa.Column("last_refreshed_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE watchlists SET updated_at = created_at")
    op.alter_column("watchlists", "updated_at", server_default=None)


def downgrade() -> None:
    op.drop_column("watchlists", "last_refreshed_at")
    op.drop_column("watchlists", "updated_at")
