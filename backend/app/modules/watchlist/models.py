from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    source_screen_type: Mapped[str | None] = mapped_column(String(50))
    screen_params_json: Mapped[str | None] = mapped_column(Text)
    auto_refresh: Mapped[str] = mapped_column(String(10), default="manual")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    watchlist_id: Mapped[str] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE"),
        index=True,
    )
    stock_code: Mapped[str] = mapped_column(String(10), index=True)
    stock_name: Mapped[str] = mapped_column(String(50))
    match_reason: Mapped[str | None] = mapped_column(Text)
    hot_tags: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (Index("ix_watchlist_item_unique", "watchlist_id", "stock_code", unique=True),)
