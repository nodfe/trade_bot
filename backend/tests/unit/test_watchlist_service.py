from __future__ import annotations

import pytest

from app.core.exceptions import BadRequestError
from app.modules.watchlist.schemas import WatchlistCreate, WatchlistItemCreate
from app.modules.watchlist.service import WatchlistService


@pytest.mark.asyncio
async def test_create_auto_refresh_watchlist_requires_params() -> None:
    service = WatchlistService()

    payload = WatchlistCreate(
        name="强势池",
        source_screen_type="strong_uptrend",
        auto_refresh="daily",
        items=[
            WatchlistItemCreate(
                stock_code="600519",
                stock_name="贵州茅台",
            )
        ],
    )

    with pytest.raises(BadRequestError, match="screen_params_json"):
        await service.create_watchlist(payload)
