from datetime import date

import tushare as ts
from loguru import logger

from app.config import settings
from app.modules.market_data.providers.base import (
    Bar,
    DragonTigerItem,
    LimitUpItem,
    MarketDataSource,
    NewsItem,
    Quote,
    StockInfo,
)


class TushareProvider(MarketDataSource):
    def __init__(self):
        self._pro = ts.pro_api(settings.tushare_token) if settings.tushare_token else None

    def _ensure_client(self):
        if not self._pro:
            self._pro = ts.pro_api(settings.tushare_token)
        return self._pro

    async def get_daily_bars(self, code: str, start_date: date, end_date: date) -> list[Bar]:
        pro = self._ensure_client()
        ts_code = self._to_ts_code(code)
        df = pro.daily(ts_code=ts_code, start_date=start_date.strftime("%Y%m%d"), end_date=end_date.strftime("%Y%m%d"))
        if df is None or df.empty:
            return []
        return [
            Bar(
                code=self._from_ts_code(row["ts_code"]),
                trade_date=date.fromisoformat(str(row["trade_date"])),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["vol"]),
                amount=float(row["amount"]),
            )
            for _, row in df.iterrows()
        ]

    async def get_realtime_quote(self, codes: list[str]) -> list[Quote]:
        logger.warning("Tushare does not support realtime quotes, use AKShare instead")
        return []

    async def get_stock_list(self) -> list[StockInfo]:
        pro = self._ensure_client()
        df = pro.stock_basic(exchange="", list_status="L", fields="ts_code,symbol,name,area,industry,list_date")
        if df is None or df.empty:
            return []
        return [
            StockInfo(
                code=str(row["symbol"]),
                name=str(row["name"]),
                industry=str(row.get("industry", "")) or None,
                market="SH" if row["ts_code"].endswith(".SH") else "SZ",
                list_date=date.fromisoformat(str(row["list_date"])) if row.get("list_date") else None,
            )
            for _, row in df.iterrows()
        ]

    async def get_dragon_tiger_list(self, trade_date: date) -> list[DragonTigerItem]:
        try:
            pro = self._ensure_client()
            date_str = trade_date.strftime("%Y%m%d")
            df = pro.top_list(trade_date=date_str)
            if df is None or df.empty:
                return []
            return [
                DragonTigerItem(
                    trade_date=trade_date,
                    code=self._from_ts_code(row["ts_code"]),
                    name=str(row.get("name", "")),
                    close_price=float(row.get("close", 0)),
                    change_pct=float(row.get("pct_change", 0)),
                    reason=str(row.get("exalter", "")) or None,
                    buy_amount=float(row.get("buy", 0)) if row.get("buy") else None,
                    sell_amount=float(row.get("sell", 0)) if row.get("sell") else None,
                    net_buy=float(row.get("net_buy", 0)) if row.get("net_buy") else None,
                )
                for _, row in df.iterrows()
            ]
        except Exception as e:
            logger.error(f"Tushare get_dragon_tiger_list failed for {trade_date}: {e}")
            return []

    async def get_limit_up_board(self, trade_date: date) -> list[LimitUpItem]:
        try:
            pro = self._ensure_client()
            date_str = trade_date.strftime("%Y%m%d")
            df = pro.limit_list(trade_date=date_str)
            if df is None or df.empty:
                return []
            return [
                LimitUpItem(
                    trade_date=trade_date,
                    code=self._from_ts_code(row["ts_code"]),
                    name=str(row.get("name", "")),
                    close_price=float(row.get("close", 0)),
                    change_pct=float(row.get("pct_change", 0)),
                    limit_up_time=None,
                    open_times=int(row.get("open_times", 0)) if row.get("open_times") else None,
                    turnover=float(row.get("turnover_ratio", 0)) if row.get("turnover_ratio") else None,
                    reason=str(row.get("limit_times", "")) or None,
                )
                for _, row in df.iterrows()
            ]
        except Exception as e:
            logger.error(f"Tushare get_limit_up_board failed for {trade_date}: {e}")
            return []

    async def get_daily_news(self, trade_date: date) -> list[NewsItem]:
        logger.warning("Tushare does not support daily news, use AKShare instead")
        return []

    @staticmethod
    def _to_ts_code(code: str) -> str:
        if "." in code:
            return code
        if code.startswith("6") or code.startswith("9"):
            return f"{code}.SH"
        return f"{code}.SZ"

    @staticmethod
    def _from_ts_code(ts_code: str) -> str:
        return ts_code.split(".")[0]
