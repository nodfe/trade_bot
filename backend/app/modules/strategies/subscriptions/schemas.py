from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SubscriptionCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    strategy_key: str = Field(..., min_length=1, max_length=80)
    params: dict[str, Any] | None = None
    bot_channel_id: str = Field(..., min_length=1, max_length=128)
    # 6-field cron (sec min hour day month dow). Default: every Monday 09:30 CST.
    schedule: str = Field("0 30 9 * * 1", max_length=64)
    enabled: bool = True


class SubscriptionOut(BaseModel):
    id: str
    user_id: str
    strategy_key: str
    params: dict[str, Any] | None
    bot_channel_id: str
    schedule: str
    enabled: bool
    last_dispatched_at: datetime | None
    created_at: datetime


class DispatchOut(BaseModel):
    dispatched: int
    subscription_ids: list[str]
