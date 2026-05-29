import asyncio
import time
from datetime import date

from loguru import logger

from app.modules.market_data.providers import akshare as _ak_mod
from app.modules.market_data.providers.akshare import AKShareProvider
from app.modules.market_data.providers.base import (
    Bar,
    DragonTigerItem,
    LimitUpItem,
    NewsItem,
    Quote,
    StockInfo,
)
from app.modules.market_data.providers.tushare import TushareProvider

# Max seconds to wait for a realtime quote before falling through to
# the daily-bar fallback.  Keeps the quote endpoint responsive even
# when the external market-data API is slow or unreachable.  The cold
# AKShare snapshot fetch (~5000 stocks) typically takes 1-3s, so 3s
# strikes a balance between responsiveness and not tripping the backoff
# on every server boot.
_QUOTE_TIMEOUT = 3.0


class DataFacade:
    """统一数据入口，主备自动降级"""

    def __init__(self, primary: TushareProvider, fallback: AKShareProvider):
        self.primary = primary
        self.fallback = fallback

    async def get_daily_bars(self, code: str, start_date: date, end_date: date) -> list[Bar]:
        try:
            result = await self.primary.get_daily_bars(code, start_date, end_date)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Primary source (Tushare) failed for daily_bars {code}: {e}")
        return await self.fallback.get_daily_bars(code, start_date, end_date)

    async def get_realtime_quote(self, codes: list[str]) -> list[Quote]:
        # Tushare does not support realtime quotes — skip straight to AKShare.
        # Apply a timeout so we don't stall for 5+ seconds when the external
        # API is unreachable; the caller will fall through to the daily-bar
        # fallback instead.
        try:
            result = await asyncio.wait_for(
                self.fallback.get_realtime_quote(codes),
                timeout=_QUOTE_TIMEOUT,
            )
            if result:
                return result
        except asyncio.TimeoutError:
            logger.warning("Realtime quote timed out after %.1fs", _QUOTE_TIMEOUT)
            # Mark the AKShare snapshot as failed so subsequent requests skip
            # the retry and go straight to the daily-bar fallback.
            _ak_mod._snapshot_fail_ts = time.monotonic()
        return []

    async def get_stock_list(self) -> list[StockInfo]:
        try:
            result = await self.primary.get_stock_list()
            if result:
                return result
        except Exception as e:
            logger.warning(f"Primary source (Tushare) failed for stock_list: {e}")
        return await self.fallback.get_stock_list()

    async def get_dragon_tiger_list(self, trade_date: date) -> list[DragonTigerItem]:
        try:
            result = await self.primary.get_dragon_tiger_list(trade_date)
            if result:
                return result
        except Exception as e:
            logger.warning(
                f"Primary source (Tushare) failed for dragon_tiger_list {trade_date}: {e}"
            )
        return await self.fallback.get_dragon_tiger_list(trade_date)

    async def get_limit_up_board(self, trade_date: date) -> list[LimitUpItem]:
        try:
            result = await self.primary.get_limit_up_board(trade_date)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Primary source (Tushare) failed for limit_up_board {trade_date}: {e}")
        return await self.fallback.get_limit_up_board(trade_date)

    async def get_daily_news(self, trade_date: date) -> list[NewsItem]:
        # Tushare has no news API, go straight to AKShare
        return await self.fallback.get_daily_news(trade_date)


def create_data_facade() -> DataFacade:
    return DataFacade(primary=TushareProvider(), fallback=AKShareProvider())
