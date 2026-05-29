import asyncio
import time
from datetime import date

import akshare as ak
from loguru import logger

from app.modules.market_data.providers.base import (
    Bar,
    DragonTigerItem,
    LimitUpItem,
    MarketDataSource,
    NewsItem,
    Quote,
    StockInfo,
)

# ---------------------------------------------------------------------------
# TTL cache for the full-market spot snapshot (used by quote + stock_list)
# ---------------------------------------------------------------------------

_SNAPSHOT_TTL = 15  # seconds — short enough for "realtime", long enough to avoid spamming

_snapshot_cache: list[Quote] | None = None
_snapshot_ts: float = 0.0
_snapshot_fail_ts: float = 0.0  # monotonic time of last failed refresh
_snapshot_lock = asyncio.Lock()

_FAIL_BACKOFF = 60  # seconds to skip retry after a failed refresh


async def _get_spot_snapshot() -> list[Quote]:
    """Return the cached market snapshot, refreshing if stale.

    Uses an asyncio Lock so that at most one refresh is in-flight at a time;
    concurrent callers wait for the in-flight refresh instead of firing their
    own.  After a failed refresh, we back off for _FAIL_BACKOFF seconds to
    avoid hammering a flaky endpoint on every request.
    """
    global _snapshot_cache, _snapshot_ts, _snapshot_fail_ts

    # Return cached data if still fresh
    if _snapshot_cache is not None and (time.monotonic() - _snapshot_ts) < _SNAPSHOT_TTL:
        return _snapshot_cache

    # If last refresh failed recently, skip retry to avoid 5s+ stalls
    if _snapshot_cache is None and (time.monotonic() - _snapshot_fail_ts) < _FAIL_BACKOFF:
        return []

    async with _snapshot_lock:
        # Double-check after acquiring the lock
        if _snapshot_cache is not None and (time.monotonic() - _snapshot_ts) < _SNAPSHOT_TTL:
            return _snapshot_cache
        if _snapshot_cache is None and (time.monotonic() - _snapshot_fail_ts) < _FAIL_BACKOFF:
            return []

        try:
            df = await asyncio.to_thread(ak.stock_zh_a_spot_em)
            if df is None or df.empty:
                logger.warning("AKShare stock_zh_a_spot_em returned empty DataFrame")
                return _snapshot_cache or []

            quotes: list[Quote] = []
            for _, row in df.iterrows():
                try:
                    quotes.append(
                        Quote(
                            code=str(row["代码"]),
                            name=str(row["名称"]),
                            price=float(row["最新价"]) if row.get("最新价") else 0.0,
                            change=float(row["涨跌额"]) if row.get("涨跌额") else 0.0,
                            change_pct=float(row["涨跌幅"]) if row.get("涨跌幅") else 0.0,
                            volume=int(row["成交量"]) if row.get("成交量") else 0,
                            amount=float(row["成交额"]) if row.get("成交额") else 0.0,
                            open=float(row["今开"]) if row.get("今开") else None,
                            high=float(row["最高"]) if row.get("最高") else None,
                            low=float(row["最低"]) if row.get("最低") else None,
                            prev_close=float(row["昨收"]) if row.get("昨收") else None,
                        )
                    )
                except (ValueError, TypeError, KeyError):
                    continue

            _snapshot_cache = quotes
            _snapshot_ts = time.monotonic()
            logger.debug(f"AKShare spot snapshot refreshed: {len(quotes)} quotes cached")
            return quotes
        except Exception as e:
            logger.error(f"AKShare spot snapshot refresh failed: {e}")
            _snapshot_fail_ts = time.monotonic()
            return _snapshot_cache or []


