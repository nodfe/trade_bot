"""init schema

Revision ID: 20260527_0001
Revises:
Create Date: 2026-05-27 19:40:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20260527_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stocks",
        sa.Column("code", sa.String(length=10), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("industry", sa.String(length=50), nullable=True),
        sa.Column("market", sa.String(length=10), nullable=False),
        sa.Column("list_date", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "daily_bars",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("turnover", sa.Float(), nullable=True),
    )
    op.create_index("ix_daily_bars_code", "daily_bars", ["code"])
    op.create_index("ix_daily_bars_trade_date", "daily_bars", ["trade_date"])
    op.create_index("ix_daily_bars_code_date", "daily_bars", ["code", "trade_date"], unique=True)

    op.create_table(
        "dragon_tiger_lists",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("close_price", sa.Float(), nullable=False),
        sa.Column("change_pct", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column("buy_amount", sa.Float(), nullable=True),
        sa.Column("sell_amount", sa.Float(), nullable=True),
        sa.Column("net_buy", sa.Float(), nullable=True),
    )
    op.create_index("ix_dragon_tiger_lists_trade_date", "dragon_tiger_lists", ["trade_date"])
    op.create_index("ix_dragon_tiger_lists_code", "dragon_tiger_lists", ["code"])
    op.create_index("ix_lhb_date_code", "dragon_tiger_lists", ["trade_date", "code"], unique=True)

    op.create_table(
        "limit_up_boards",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("close_price", sa.Float(), nullable=False),
        sa.Column("change_pct", sa.Float(), nullable=False),
        sa.Column("limit_up_time", sa.String(length=20), nullable=True),
        sa.Column("open_times", sa.Integer(), nullable=True),
        sa.Column("turnover", sa.Float(), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=True),
    )
    op.create_index("ix_limit_up_boards_trade_date", "limit_up_boards", ["trade_date"])
    op.create_index("ix_limit_up_boards_code", "limit_up_boards", ["code"])
    op.create_index("ix_zt_date_code", "limit_up_boards", ["trade_date", "code"], unique=True)

    op.create_table(
        "daily_news",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("code", sa.String(length=10), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_daily_news_trade_date", "daily_news", ["trade_date"])
    op.create_index("ix_daily_news_code", "daily_news", ["code"])
    op.create_index("ix_news_date_title", "daily_news", ["trade_date", "title"], unique=True)

    op.create_table(
        "watchlists",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("source_screen_type", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_watchlists_name", "watchlists", ["name"], unique=True)

    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "watchlist_id",
            sa.String(length=64),
            sa.ForeignKey("watchlists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stock_code", sa.String(length=10), nullable=False),
        sa.Column("stock_name", sa.String(length=50), nullable=False),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("hot_tags", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_watchlist_items_watchlist_id", "watchlist_items", ["watchlist_id"])
    op.create_index("ix_watchlist_items_stock_code", "watchlist_items", ["stock_code"])
    op.create_index(
        "ix_watchlist_item_unique",
        "watchlist_items",
        ["watchlist_id", "stock_code"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_watchlist_item_unique", table_name="watchlist_items")
    op.drop_index("ix_watchlist_items_stock_code", table_name="watchlist_items")
    op.drop_index("ix_watchlist_items_watchlist_id", table_name="watchlist_items")
    op.drop_table("watchlist_items")

    op.drop_index("ix_watchlists_name", table_name="watchlists")
    op.drop_table("watchlists")

    op.drop_index("ix_news_date_title", table_name="daily_news")
    op.drop_index("ix_daily_news_code", table_name="daily_news")
    op.drop_index("ix_daily_news_trade_date", table_name="daily_news")
    op.drop_table("daily_news")

    op.drop_index("ix_zt_date_code", table_name="limit_up_boards")
    op.drop_index("ix_limit_up_boards_code", table_name="limit_up_boards")
    op.drop_index("ix_limit_up_boards_trade_date", table_name="limit_up_boards")
    op.drop_table("limit_up_boards")

    op.drop_index("ix_lhb_date_code", table_name="dragon_tiger_lists")
    op.drop_index("ix_dragon_tiger_lists_code", table_name="dragon_tiger_lists")
    op.drop_index("ix_dragon_tiger_lists_trade_date", table_name="dragon_tiger_lists")
    op.drop_table("dragon_tiger_lists")

    op.drop_index("ix_daily_bars_code_date", table_name="daily_bars")
    op.drop_index("ix_daily_bars_trade_date", table_name="daily_bars")
    op.drop_index("ix_daily_bars_code", table_name="daily_bars")
    op.drop_table("daily_bars")

    op.drop_table("stocks")
