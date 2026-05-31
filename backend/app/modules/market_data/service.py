from bisect import bisect_right
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pandas as pd
from loguru import logger
from ta.momentum import RSIIndicator
from ta.trend import MACD

from app.modules.market_data.models import DailyBar, DailyNews, DragonTigerList, LimitUpBoard, Stock
from app.modules.market_data.markets import passes_market_filter
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

    async def get_stock_quote(self, code: str) -> tuple[Quote, bool] | None:
        """Return (Quote, is_delayed). is_delayed=True when sourced from daily bar."""
        # Try realtime AKShare quote first
        try:
            quotes = await self.facade.get_realtime_quote([code])
            if quotes:
                return quotes[0], False
        except Exception as e:
            logger.warning(f"Realtime quote failed for {code}: {e}")

        # Fallback: construct quote from the latest daily bar (DB first, then facade)
        bar = await self.repo.get_latest_daily_bar(code)
        prev_bar = await self.repo.get_latest_daily_bar(code, before=bar.trade_date) if bar else None

        if not bar:
            # No DB data — go straight to the facade (we just confirmed DB is
            # empty, so self.get_daily_bars() would only re-query it for nothing).
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
            bars = await self.facade.get_daily_bars(code, start_date, end_date)
            if len(bars) >= 2:
                bars.sort(key=lambda b: b.trade_date)
                latest = bars[-1]
                prev = bars[-2]
                stock = await self.repo.get_stock(code)
                return Quote(
                    code=latest.code,
                    name=stock.name if stock else latest.code,
                    price=latest.close,
                    change=round(latest.close - prev.close, 2),
                    change_pct=round((latest.close - prev.close) / prev.close * 100, 2) if prev.close else 0.0,
                    volume=latest.volume,
                    amount=latest.amount,
                    open=latest.open,
                    high=latest.high,
                    low=latest.low,
                    prev_close=prev.close,
                ), True
            elif len(bars) == 1:
                latest = bars[0]
                stock = await self.repo.get_stock(code)
                # Single-bar branch: we have no prior close to compare against,
                # so leave prev_close as None rather than fabricating it from
                # latest.open (which would contradict change=0.0/change_pct=0.0).
                return Quote(
                    code=latest.code,
                    name=stock.name if stock else latest.code,
                    price=latest.close,
                    change=0.0,
                    change_pct=0.0,
                    volume=latest.volume,
                    amount=latest.amount,
                    open=latest.open,
                    high=latest.high,
                    low=latest.low,
                    prev_close=None,
                ), True
            return None

        prev_close = prev_bar.close if prev_bar else bar.open
        change = round(bar.close - prev_close, 2)
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0.0
        stock = await self.repo.get_stock(code)
        return Quote(
            code=bar.code,
            name=stock.name if stock else bar.code,
            price=bar.close,
            change=change,
            change_pct=change_pct,
            volume=bar.volume,
            amount=bar.amount,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            prev_close=prev_close,
        ), True

    async def get_stock_kline(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 120,
        period: str = "daily",
        *,
        local_only: bool = False,
        as_of_date: date | None = None,
    ) -> list[DailyBar]:
        # When `as_of_date` is set it overrides any explicit end_date so the
        # caller gets a strictly historical view (used by the screener
        # walk-forward backtest engine).
        if as_of_date is not None:
            end_date = as_of_date
        bars = await self.get_daily_bars(
            code, start_date, end_date, local_only=local_only
        )
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

    async def get_stock_analysis_summary(
        self, code: str, *, local_only: bool = False, as_of_date: date | None = None
    ) -> StockAnalysisSummaryOut | None:
        bars = await self.get_stock_kline(
            code, limit=60, local_only=local_only, as_of_date=as_of_date
        )
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
            ((latest_close - closes[-20]) / closes[-20] * 100)
            if len(closes) >= 20
            else None
        )

        latest_volume = volumes[-1]
        # Compare today's volume against the average of the PRIOR 5 sessions
        # (excluding today). Including today in the denominator dampens any
        # genuine breakout — a 2x volume spike would only register as ~1.67x.
        avg_volume_5d = sum(volumes[-6:-1]) / 5 if len(volumes) >= 6 else None
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
            **self._derive_limit_up_fields(code, bars),  # type: ignore[arg-type]
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
        *,
        as_of_date: date | None = None,
    ) -> StockScreenResultOut:
        screen_type = screen_type.lower().strip()
        params = params or StockScreenParams()
        stocks = await self.repo.get_stocks()
        # Restrict scan to stocks with local daily-bar data. Without this guard
        # we would call `facade.get_daily_bars` for every stock missing bars,
        # serializing 200+ remote requests and blocking the endpoint.
        codes_with_bars = await self.repo.get_codes_with_daily_bars()
        candidate_stocks = [s for s in stocks if s.code in codes_with_bars]
        matches: list[StockScreenItemOut] = []

        # In as-of-date mode (used by the walk-forward backtest engine) we
        # SKIP dragon_tiger / limit_up / news enrichment because those data
        # sources are "current state" decorators that cannot be reconstructed
        # for an arbitrary historical date and are not part of the matching
        # logic. The output preserves the same StockScreenItemOut shape with
        # empty enrichment fields.
        historical_mode = as_of_date is not None

        dragon_tiger_map: dict[str, DragonTigerList] = {}
        limit_up_map: dict[str, LimitUpBoard] = {}
        news_by_code: dict[str, list[str]] = {}

        if not historical_mode:
            latest_dragon_tiger_date = await self.repo.get_latest_trade_date_for_dragon_tiger()
            latest_limit_up_date = await self.repo.get_latest_trade_date_for_limit_up()
            latest_news_date = await self.repo.get_latest_trade_date_for_news()

            if latest_dragon_tiger_date:
                dragon_tiger_map = {
                    item.code: item
                    for item in await self.repo.get_dragon_tiger_list(latest_dragon_tiger_date)
                }
            if latest_limit_up_date:
                limit_up_map = {
                    item.code: item
                    for item in await self.repo.get_limit_up_board(latest_limit_up_date)
                }
            if latest_news_date:
                for item in await self.repo.get_daily_news(latest_news_date, limit=100):
                    if not item.code:
                        continue
                    news_by_code.setdefault(item.code, []).append(item.title)

        # Build recent-LHB lookup for the lhb_follow screener. For both live
        # and historical modes we look back ``lhb_lookback_days`` trading days
        # ending the day before the as-of date (or yesterday in live mode).
        lhb_recent: dict[str, dict] = {}
        if screen_type == "lhb_follow":
            lookback = (
                params.lhb_lookback_days
                if params.lhb_lookback_days is not None
                else 1
            )
            lookback = max(1, min(lookback, 20))
            if historical_mode and as_of_date is not None:
                end_d = as_of_date - timedelta(days=1)
                start_d = end_d - timedelta(days=lookback * 2 + 7)  # cushion for weekends
                rows = await self.repo.get_dragon_tiger_in_range(start_d, end_d)
            else:
                end_d = await self.repo.get_latest_trade_date_for_dragon_tiger()
                if end_d is not None:
                    start_d = end_d - timedelta(days=lookback * 2 + 7)
                    rows = await self.repo.get_dragon_tiger_in_range(start_d, end_d)
                else:
                    rows = []
            # Take the most recent ``lookback`` distinct trading dates and
            # aggregate per code (sum net_buy across rows on those dates).
            distinct_dates = sorted({r.trade_date for r in rows}, reverse=True)[:lookback]
            keep = set(distinct_dates)
            agg: dict[str, dict] = {}
            for r in rows:
                if r.trade_date not in keep:
                    continue
                cur = agg.get(r.code)
                net_yi = (r.net_buy or 0.0) / 1e8
                if cur is None:
                    agg[r.code] = {
                        "trade_date": r.trade_date,
                        "net_buy_yi": net_yi,
                        "reason": r.reason,
                    }
                else:
                    cur["net_buy_yi"] = cur["net_buy_yi"] + net_yi
                    # keep the most recent date
                    if r.trade_date > cur["trade_date"]:
                        cur["trade_date"] = r.trade_date
                        cur["reason"] = r.reason
            lhb_recent = agg

        for stock in candidate_stocks[: max(params.max_candidates, 1)]:
            # Apply market-segment + ST filter (default: all boards, no ST).
            if not passes_market_filter(
                stock.code, stock.name, params.markets, params.include_st
            ):
                continue
            analysis = await self.get_stock_analysis_summary(
                stock.code, local_only=True, as_of_date=as_of_date
            )
            if not analysis:
                continue

            match_reason = self._match_screen(
                screen_type, analysis, params, lhb_recent=lhb_recent
            )
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
                    consec_limit_up_days=analysis.consec_limit_up_days,
                    high_60d_ratio=analysis.high_60d_ratio,
                )
            )

        sorted_matches = self._sort_screen_matches(screen_type, matches)
        return StockScreenResultOut(
            screen_type=screen_type,
            total=len(sorted_matches),
            items=sorted_matches[: params.limit],
        )

    @staticmethod
    def _limit_up_threshold_pct(code: str) -> float:
        """A-share daily price-limit threshold for the given board prefix."""
        if not code:
            return 9.8
        head = code[:3]
        # 主板 10%, 创业板/科创板/北交所 20%. 北交所 codes are now `8x` and
        # newer `9x` (920xxx, 924xxx, etc.); historical `4x` codes share the
        # 20% rule. ST/*ST stocks have ±5% caps but are detected by name not
        # by code prefix — handled via the live name-based ST filter, not here.
        if head.startswith("300") or head.startswith("688") or code.startswith(("8", "4", "9")):
            return 19.8
        return 9.8

    def _derive_limit_up_fields(
        self, code: str, bars: list[DailyBar]
    ) -> dict[str, object]:
        """Derive the limit-up extension fields from a chronologically sorted
        bar list ending at the as-of bar. The returned dict mirrors the
        ``StockAnalysisSummaryOut`` extension fields.
        """
        threshold = self._limit_up_threshold_pct(code)
        n = len(bars)
        if n == 0:
            return {
                "pct_change_1d": None,
                "is_limit_up_today": None,
                "consec_limit_up_days": None,
                "open_gap_pct": None,
                "high_60d_ratio": None,
                "days_since_last_limit_up": None,
                "prior_consec_limit_up_days": None,
            }
        # Walk forward computing per-bar limit-up flags.
        is_zt: list[bool] = []
        for i, bar in enumerate(bars):
            if i == 0:
                is_zt.append(False)
                continue
            prev_close = bars[i - 1].close
            if prev_close <= 0:
                is_zt.append(False)
                continue
            chg = (bar.close - prev_close) / prev_close * 100
            is_zt.append(chg >= threshold)
        # Trailing streak.
        streak = 0
        for flag in reversed(is_zt):
            if flag:
                streak += 1
            else:
                break
        # Days since the most recent PRIOR limit-up (today's own zt does
        # not count — strategies like first_limit_up_low need to know how
        # long the stock was quiet before today's break-out).
        last_zt_idx: int | None = None
        for i in range(n - 2, -1, -1):
            if is_zt[i]:
                last_zt_idx = i
                break
        if last_zt_idx is None:
            days_since: int | None = None
            prior_streak: int | None = None
        else:
            days_since = (n - 1) - last_zt_idx
            # Reconstruct the streak that ENDED at last_zt_idx by walking
            # backward from there. ``zt_relay`` uses this to enforce
            # ``max_streak`` on the relayed name.
            ps = 0
            for j in range(last_zt_idx, -1, -1):
                if is_zt[j]:
                    ps += 1
                else:
                    break
            prior_streak = ps
        # Open gap.
        if n >= 2 and bars[-2].close > 0:
            open_gap_pct = (bars[-1].open - bars[-2].close) / bars[-2].close * 100
        else:
            open_gap_pct = None
        # 60-day high ratio (uses what we have). Uses intraday HIGH for the
        # rolling max — that's what 中国 A 股 traders refer to as "60 日高位",
        # not the closing high. Denominator stays at today's close.
        window = bars[-60:] if n >= 60 else bars
        max_high = max(b.high for b in window)
        high_60d_ratio = bars[-1].close / max_high if max_high > 0 else None
        # Today's pct change.
        if n >= 2 and bars[-2].close > 0:
            pct_change_1d: float | None = (
                (bars[-1].close - bars[-2].close) / bars[-2].close * 100
            )
        else:
            pct_change_1d = None
        return {
            "pct_change_1d": pct_change_1d,
            "is_limit_up_today": is_zt[-1],
            "consec_limit_up_days": streak,
            "open_gap_pct": open_gap_pct,
            "high_60d_ratio": high_60d_ratio,
            "days_since_last_limit_up": days_since,
            "prior_consec_limit_up_days": prior_streak,
        }

    def _analysis_from_bars(
        self, code: str, bars: list[DailyBar], as_of_date: date
    ) -> StockAnalysisSummaryOut | None:
        """In-memory equivalent of ``get_stock_analysis_summary`` for the
        walk-forward backtest engine. Operates on a pre-fetched bar list and
        an as-of date, slicing locally to the trailing 60 sessions.
        """
        sliced = [b for b in bars if b.trade_date <= as_of_date]
        if len(sliced) < 5:
            return None
        sliced = sorted(sliced, key=lambda b: b.trade_date)[-60:]
        closes = [bar.close for bar in sliced]
        volumes = [float(bar.volume) for bar in sliced]
        latest_close = closes[-1]
        ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else None
        ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
        rsi14, macd_value, macd_signal, macd_histogram = self._calculate_ta_metrics(closes)
        price_vs_ma5_pct = ((latest_close - ma5) / ma5 * 100) if ma5 else None
        price_vs_ma20_pct = ((latest_close - ma20) / ma20 * 100) if ma20 else None
        return_5d_pct = (
            ((latest_close - closes[-5]) / closes[-5] * 100) if len(closes) >= 5 else None
        )
        return_20d_pct = (
            ((latest_close - closes[-20]) / closes[-20] * 100) if len(closes) >= 20 else None
        )
        latest_volume = volumes[-1]
        avg_volume_5d = sum(volumes[-6:-1]) / 5 if len(volumes) >= 6 else None
        volume_ratio_5d = (latest_volume / avg_volume_5d) if avg_volume_5d else None
        trend_bias = self._determine_trend_bias(price_vs_ma5_pct, price_vs_ma20_pct, return_20d_pct)
        zt_fields = self._derive_limit_up_fields(code, sliced)
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
            summary="",
            signals=[],
            **zt_fields,  # type: ignore[arg-type]
        )

    def screen_with_prefetched_bars(
        self,
        screen_type: str,
        params: StockScreenParams,
        *,
        as_of_date: date,
        bars_by_code: dict[str, list[DailyBar]],
        name_by_code: dict[str, str],
        precomputed: dict[str, "PrecomputedScreenSeries"] | None = None,
        lhb_recent: dict[str, dict] | None = None,
    ) -> StockScreenResultOut:
        """Run the screener against an in-memory bar map. No DB queries.

        Used by the walk-forward backtest engine which already prefetches a
        full ``bars_by_code`` for every candidate over the simulation window;
        re-querying the DB per (rebalance_date, code) was the engine's main
        latency contributor.

        When ``precomputed`` is provided, indicator lookup is O(log N) per
        (code, as_of_date) instead of recomputing pandas-based RSI/MACD on
        each call. For daily-rebalance backtests over wide universes this
        cuts hundreds of thousands of TA invocations down to one per code.
        """
        screen_type = screen_type.lower().strip()
        candidate_codes = list(bars_by_code.keys())[: max(params.max_candidates, 1)]
        matches: list[StockScreenItemOut] = []
        for code in candidate_codes:
            name = name_by_code.get(code, code)
            # Apply market-segment + ST filter.
            if not passes_market_filter(
                code, name, params.markets, params.include_st
            ):
                continue
            if precomputed is not None and code in precomputed:
                analysis = precomputed[code].analysis_at(code, as_of_date)
            else:
                analysis = self._analysis_from_bars(code, bars_by_code[code], as_of_date)
            if not analysis:
                continue
            match_reason = self._match_screen(
                screen_type, analysis, params, lhb_recent=lhb_recent
            )
            if not match_reason:
                continue
            matches.append(
                StockScreenItemOut(
                    symbol=code,
                    name=name_by_code.get(code, code),
                    market="",
                    industry=None,
                    latest_close=analysis.latest_close,
                    return_5d_pct=analysis.return_5d_pct,
                    return_20d_pct=analysis.return_20d_pct,
                    volume_ratio_5d=analysis.volume_ratio_5d,
                    trend_bias=analysis.trend_bias,
                    match_reason=match_reason,
                    is_on_dragon_tiger=False,
                    is_limit_up_candidate=False,
                    hot_tags=[],
                    related_news_headlines=[],
                    consec_limit_up_days=analysis.consec_limit_up_days,
                    high_60d_ratio=analysis.high_60d_ratio,
                )
            )
        sorted_matches = self._sort_screen_matches(screen_type, matches)
        return StockScreenResultOut(
            screen_type=screen_type,
            total=len(sorted_matches),
            items=sorted_matches[: params.limit],
        )

    def precompute_screen_series(
        self, bars_by_code: dict[str, list[DailyBar]]
    ) -> dict[str, "PrecomputedScreenSeries"]:
        """Precompute per-code indicator vectors over the full bar history.

        For each code we sort bars chronologically and compute MA5/MA20/RSI14/
        MACD-histogram/5d-and-20d returns/5d volume ratio as full-length
        pandas Series (or None when too short). The returned struct supports
        fast point-in-time lookup via ``analysis_at(as_of_date)``.
        """
        out: dict[str, PrecomputedScreenSeries] = {}
        for code, bars in bars_by_code.items():
            sorted_bars = sorted(bars, key=lambda b: b.trade_date)
            if len(sorted_bars) < 5:
                continue
            out[code] = PrecomputedScreenSeries.build(
                code, sorted_bars, self._determine_trend_bias
            )
        return out


    @staticmethod
    def quote_timestamp() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _determine_trend_bias(
        price_vs_ma5_pct: float | None,
        price_vs_ma20_pct: float | None,
        return_20d_pct: float | None,
    ) -> str:
        # If any leg is missing we cannot honestly classify the trend — fall
        # back to "neutral" rather than letting `(None or 0)` silently flip
        # the comparison and emit a misleading bullish/bearish label.
        if (
            price_vs_ma5_pct is None
            or price_vs_ma20_pct is None
            or return_20d_pct is None
        ):
            return "neutral"
        bullish = (
            price_vs_ma5_pct > 0
            and price_vs_ma20_pct > 0
            and return_20d_pct > 0
        )
        bearish = (
            price_vs_ma5_pct < 0
            and price_vs_ma20_pct < 0
            and return_20d_pct < 0
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

        # MACD(12, 26, 9) needs ~34 bars of warmup before the histogram
        # stabilizes. Below 26 we cannot even seed the slow EMA, so return
        # None for the MACD trio rather than emit unreliable values.
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
        *,
        lhb_recent: dict[str, dict] | None = None,
    ) -> str | None:
        if screen_type == "strong_uptrend":
            min_return_20d_pct = (
                params.min_return_20d_pct
                if params.min_return_20d_pct is not None
                else 5
            )
            if (
                analysis.trend_bias == "bullish"
                and analysis.return_20d_pct is not None
                and analysis.return_20d_pct >= min_return_20d_pct
                and analysis.rsi14 is not None
                and analysis.rsi14 >= 50
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
                analysis.volume_ratio_5d is not None
                and analysis.volume_ratio_5d >= min_volume_ratio
                and analysis.return_5d_pct is not None
                and analysis.return_5d_pct > min_return_5d_pct
            ):
                # MACD positivity is now an opt-in filter. Historically this
                # screener silently required macd_histogram > 0, which often
                # produced empty result sets on otherwise-valid breakouts.
                if params.require_macd_positive and (
                    analysis.macd_histogram is None
                    or analysis.macd_histogram <= 0
                ):
                    return None
                return f"量比超过 {min_volume_ratio:.2f}x 且近5日表现转强，具备突破观察价值"
            return None

        if screen_type == "pullback_watch":
            max_return_5d_pct = (
                params.max_return_5d_pct if params.max_return_5d_pct is not None else 1
            )
            if (
                analysis.trend_bias == "bullish"
                and analysis.price_vs_ma20_pct is not None
                and analysis.price_vs_ma20_pct > 0
                and analysis.return_5d_pct is not None
                and -3 <= analysis.return_5d_pct <= max_return_5d_pct
            ):
                return f"中期趋势未坏，近5日回撤控制在 {max_return_5d_pct:.1f}% 内，可继续跟踪"
            return None

        if screen_type == "first_limit_up_low":
            # 低位首板：今日涨停 + 前 N 日没有涨停 + 当前价不在 60 日高位
            if not analysis.is_limit_up_today:
                return None
            quiet_required = (
                params.min_quiet_days if params.min_quiet_days is not None else 20
            )
            since = analysis.days_since_last_limit_up
            # ``days_since_last_limit_up`` is the offset to the *previous*
            # limit-up bar; today's own limit-up was registered before the
            # field was read. ``None`` means no prior streak in the window —
            # treat as fresh enough.
            if since is not None and since < quiet_required:
                return None
            high_ratio_cap = (
                params.max_high_60d_ratio
                if params.max_high_60d_ratio is not None
                else 0.85
            )
            if (
                analysis.high_60d_ratio is not None
                and analysis.high_60d_ratio > high_ratio_cap
            ):
                return None
            return f"低位首板：当前价仅为60日高的 {(analysis.high_60d_ratio or 0)*100:.1f}%，{quiet_required}日内无前板"

        if screen_type == "leader_streak":
            # 龙头连板：连板 ≥ N 天 + 量能放大 + 趋势偏强
            min_streak = params.min_streak if params.min_streak is not None else 3
            min_volume_ratio = (
                params.min_volume_ratio if params.min_volume_ratio is not None else 1.2
            )
            if (
                analysis.consec_limit_up_days is None
                or analysis.consec_limit_up_days < min_streak
            ):
                return None
            if (
                analysis.volume_ratio_5d is None
                or analysis.volume_ratio_5d < min_volume_ratio
            ):
                return None
            if analysis.trend_bias != "bullish":
                return None
            return (
                f"龙头连板：已连板 {analysis.consec_limit_up_days} 天，量比 "
                f"{analysis.volume_ratio_5d:.2f}x 配合"
            )

        if screen_type == "zt_relay":
            # 涨停接力：昨日涨停 + 今日不能跳空过高 + 今日量比保持 + 板数不过高
            if analysis.consec_limit_up_days is None:
                return None
            if analysis.is_limit_up_today:
                return None  # already in board, not a relay candidate
            if (
                analysis.days_since_last_limit_up is None
                or analysis.days_since_last_limit_up != 1
            ):
                return None
            # max_streak now works against the prior streak (days_since==1
            # means yesterday was zt; prior_consec is that streak's length).
            max_streak = params.max_streak if params.max_streak is not None else 3
            if (
                analysis.prior_consec_limit_up_days is not None
                and analysis.prior_consec_limit_up_days > max_streak
            ):
                return None
            max_gap = (
                params.max_open_gap_pct
                if params.max_open_gap_pct is not None
                else 5.0
            )
            # Reject gap-downs: a relay setup wants positive gap-up. Allow
            # exactly 0 (flat open) but reject negative gaps.
            if analysis.open_gap_pct is None or analysis.open_gap_pct < 0:
                return None
            if analysis.open_gap_pct > max_gap:
                return None
            min_volume_ratio = (
                params.min_volume_ratio if params.min_volume_ratio is not None else 1.0
            )
            if (
                analysis.volume_ratio_5d is None
                or analysis.volume_ratio_5d < min_volume_ratio
            ):
                return None
            prior_streak_text = (
                f"前板 {analysis.prior_consec_limit_up_days} 连板，"
                if analysis.prior_consec_limit_up_days
                else ""
            )
            return (
                f"涨停接力：{prior_streak_text}今日开盘缺口 "
                f"{(analysis.open_gap_pct or 0):+.2f}%，"
                f"量比 {analysis.volume_ratio_5d:.2f}x"
            )

        if screen_type == "lhb_follow":
            # 龙虎榜跟买：最近 N 日上榜且净买入达到阈值，今日跟随介入。
            if lhb_recent is None:
                return None
            info = lhb_recent.get(analysis.symbol)
            if info is None:
                return None
            net_buy_yi = info.get("net_buy_yi")
            if net_buy_yi is None:
                return None
            min_yi = (
                params.min_net_buy_yi
                if params.min_net_buy_yi is not None
                else 0.3
            )
            if net_buy_yi < min_yi:
                return None
            # 避开高开过多的跟买（次日大幅高开易破位）。当 open_gap_pct 缺失时
            # 不强制要求，避免在历史回测早期窗口因数据不足而误杀。
            max_gap = (
                params.max_open_gap_pct
                if params.max_open_gap_pct is not None
                else 5.0
            )
            if (
                analysis.open_gap_pct is not None
                and analysis.open_gap_pct > max_gap
            ):
                return None
            reason_text = info.get("reason") or "上榜"
            lhb_date = info.get("trade_date")
            date_text = f"{lhb_date}" if lhb_date is not None else "近日"
            return (
                f"龙虎榜跟买：{date_text} {reason_text}，"
                f"净买入 {net_buy_yi:.2f} 亿"
            )

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

        if screen_type == "first_limit_up_low":
            # Lowest 60d-high ratio first (most depressed) then highest volume.
            return sorted(
                matches,
                key=lambda item: (
                    (item.high_60d_ratio if item.high_60d_ratio is not None else 1.0),
                    -(item.volume_ratio_5d or 0),
                ),
            )

        if screen_type == "leader_streak":
            # Streak length is the dominant signal; longer streak = stronger leader.
            return sorted(
                matches,
                key=lambda item: (
                    (item.consec_limit_up_days or 0),
                    (item.return_5d_pct or 0),
                    (item.volume_ratio_5d or 0),
                ),
                reverse=True,
            )

        if screen_type == "zt_relay":
            return sorted(
                matches,
                key=lambda item: (
                    (item.volume_ratio_5d or 0),
                    (item.return_20d_pct or 0),
                ),
                reverse=True,
            )

        if screen_type == "lhb_follow":
            # 净买入额排序无法从 StockScreenItemOut 直接拿到，但 match_reason
            # 文本已编入数值，先按 5 日量能 + 20 日动量近似排序，把最有承接量的
            # 票排前面。
            return sorted(
                matches,
                key=lambda item: (
                    (item.volume_ratio_5d or 0),
                    (item.return_20d_pct or 0),
                ),
                reverse=True,
            )

        return sorted(
            matches,
            key=lambda item: ((item.return_20d_pct or 0), (item.return_5d_pct or 0)),
            reverse=True,
        )

    async def get_daily_bars(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
        *,
        local_only: bool = False,
    ) -> list[DailyBar]:
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=365)

        bars = await self.repo.get_daily_bars(code, start_date, end_date)
        if bars:
            return bars

        if local_only:
            return []

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


