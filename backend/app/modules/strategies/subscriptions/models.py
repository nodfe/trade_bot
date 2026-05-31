from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StrategySubscription(Base):
    """A user-level subscription that triggers strategy screens on a schedule
    and pushes the result as a card to a bot channel (e.g. Feishu chat).
    """

    __tablename__ = "strategy_subscriptions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), index=True)
    params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    bot_channel_id: Mapped[str] = mapped_column(String(128))
    schedule: Mapped[str] = mapped_column(String(64), default="0 30 9 * * 1")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    __table_args__ = (
        Index(
            "ix_strategy_subscriptions_user_strategy",
            "user_id",
            "strategy_key",
        ),
    )
