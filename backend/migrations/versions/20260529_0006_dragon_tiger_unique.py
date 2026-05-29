"""widen dragon_tiger unique key to include reason

Same stock can appear on the dragon-tiger list multiple times on the same
trade_date when triggered by different rules (e.g. "日涨幅偏离7%" and
"连续3日涨幅12%"). The original (trade_date, code) unique index rejected the
2nd row. Widening to (trade_date, code, reason) lets all distinct rules land,
while still preventing exact duplicates.

Revision ID: 20260529_0006
Revises: 20260529_0005
Create Date: 2026-05-29 17:45:00
"""

from alembic import op

revision = "20260529_0006"
down_revision = "20260529_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_lhb_date_code", table_name="dragon_tiger_lists")
    op.create_index(
        "ix_lhb_date_code_reason",
        "dragon_tiger_lists",
        ["trade_date", "code", "reason"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_lhb_date_code_reason", table_name="dragon_tiger_lists")
    op.create_index(
        "ix_lhb_date_code",
        "dragon_tiger_lists",
        ["trade_date", "code"],
        unique=True,
    )
