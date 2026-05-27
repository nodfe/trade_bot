from datetime import date

import akshare as ak
from loguru import logger

from app.modules.market_data.providers.base import Bar, MarketDataSource, Quote, StockInfo, DragonTigerItem, LimitUpItem, NewsItem


class AKShareProvider(MarketDataSource):
    async def get_daily_bars(self, code: str, start_date: date, end_date: date) -> list[Bar]:
        try:
            symbol = self._to_symbol(code)
            df = ak.stock_zh_a_hist(
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
        try:
            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty:
                return []
            df_filtered = df[df["代码"].isin(codes)]
            return [
                Quote(
                    code=str(row["代码"]),
                    name=str(row["名称"]),
                    price=float(row["最新价"]),
                    change=float(row["涨跌额"]),
                    change_pct=float(row["涨跌幅"]),
                    volume=int(row["成交量"]),
                    amount=float(row["成交额"]),
                    open=float(row["今开"]) if row.get("今开") else None,
                    high=float(row["最高"]) if row.get("最高") else None,
                    low=float(row["最低"]) if row.get("最低") else None,
                    prev_close=float(row["昨收"]) if row.get("昨收") else None,
                )
                for _, row in df_filtered.iterrows()
            ]
        except Exception as e:
            logger.error(f"AKShare get_realtime_quote failed: {e}")
            return []

    async def get_stock_list(self) -> list[StockInfo]:
        try:
            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty:
                return []
            return [
                StockInfo(
                    code=str(row["代码"]),
                    name=str(row["名称"]),
                )
                for _, row in df.iterrows()
            ]
        except Exception as e:
            logger.error(f"AKShare get_stock_list failed: {e}")
            return []

    async def get_dragon_tiger_list(self, trade_date: date) -> list[DragonTigerItem]:
        try:
            date_str = trade_date.strftime("%Y%m%d")
            df = ak.stock_lhb_detail_em(start_date=date_str, end_date=date_str)
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
            df = ak.stock_zt_pool_em(date=date_str)
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
            df = ak.stock_news_em(symbol="财经")
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
                for _, row in df.head(100).iterrows()  # 限制 100 条
            ]
        except Exception as e:
            logger.error(f"AKShare get_daily_news failed for {trade_date}: {e}")
            return []

    @staticmethod
    def _to_symbol(code: str) -> str:
        return code