@dataclass
class PrecomputedScreenSeries:
    """Vectorized indicators for a single code, indexed by sorted dates.

    All series are aligned with ``dates``. ``analysis_at`` finds the latest
    bar with ``trade_date <= as_of`` via binary search and reads each
    indicator at that index, producing a ``StockAnalysisSummaryOut`` without
    re-running pandas/TA on per-call subsets.
    """

    dates: list[date]
    opens: list[float]
    closes: list[float]
    volumes: list[float]
    ma5: list[float | None]
    ma20: list[float | None]
    rsi14: list[float | None]
    macd_hist: list[float | None]
    return_5d: list[float | None]
    return_20d: list[float | None]
    vol_ratio_5d: list[float | None]
    trend_bias: list[str]
    pct_change_1d: list[float | None]
    is_limit_up: list[bool]
    consec_limit_up: list[int]
    open_gap_pct: list[float | None]
    high_60d_ratio: list[float | None]
    days_since_last_zt: list[int | None]
    # Streak that ended at the last zt bar PRIOR to index i (None when no
    # prior zt exists).
    prior_consec_limit_up: list[int | None]

    @staticmethod
    def _limit_up_threshold_pct(code: str) -> float:
        """A-share daily price-limit thresholds, by board prefix.

        - 300xxx (创业板) and 688xxx (科创板) and 8/4xxx (北交所): 20% (post-2020)
        - 6xxxxx, 0xxxxx, 002xxx (主板/中小板): 10%
        Using a 0.2 pct tolerance ('reach' rather than 'exact') so a 9.97%
        close still counts — A-share quote ticks frequently produce closes
        slightly under the theoretical limit.
        """
        if not code:
            return 9.8
        head = code[:3]
        if head.startswith("300") or head.startswith("688") or code.startswith(("8", "4", "9")):
            return 19.8
        return 9.8

    @classmethod
    def build(
        cls,
        code: str,
        sorted_bars: list[DailyBar],
        trend_fn,  # type: ignore[no-untyped-def]
    ) -> "PrecomputedScreenSeries":
        n = len(sorted_bars)
        dates = [b.trade_date for b in sorted_bars]
        opens = [float(b.open) for b in sorted_bars]
        closes = [float(b.close) for b in sorted_bars]
        volumes = [float(b.volume) for b in sorted_bars]

        close_series = pd.Series(closes, dtype="float64")
        # Rolling means (NaN where window is short).
        ma5_arr = close_series.rolling(window=5, min_periods=5).mean()
        ma20_arr = close_series.rolling(window=20, min_periods=20).mean()
        # 5/20-day returns: match the legacy `closes[-5]`/`closes[-20]`
        # semantics — that's an offset of 4/19 sessions from the latest bar
        # (Python negative indexing is 1-based from the end). Using
        # pct_change(5) here would silently shift signals by one bar.
        ret5_arr = close_series.pct_change(periods=4) * 100
        ret20_arr = close_series.pct_change(periods=19) * 100
        ret1_arr = close_series.pct_change(periods=1) * 100

        # Volume ratio = today / mean(prev 5). Shift so the rolling mean
        # excludes the current bar.
        vol_series = pd.Series(volumes, dtype="float64")
        prior5_mean = vol_series.shift(1).rolling(window=5, min_periods=5).mean()
        vol_ratio = vol_series / prior5_mean

        # 60-day rolling intraday-HIGH (inclusive of today). Used by
        # first_limit_up_low. Using intraday `high` rather than `close` matches
        # how traders look at "60 日高位"; denominator stays close-based.
        high_series = pd.Series(
            [float(b.high) for b in sorted_bars], dtype="float64"
        )
        high60_arr = high_series.rolling(window=60, min_periods=5).max()
        high60_ratio = close_series / high60_arr

        # Open gap relative to prior close: (open - prev_close) / prev_close.
        prev_close = close_series.shift(1)
        open_series = pd.Series(opens, dtype="float64")
        gap_arr = (open_series - prev_close) / prev_close * 100

        # RSI / MACD: TA library expects sufficient history. We compute on
        # the full series once.
        if n >= 14:
            rsi_series = RSIIndicator(close_series, window=14).rsi()
        else:
            rsi_series = pd.Series([float("nan")] * n)
        if n >= 26:
            macd_diff_series = MACD(close_series).macd_diff()
        else:
            macd_diff_series = pd.Series([float("nan")] * n)

        def _to_list(s: pd.Series) -> list[float | None]:
            return [None if pd.isna(v) else float(v) for v in s]

        ma5_list = _to_list(ma5_arr)
        ma20_list = _to_list(ma20_arr)
        rsi_list = _to_list(rsi_series)
        macd_list = _to_list(macd_diff_series)
        ret5_list = _to_list(ret5_arr)
        ret20_list = _to_list(ret20_arr)
        vol_list = _to_list(vol_ratio)
        ret1_list = _to_list(ret1_arr)
        high60_list = _to_list(high60_ratio)
        gap_list = _to_list(gap_arr)

        # Limit-up state per bar: pct_change_1d >= board threshold.
        threshold = cls._limit_up_threshold_pct(code)
        is_zt: list[bool] = [
            (r is not None and r >= threshold) for r in ret1_list
        ]
        # Consecutive limit-up days (i.e. trailing streak ending at i).
        consec: list[int] = [0] * n
        for i in range(n):
            if is_zt[i]:
                consec[i] = (consec[i - 1] + 1) if i > 0 else 1
            else:
                consec[i] = 0
        # Days since the last limit-up (None if never seen yet).
        days_since: list[int | None] = [None] * n
        prior_streak: list[int | None] = [None] * n
        last_zt_idx: int | None = None
        last_streak_end: int | None = None  # streak length of the most recent zt bar
        for i in range(n):
            if last_zt_idx is None:
                days_since[i] = None
                prior_streak[i] = None
            else:
                days_since[i] = i - last_zt_idx
                prior_streak[i] = last_streak_end
            if is_zt[i]:
                last_zt_idx = i
                last_streak_end = consec[i]

        # trend_bias depends on price-vs-MA5/20 and 20d return; precompute it
        # using the same helper as the live screener for behavioral parity.
        trend: list[str] = []
        for i in range(n):
            ma5_v = ma5_list[i]
            ma20_v = ma20_list[i]
            r20 = ret20_list[i]
            pv5 = (closes[i] - ma5_v) / ma5_v * 100 if ma5_v else None
            pv20 = (closes[i] - ma20_v) / ma20_v * 100 if ma20_v else None
            trend.append(trend_fn(pv5, pv20, r20))

        return cls(
            dates=dates,
            opens=opens,
            closes=closes,
            volumes=volumes,
            ma5=ma5_list,
            ma20=ma20_list,
            rsi14=rsi_list,
            macd_hist=macd_list,
            return_5d=ret5_list,
            return_20d=ret20_list,
            vol_ratio_5d=vol_list,
            trend_bias=trend,
            pct_change_1d=ret1_list,
            is_limit_up=is_zt,
            consec_limit_up=consec,
            open_gap_pct=gap_list,
            high_60d_ratio=high60_list,
            days_since_last_zt=days_since,
            prior_consec_limit_up=prior_streak,
        )

    def analysis_at(self, code: str, as_of: date) -> StockAnalysisSummaryOut | None:
        """Return point-in-time analysis using the latest bar <= ``as_of``."""
        # bisect_right - 1 gives the largest index with date <= as_of.
        idx = bisect_right(self.dates, as_of) - 1
        if idx < 0:
            return None
        ma5_v = self.ma5[idx]
        ma20_v = self.ma20[idx]
        latest_close = self.closes[idx]
        pv5 = (latest_close - ma5_v) / ma5_v * 100 if ma5_v else None
        pv20 = (latest_close - ma20_v) / ma20_v * 100 if ma20_v else None
        return StockAnalysisSummaryOut(
            symbol=code,
            latest_close=latest_close,
            ma5=ma5_v,
            ma20=ma20_v,
            rsi14=self.rsi14[idx],
            macd=None,
            macd_signal=None,
            macd_histogram=self.macd_hist[idx],
            price_vs_ma5_pct=pv5,
            price_vs_ma20_pct=pv20,
            return_5d_pct=self.return_5d[idx],
            return_20d_pct=self.return_20d[idx],
            volume_ratio_5d=self.vol_ratio_5d[idx],
            trend_bias=self.trend_bias[idx],
            summary="",
            signals=[],
            pct_change_1d=self.pct_change_1d[idx],
            is_limit_up_today=self.is_limit_up[idx],
            consec_limit_up_days=self.consec_limit_up[idx],
            open_gap_pct=self.open_gap_pct[idx],
            high_60d_ratio=self.high_60d_ratio[idx],
            days_since_last_limit_up=self.days_since_last_zt[idx],
            prior_consec_limit_up_days=self.prior_consec_limit_up[idx],
        )
