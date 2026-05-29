from datetime import UTC, date, datetime, timedelta

import pandas as pd
from loguru import logger
from ta.momentum import RSIIndicator
from ta.trend import MACD

from app.modules.market_data.models import DailyBar, DailyNews, DragonTigerList, LimitUpBoard, Stock
from app.modules.market_data.providers.base import Quote
from app.modules.market_data.providers.facade import DataFacade, create_data_facade
from app.modules.market_data.repository import MarketDataRepository
from app.modules.market_data.schemas import (
    MarketOverviewOut,
    StockAnalysisSummaryOut,
    StockScreenItemOut,
    StockScreenParams,
    StockScreenResultOut,
    SyncResult,
)
from app.modules.sync_runs import SyncRunService


class MarketDataService:
    def __init__(self):
        self.repo = MarketDataRepository()
        self.facade: DataFacade = create_data_facade()
        self.sync_runs = SyncRunService()

    async def get_stocks(self) -> list[Stock]:
        return await self.repo.get_stocks()

    async def get_stock(self, code: str) -> Stock | None:
        return await self.repo.get_stock(code)

    async def get_stock_quote(self, code: str) -> Quote | None:
        quotes = await self.facade.get_realtime_quote([code])
        if quotes:
            return quotes[0]
        return None

    async def get_stock_kline(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 120,
        period: str = "daily",
    ) -> list[DailyBar]:
        bars = await self.get_daily_bars(code, start_date, end_date)
        bars_sorted = sorted(bars, key=lambda bar: bar.trade_date)
        if period != "daily":
            bars_sorted = self._resample_bars(bars_sorted, period)
        if limit > 0:
            return bars_sorted[-limit:]
        return bars_sorted

    @staticmethod
    def _resample_bars(bars: list[DailyBar], period: str) -> list[DailyBar]:
        """Resample daily bars to weekly/monthly server-side.

        Aggregation: open=first, high=max, low=min, close=last,
        volume=sum, amount=sum, turnover=mean.
        """
        if not bars:
            return bars
        rule_map = {"weekly": "W-FRI", "monthly": "ME"}
        rule = rule_map.get(period)
        if rule is None:
            return bars
        df = pd.DataFrame(
            [
                {
                    "trade_date": pd.Timestamp(b.trade_date),
                    "code": b.code,
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                    "amount": b.amount,
                    "turnover": b.turnover,
                }
                for b in bars
            ]
        ).set_index("trade_date")
        agg = df.resample(rule).agg(
            {
                "code": "last",
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "amount": "sum",
                "turnover": "mean",
            }
        ).dropna(subset=["close"])
        return [
            DailyBar(
                code=row["code"],
                trade_date=idx.date(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]),
                amount=float(row["amount"]),
                turnover=(
                    float(row["turnover"]) if pd.notna(row["turnover"]) else None
                ),
            )
            for idx, row in agg.iterrows()
        ]

    async def get_stock_analysis_summary(self, code: str) -> StockAnalysisSummaryOut | None:
        bars = await self.get_stock_kline(code, limit=20)
        if len(bars) < 5:
            return None

        closes = [bar.close for bar in bars]
        volumes = [float(bar.volume) for bar in bars]
        latest_close = closes[-1]

        ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else None
        ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
        rsi14, macd_value, macd_signal, macd_histogram = self._calculate_ta_metrics(closes)

        price_vs_ma5_pct = ((latest_close - ma5) / ma5 * 100) if ma5 else None
        price_vs_ma20_pct = ((latest_close - ma20) / ma20 * 100) if ma20 else None
        return_5d_pct = (
            ((latest_close - closes[-5]) / closes[-5] * 100)
            if len(closes) >= 5
            else None
        )
        return_20d_pct = (
            ((latest_close - closes[0]) / closes[0] * 100)
            if len(closes) >= 20
            else None
        )

        latest_volume = volumes[-1]
        avg_volume_5d = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else None
        volume_ratio_5d = (latest_volume / avg_volume_5d) if avg_volume_5d else None

        trend_bias = self._determine_trend_bias(price_vs_ma5_pct, price_vs_ma20_pct, return_20d_pct)
        summary = self._build_analysis_summary(
            trend_bias=trend_bias,
            price_vs_ma5_pct=price_vs_ma5_pct,
            price_vs_ma20_pct=price_vs_ma20_pct,
            return_20d_pct=return_20d_pct,
            volume_ratio_5d=volume_ratio_5d,
            rsi14=rsi14,
            macd_histogram=macd_histogram,
        )
        signals = self._build_analysis_signals(
            trend_bias=trend_bias,
            ma5=ma5,
            ma20=ma20,
            rsi14=rsi14,
            macd_histogram=macd_histogram,
            return_5d_pct=return_5d_pct,
            return_20d_pct=return_20d_pct,
            volume_ratio_5d=volume_ratio_5d,
        )

        return StockAnalysisSummaryOut(
            symbol=code,
            latest_close=latest_close,
            ma5=ma5,
            ma20=ma20,
            rsi14=rsi14,
            macd=macd_value,
            macd_signal=macd_signal,
            macd_histogram=macd_histogram,
            price_vs_ma5_pct=price_vs_ma5_pct,
            price_vs_ma20_pct=price_vs_ma20_pct,
            return_5d_pct=return_5d_pct,
            return_20d_pct=return_20d_pct,
            volume_ratio_5d=volume_ratio_5d,
            trend_bias=trend_bias,
            summary=summary,
            signals=signals,
        )

    async def get_market_overview(self) -> MarketOverviewOut:
        stocks = await self.repo.get_stocks()
        latest_bar_date = await self.repo.get_latest_trade_date_for_all_bars()

        latest_dragon_tiger_date = await self.repo.get_latest_trade_date_for_dragon_tiger()
        latest_limit_up_date = await self.repo.get_latest_trade_date_for_limit_up()
        latest_news_date = await self.repo.get_latest_trade_date_for_news()

        latest_dragon_tiger_count = 0
        if latest_dragon_tiger_date:
            latest_dragon_tiger_count = len(
                await self.repo.get_dragon_tiger_list(latest_dragon_tiger_date)
            )

        latest_limit_up_count = 0
        if latest_limit_up_date:
            latest_limit_up_count = len(await self.repo.get_limit_up_board(latest_limit_up_date))

        latest_news_count = 0
        if latest_news_date:
            latest_news_count = len(await self.repo.get_daily_news(latest_news_date, limit=100))

        return MarketOverviewOut(
            stock_count=len(stocks),
            latest_trade_date=latest_bar_date,
            latest_dragon_tiger_date=latest_dragon_tiger_date,
            latest_limit_up_date=latest_limit_up_date,
            latest_news_date=latest_news_date,
            latest_dragon_tiger_count=latest_dragon_tiger_count,
            latest_limit_up_count=latest_limit_up_count,
            latest_news_count=latest_news_count,
        )

    async def screen_stocks(
        self,
        screen_type: str,
        params: StockScreenParams | None = None,
    ) -> StockScreenResultOut:
        screen_type = screen_type.lower().strip()
        params = params or StockScreenParams()
        stocks = await self.repo.get_stocks()
        matches: list[StockScreenItemOut] = []

        latest_dragon_tiger_date = await self.repo.get_latest_trade_date_for_dragon_tiger()
        latest_limit_up_date = await self.repo.get_latest_trade_date_for_limit_up()
        latest_news_date = await self.repo.get_latest_trade_date_for_news()

        dragon_tiger_map: dict[str, DragonTigerList] = {}
        if latest_dragon_tiger_date:
            dragon_tiger_map = {
                item.code: item
                for item in await self.repo.get_dragon_tiger_list(latest_dragon_tiger_date)
            }

        limit_up_map: dict[str, LimitUpBoard] = {}
        if latest_limit_up_date:
            limit_up_map = {
                item.code: item for item in await self.repo.get_limit_up_board(latest_limit_up_date)
            }

        news_by_code: dict[str, list[str]] = {}
        if latest_news_date:
            for item in await self.repo.get_daily_news(latest_news_date, limit=100):
                if not item.code:
                    continue
                news_by_code.setdefault(item.code, []).append(item.title)

        for stock in stocks[:200]:
            analysis = await self.get_stock_analysis_summary(stock.code)
            if not analysis:
                continue

            match_reason = self._match_screen(screen_type, analysis, params)
            if not match_reason:
                continue

            dragon_tiger_item = dragon_tiger_map.get(stock.code)
            limit_up_item = limit_up_map.get(stock.code)
            hot_tags: list[str] = []
            if dragon_tiger_item:
                hot_tags.append("龙虎榜")
            if limit_up_item:
                hot_tags.append("涨停板")
            if news_by_code.get(stock.code):
                hot_tags.append("相关新闻")

            matches.append(
                StockScreenItemOut(
                    symbol=stock.code,
                    name=stock.name,
                    market=stock.market,
                    industry=stock.industry,
                    latest_close=analysis.latest_close,
                    return_5d_pct=analysis.return_5d_pct,
                    return_20d_pct=analysis.return_20d_pct,
                    volume_ratio_5d=analysis.volume_ratio_5d,
                    trend_bias=analysis.trend_bias,
                    match_reason=match_reason,
                    is_on_dragon_tiger=dragon_tiger_item is not None,
                    is_limit_up_candidate=limit_up_item is not None,
                    hot_tags=hot_tags,
                    related_news_headlines=news_by_code.get(stock.code, [])[:2],
                )
            )

        sorted_matches = self._sort_screen_matches(screen_type, matches)
        return StockScreenResultOut(
            screen_type=screen_type,
            total=len(sorted_matches),
            items=sorted_matches[: params.limit],
        )

    @staticmethod
    def quote_timestamp() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _determine_trend_bias(
        price_vs_ma5_pct: float | None,
        price_vs_ma20_pct: float | None,
        return_20d_pct: float | None,
    ) -> str:
        bullish = (
            (price_vs_ma5_pct or 0) > 0
            and (price_vs_ma20_pct or 0) > 0
            and (return_20d_pct or 0) > 0
        )
        bearish = (
            (price_vs_ma5_pct or 0) < 0
            and (price_vs_ma20_pct or 0) < 0
            and (return_20d_pct or 0) < 0
        )

        if bullish:
            return "bullish"
        if bearish:
            return "bearish"
        return "neutral"

    @staticmethod
    def _build_analysis_summary(
        trend_bias: str,
        price_vs_ma5_pct: float | None,
        price_vs_ma20_pct: float | None,
        return_20d_pct: float | None,
        volume_ratio_5d: float | None,
        rsi14: float | None,
        macd_histogram: float | None,
    ) -> str:
        trend_text = {
            "bullish": "短中期趋势偏强",
            "bearish": "短中期趋势偏弱",
            "neutral": "趋势仍在整理区间",
        }[trend_bias]

        ma5_text = (
            f"较 MA5 {price_vs_ma5_pct:+.2f}%"
            if price_vs_ma5_pct is not None
            else "MA5 数据不足"
        )
        ma20_text = (
            f"较 MA20 {price_vs_ma20_pct:+.2f}%"
            if price_vs_ma20_pct is not None
            else "MA20 数据不足"
        )
        return_text = (
            f"近20日 {return_20d_pct:+.2f}%"
            if return_20d_pct is not None
            else "20日收益待补充"
        )
        volume_text = (
            f"量比(5日) {volume_ratio_5d:.2f}x"
            if volume_ratio_5d is not None
            else "量能数据不足"
        )
        rsi_text = f"RSI14 {rsi14:.1f}" if rsi14 is not None else "RSI 数据不足"
        macd_text = (
            f"MACD柱 {'正值' if macd_histogram >= 0 else '负值'}"
            if macd_histogram is not None
            else "MACD 数据不足"
        )

        return (
            f"{trend_text}，{ma5_text}，{ma20_text}，{return_text}，"
            f"{volume_text}，{rsi_text}，{macd_text}。"
        )

    @staticmethod
    def _calculate_ta_metrics(
        closes: list[float],
    ) -> tuple[float | None, float | None, float | None, float | None]:
        if len(closes) < 14:
            return None, None, None, None

        close_series = pd.Series(closes, dtype="float64")
        rsi_series = RSIIndicator(close_series, window=14).rsi()

        if len(closes) < 26:
            latest_rsi = rsi_series.iloc[-1]
            return (float(latest_rsi) if pd.notna(latest_rsi) else None, None, None, None)

        macd_indicator = MACD(close_series)
        macd_series = macd_indicator.macd()
        macd_signal_series = macd_indicator.macd_signal()
        macd_diff_series = macd_indicator.macd_diff()

        latest_rsi = rsi_series.iloc[-1]
        latest_macd = macd_series.iloc[-1]
        latest_signal = macd_signal_series.iloc[-1]
        latest_hist = macd_diff_series.iloc[-1]

        return (
            float(latest_rsi) if pd.notna(latest_rsi) else None,
            float(latest_macd) if pd.notna(latest_macd) else None,
            float(latest_signal) if pd.notna(latest_signal) else None,
            float(latest_hist) if pd.notna(latest_hist) else None,
        )

    @staticmethod
    def _build_analysis_signals(
        trend_bias: str,
        ma5: float | None,
        ma20: float | None,
        rsi14: float | None,
        macd_histogram: float | None,
        return_5d_pct: float | None,
        return_20d_pct: float | None,
        volume_ratio_5d: float | None,
    ) -> list[dict[str, str]]:
        signals: list[dict[str, str]] = []

        trend_detail = {
            "bullish": "均线与阶段收益共振偏强",
            "bearish": "均线与阶段收益共振偏弱",
            "neutral": "多空仍在拉锯整理",
        }[trend_bias]
        signals.append({"name": "趋势结构", "detail": trend_detail})

        if ma5 is not None and ma20 is not None:
            ma_detail = (
                "MA5 位于 MA20 上方，短线领先"
                if ma5 >= ma20
                else "MA5 位于 MA20 下方，短线承压"
            )
            signals.append({"name": "均线关系", "detail": ma_detail})

        if rsi14 is not None:
            if rsi14 >= 70:
                rsi_detail = "RSI 进入高位区，短线偏热"
            elif rsi14 <= 30:
                rsi_detail = "RSI 进入低位区，存在修复可能"
            else:
                rsi_detail = "RSI 位于中性区，动量平衡"
            signals.append({"name": "RSI", "detail": rsi_detail})

        if macd_histogram is not None:
            macd_detail = (
                "MACD 柱体为正，动能向上"
                if macd_histogram >= 0
                else "MACD 柱体为负，动能向下"
            )
            signals.append({"name": "MACD", "detail": macd_detail})

        if return_5d_pct is not None and return_20d_pct is not None:
            momentum_detail = (
                f"近5日 {return_5d_pct:+.2f}%，近20日 {return_20d_pct:+.2f}%"
            )
            signals.append({"name": "阶段涨跌", "detail": momentum_detail})

        if volume_ratio_5d is not None:
            if volume_ratio_5d >= 1.2:
                volume_detail = f"量比 {volume_ratio_5d:.2f}x，量能放大"
            elif volume_ratio_5d <= 0.8:
                volume_detail = f"量比 {volume_ratio_5d:.2f}x，量能偏弱"
            else:
                volume_detail = f"量比 {volume_ratio_5d:.2f}x，量能平稳"
            signals.append({"name": "量能", "detail": volume_detail})

        return signals

    @staticmethod
    def _match_screen(
        screen_type: str,
        analysis: StockAnalysisSummaryOut,
        params: StockScreenParams,
    ) -> str | None:
        if screen_type == "strong_uptrend":
            min_return_20d_pct = (
                params.min_return_20d_pct
                if params.min_return_20d_pct is not None
                else 5
            )
            if (
                analysis.trend_bias == "bullish"
                and (analysis.return_20d_pct or 0) >= min_return_20d_pct
                and (analysis.rsi14 or 0) >= 50
            ):
                return f"多头趋势延续，20日收益超过 {min_return_20d_pct:.1f}% 且 RSI 共振偏强"
            return None

        if screen_type == "volume_breakout":
            min_volume_ratio = (
                params.min_volume_ratio if params.min_volume_ratio is not None else 1.3
            )
            min_return_5d_pct = (
                params.min_return_5d_pct if params.min_return_5d_pct is not None else 0
            )
            if (
                (analysis.volume_ratio_5d or 0) >= min_volume_ratio
                and (analysis.return_5d_pct or 0) > min_return_5d_pct
                and (analysis.macd_histogram or 0) > 0
            ):
                return f"量比超过 {min_volume_ratio:.2f}x 且近5日表现转强，具备突破观察价值"
            return None

        if screen_type == "pullback_watch":
            max_return_5d_pct = (
                params.max_return_5d_pct if params.max_return_5d_pct is not None else 1
            )
            if (
                analysis.trend_bias == "bullish"
                and (analysis.price_vs_ma20_pct or 0) > 0
                and -3 <= (analysis.return_5d_pct or 0) <= max_return_5d_pct
            ):
                return f"中期趋势未坏，近5日回撤控制在 {max_return_5d_pct:.1f}% 内，可继续跟踪"
            return None

        return None

    @staticmethod
    def _sort_screen_matches(
        screen_type: str,
        matches: list[StockScreenItemOut],
    ) -> list[StockScreenItemOut]:
        if screen_type == "volume_breakout":
            return sorted(
                matches,
                key=lambda item: ((item.volume_ratio_5d or 0), (item.return_5d_pct or 0)),
                reverse=True,
            )

        if screen_type == "pullback_watch":
            return sorted(
                matches,
                key=lambda item: ((item.return_20d_pct or 0), -(item.return_5d_pct or 0)),
                reverse=True,
            )

        return sorted(
            matches,
            key=lambda item: ((item.return_20d_pct or 0), (item.return_5d_pct or 0)),
            reverse=True,
        )

    async def get_daily_bars(
        self, code: str, start_date: date | None = None, end_date: date | None = None
    ) -> list[DailyBar]:
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=365)

        bars = await self.repo.get_daily_bars(code, start_date, end_date)
        if bars:
            return bars

        bar_dtos = await self.facade.get_daily_bars(code, start_date, end_date)
        return [
            DailyBar(
                code=b.code,
                trade_date=b.trade_date,
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume,
                amount=b.amount,
                turnover=b.turnover,
            )
            for b in bar_dtos
        ]

    async def sync_stock_list(self) -> int:
        async with self.sync_runs.track("stock_list") as handle:
            stock_dtos = await self.facade.get_stock_list()
            stocks = [
                Stock(
                    code=s.code,
                    name=s.name,
                    industry=s.industry,
                    market=s.market or "SZ",
                    list_date=s.list_date,
                )
                for s in stock_dtos
            ]
            count = await self.repo.save_stocks(stocks)
            handle.synced_count = count
            logger.info(f"Synced {count} stocks")
            return count

    async def sync_daily_bars(self, code: str, days: int = 30) -> int:
        async with self.sync_runs.track(
            "daily_bars", target=code, meta={"days": days}
        ) as handle:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            bar_dtos = await self.facade.get_daily_bars(code, start_date, end_date)
            bars = [
                DailyBar(
                    code=b.code,
                    trade_date=b.trade_date,
                    open=b.open,
                    high=b.high,
                    low=b.low,
                    close=b.close,
                    volume=b.volume,
                    amount=b.amount,
                    turnover=b.turnover,
                )
                for b in bar_dtos
            ]
            count = await self.repo.save_daily_bars(bars)
            handle.synced_count = count
            logger.info(f"Synced {count} daily bars for {code}")
            return count

    # -- Dragon Tiger List (龙虎榜) --

    async def get_dragon_tiger_list(self, trade_date: date) -> list[DragonTigerList]:
        return await self.repo.get_dragon_tiger_list(trade_date)

    async def sync_dragon_tiger_list(self, trade_date: date | None = None) -> SyncResult:
        if not trade_date:
            trade_date = date.today()
        if await self.repo.has_dragon_tiger_data(trade_date):
            existing = await self.repo.get_dragon_tiger_list(trade_date)
            await self.sync_runs.mark_skipped(
                "dragon_tiger",
                target=str(trade_date),
                reason="data already present",
            )
            return SyncResult(
                synced=0,
                message=f"{trade_date} 龙虎榜数据已存在，共 {len(existing)} 条记录",
            )
        async with self.sync_runs.track(
            "dragon_tiger", target=str(trade_date)
        ) as handle:
            dtos = await self.facade.get_dragon_tiger_list(trade_date)
            if not dtos:
                handle.synced_count = 0
                return SyncResult(synced=0, message=f"{trade_date} 龙虎榜无数据")
            items = [
                DragonTigerList(
                    trade_date=d.trade_date,
                    code=d.code,
                    name=d.name,
                    close_price=d.close_price,
                    change_pct=d.change_pct,
                    reason=d.reason,
                    buy_amount=d.buy_amount,
                    sell_amount=d.sell_amount,
                    net_buy=d.net_buy,
                )
                for d in dtos
            ]
            count = await self.repo.save_dragon_tiger_list(items)
            handle.synced_count = count
            logger.info(f"Synced {count} dragon tiger items for {trade_date}")
            return SyncResult(
                synced=count, message=f"{trade_date} 龙虎榜抓取成功，共 {count} 条"
            )

    # -- Limit Up Board (涨停板) --

    async def get_limit_up_board(self, trade_date: date) -> list[LimitUpBoard]:
        return await self.repo.get_limit_up_board(trade_date)

    async def sync_limit_up_board(self, trade_date: date | None = None) -> SyncResult:
        if not trade_date:
            trade_date = date.today()
        if await self.repo.has_limit_up_data(trade_date):
            existing = await self.repo.get_limit_up_board(trade_date)
            await self.sync_runs.mark_skipped(
                "limit_up",
                target=str(trade_date),
                reason="data already present",
            )
            return SyncResult(
                synced=0,
                message=f"{trade_date} 涨停板数据已存在，共 {len(existing)} 条记录",
            )
        async with self.sync_runs.track(
            "limit_up", target=str(trade_date)
        ) as handle:
            dtos = await self.facade.get_limit_up_board(trade_date)
            if not dtos:
                handle.synced_count = 0
                return SyncResult(synced=0, message=f"{trade_date} 涨停板无数据")
            items = [
                LimitUpBoard(
                    trade_date=d.trade_date,
                    code=d.code,
                    name=d.name,
                    close_price=d.close_price,
                    change_pct=d.change_pct,
                    limit_up_time=d.limit_up_time,
                    open_times=d.open_times,
                    turnover=d.turnover,
                    reason=d.reason,
                )
                for d in dtos
            ]
            count = await self.repo.save_limit_up_board(items)
            handle.synced_count = count
            logger.info(f"Synced {count} limit up items for {trade_date}")
            return SyncResult(
                synced=count, message=f"{trade_date} 涨停板抓取成功，共 {count} 条"
            )

    # -- Daily News (每日新闻) --

    async def get_daily_news(self, trade_date: date, limit: int = 50) -> list[DailyNews]:
        return await self.repo.get_daily_news(trade_date, limit)

    async def sync_daily_news(self, trade_date: date | None = None) -> SyncResult:
        if not trade_date:
            trade_date = date.today()
        if await self.repo.has_news_data(trade_date):
            await self.sync_runs.mark_skipped(
                "news",
                target=str(trade_date),
                reason="data already present",
            )
            return SyncResult(synced=0, message=f"{trade_date} 新闻数据已存在")
        async with self.sync_runs.track("news", target=str(trade_date)) as handle:
            dtos = await self.facade.get_daily_news(trade_date)
            if not dtos:
                handle.synced_count = 0
                return SyncResult(synced=0, message=f"{trade_date} 新闻无数据")
            items = [
                DailyNews(
                    trade_date=d.trade_date,
                    title=d.title,
                    content=d.content,
                    source=d.source,
                    url=d.url,
                    code=d.code,
                    published_at=d.published_at,
                )
                for d in dtos
            ]
            count = await self.repo.save_daily_news(items)
            handle.synced_count = count
            logger.info(f"Synced {count} news items for {trade_date}")
            return SyncResult(
                synced=count, message=f"{trade_date} 新闻抓取成功，共 {count} 条"
            )
