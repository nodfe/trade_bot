from __future__ import annotations

import json
from uuid import uuid4

from app.modules.market_data.schemas import StockScreenParams
from app.modules.market_data.service import MarketDataService
from app.modules.watchlist.models import Watchlist, WatchlistItem
from app.modules.watchlist.repository import WatchlistRepository
from app.modules.watchlist.schemas import WatchlistCreate, WatchlistItemOut, WatchlistOut


class WatchlistService:
    def __init__(self) -> None:
        self.repo = WatchlistRepository()
        self.market_data_service = MarketDataService()

    async def list_watchlists(self) -> list[WatchlistOut]:
        watchlists = await self.repo.list_watchlists()
        result: list[WatchlistOut] = []
        for watchlist in watchlists:
            items = await self.repo.get_watchlist_items(watchlist.id)
            result.append(self._to_schema(watchlist, items))
        return result

    async def get_watchlist(self, watchlist_id: str) -> WatchlistOut | None:
        watchlist = await self.repo.get_watchlist(watchlist_id)
        if not watchlist:
            return None
        items = await self.repo.get_watchlist_items(watchlist_id)
        return self._to_schema(watchlist, items)

    async def create_watchlist(self, payload: WatchlistCreate) -> WatchlistOut:
        watchlist = Watchlist(
            id=str(uuid4()),
            name=payload.name,
            source_screen_type=payload.source_screen_type,
            screen_params_json=payload.screen_params_json,
            auto_refresh=payload.auto_refresh,
            notes=payload.notes,
        )
        items = [
            WatchlistItem(
                id=str(uuid4()),
                watchlist_id=watchlist.id,
                stock_code=item.stock_code,
                stock_name=item.stock_name,
                match_reason=item.match_reason,
                hot_tags=",".join(item.hot_tags),
            )
            for item in payload.items
        ]
        created = await self.repo.create_watchlist(watchlist, items)
        return self._to_schema(created, items)

    async def refresh_watchlist(self, watchlist_id: str) -> WatchlistOut | None:
        watchlist = await self.repo.get_watchlist(watchlist_id)
        if not watchlist:
            return None

        if not watchlist.source_screen_type or not watchlist.screen_params_json:
            items = await self.repo.get_watchlist_items(watchlist_id)
            return self._to_schema(watchlist, items)

        params = StockScreenParams(**json.loads(watchlist.screen_params_json))
        screen_result = await self.market_data_service.screen_stocks(watchlist.source_screen_type, params)
        refreshed_items = [
            WatchlistItem(
                id=str(uuid4()),
                watchlist_id=watchlist.id,
                stock_code=item.symbol,
                stock_name=item.name,
                match_reason=item.match_reason,
                hot_tags=",".join(item.hot_tags),
            )
            for item in screen_result.items
        ]
        await self.repo.replace_watchlist_items(watchlist_id, refreshed_items)
        return self._to_schema(watchlist, refreshed_items)

    async def refresh_auto_watchlists(self) -> list[WatchlistOut]:
        watchlists = await self.repo.list_auto_refresh_watchlists()
        refreshed: list[WatchlistOut] = []
        for watchlist in watchlists:
            updated = await self.refresh_watchlist(watchlist.id)
            if updated:
                refreshed.append(updated)
        return refreshed

    @staticmethod
    def _to_schema(watchlist: Watchlist, items: list[WatchlistItem]) -> WatchlistOut:
        return WatchlistOut(
            id=watchlist.id,
            name=watchlist.name,
            source_screen_type=watchlist.source_screen_type,
            screen_params_json=watchlist.screen_params_json,
            auto_refresh=watchlist.auto_refresh,
            notes=watchlist.notes,
            created_at=watchlist.created_at,
            items=[
                WatchlistItemOut(
                    id=item.id,
                    stock_code=item.stock_code,
                    stock_name=item.stock_name,
                    match_reason=item.match_reason,
                    hot_tags=item.hot_tags.split(",") if item.hot_tags else [],
                    created_at=item.created_at,
                )
                for item in items
            ],
        )