class AKShareProvider(MarketDataSource):
    async def get_daily_bars(self, code: str, start_date: date, end_date: date) -> list[Bar]:
        try:
            symbol = self._to_symbol(code)
            df = await asyncio.to_thread(
                ak.stock_zh_a_hist,
                symbol=symbol,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq",
            )
            if df is None or df.empty:
                return []
            return [
                Bar(
                    code=code,
                    trade_date=date.fromisoformat(str(row["日期"])),
                    open=float(row["开盘"]),
                    high=float(row["最高"]),
                    low=float(row["最低"]),
                    close=float(row["收盘"]),
                    volume=int(row["成交量"]),
                    amount=float(row["成交额"]),
                    turnover=float(row["换手率"]) if row.get("换手率") else None,
                )
                for _, row in df.iterrows()
            ]
        except Exception as e:
            logger.error(f"AKShare get_daily_bars failed for {code}: {e}")
            return []

    async def get_realtime_quote(self, codes: list[str]) -> list[Quote]:
        """Serve quotes from the cached market snapshot instead of hitting the
        network on every call.  The snapshot auto-refreshes every 15 s.

        Returns empty list immediately if no snapshot is available yet and the
        last refresh failed within the backoff window, so the caller can fall
        through to a cheaper fallback without stalling."""
        try:
            snapshot = await _get_spot_snapshot()
            if not snapshot:
                return []
            code_set = set(codes)
            return [q for q in snapshot if q.code in code_set]
        except Exception as e:
            logger.error(f"AKShare get_realtime_quote failed: {e}")
            return []

    async def get_stock_list(self) -> list[StockInfo]:
        """Reuse the spot snapshot cache so we don't fetch the same data twice."""
        try:
            snapshot = await _get_spot_snapshot()
            return [
                StockInfo(code=q.code, name=q.name)
                for q in snapshot
            ]
        except Exception as e:
            logger.error(f"AKShare get_stock_list failed: {e}")
            return []

    async def get_dragon_tiger_list(self, trade_date: date) -> list[DragonTigerItem]:
        try:
            date_str = trade_date.strftime("%Y%m%d")
            df = await asyncio.to_thread(
                ak.stock_lhb_detail_em,
                start_date=date_str,
                end_date=date_str,
            )
            if df is None or df.empty:
                return []
            return [
                DragonTigerItem(
                    trade_date=trade_date,
                    code=str(row["代码"]),
                    name=str(row["名称"]),
                    close_price=float(row["收盘价"]) if row.get("收盘价") else 0.0,
                    change_pct=float(row["涨跌幅"]) if row.get("涨跌幅") else 0.0,
                    reason=str(row.get("上榜原因", "")) or None,
                    buy_amount=float(row["买入额"]) if row.get("买入额") else None,
                    sell_amount=float(row["卖出额"]) if row.get("卖出额") else None,
                    net_buy=float(row["净买入额"]) if row.get("净买入额") else None,
                )
                for _, row in df.iterrows()
            ]
        except Exception as e:
            logger.error(f"AKShare get_dragon_tiger_list failed for {trade_date}: {e}")
            return []

    async def get_limit_up_board(self, trade_date: date) -> list[LimitUpItem]:
        try:
            date_str = trade_date.strftime("%Y%m%d")
            df = await asyncio.to_thread(ak.stock_zt_pool_em, date=date_str)
            if df is None or df.empty:
                return []
            return [
                LimitUpItem(
                    trade_date=trade_date,
                    code=str(row["代码"]),
                    name=str(row["名称"]),
                    close_price=float(row["收盘价"]) if row.get("收盘价") else 0.0,
                    change_pct=float(row["涨跌幅"]) if row.get("涨跌幅") else 0.0,
                    limit_up_time=str(row.get("首次封板时间", "")) or None,
                    open_times=int(row["开板次数"]) if row.get("开板次数") else None,
                    turnover=float(row["换手率"]) if row.get("换手率") else None,
                    reason=str(row.get("涨停原因", "")) or None,
                )
                for _, row in df.iterrows()
            ]
        except Exception as e:
            logger.error(f"AKShare get_limit_up_board failed for {trade_date}: {e}")
            return []

    async def get_daily_news(self, trade_date: date) -> list[NewsItem]:
        try:
            df = await asyncio.to_thread(ak.stock_news_em, symbol="财经")
            if df is None or df.empty:
                return []
            return [
                NewsItem(
                    trade_date=trade_date,
                    title=str(row.get("新闻标题", "")),
                    content=str(row.get("新闻内容", "")) or None,
                    source=str(row.get("来源", "")) or None,
                    url=str(row.get("新闻链接", "")) or None,
                    code=None,
                    published_at=None,
                )
                for _, row in df.head(100).iterrows()
            ]
        except Exception as e:
            logger.error(f"AKShare get_daily_news failed for {trade_date}: {e}")
            return []

    @staticmethod
    def _to_symbol(code: str) -> str:
        return code
