"""Backtest engines.

This module contains:
- A simple double-MA crossover backtest on a single stock
  (:meth:`BacktestService.run_simple_backtest`), already shipped.
- A walk-forward screener-based portfolio backtest engine
  (:meth:`BacktestService.run_screener_backtest`) that simulates running a
  factor screener on a periodic schedule and holding the picks.

Both engines are pure computation — no DB writes, no new tables.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta

from app.core.exceptions import NotFoundError
from app.modules.backtests.schemas import (
    AttributionOut,
    BacktestRequest,
    BacktestResult,
    BacktestTrade,
    CostBreakdown,
    DrawdownPoint,
    EquityPoint,
    HoldingItem,
    HoldingSnapshot,
    MarketCapBucket,
    MonthlyReturn,
    RebalanceTradeReason,
    ScreenerBacktestRequest,
    ScreenerBacktestResult,
    ScreenerBacktestTrade,
    SectorWeight,
    YearlyReturn,
)
from app.modules.market_data.models import DailyBar
from app.modules.market_data.markets import passes_market_filter
from app.modules.market_data.schemas import StockScreenParams
from app.modules.market_data.service import MarketDataService

TRADING_DAYS_PER_YEAR = 252


def _sma(values: list[float], period: int, idx: int) -> float | None:
    """Simple moving average ending at index `idx` (inclusive)."""
    if idx + 1 < period:
        return None
    window = values[idx + 1 - period : idx + 1]
    return sum(window) / period


class BacktestService:
    def __init__(self, market_data: MarketDataService | None = None) -> None:
        self.market_data = market_data or MarketDataService()

    async def run_simple_backtest(self, req: BacktestRequest) -> BacktestResult:
        bars = await self.market_data.get_daily_bars(req.code, req.start_date, req.end_date)

        if len(bars) < req.slow_period + 2:
            raise NotFoundError("Insufficient bars for backtest")

        # Sort bars chronologically (defensive — repo may return DESC).
        bars = sorted(bars, key=lambda b: b.trade_date)

        closes = [float(b.close) for b in bars]
        opens = [float(b.open) for b in bars]
        dates = [b.trade_date for b in bars]
        n = len(bars)

        fast_smas: list[float | None] = [_sma(closes, req.fast_period, i) for i in range(n)]
        slow_smas: list[float | None] = [_sma(closes, req.slow_period, i) for i in range(n)]

        cash = float(req.initial_capital)
        shares = 0
        entry_date = None
        entry_price = 0.0
        trades: list[BacktestTrade] = []
        equity_curve: list[EquityPoint] = []

        for i in range(n):
            signal: str | None = None  # "BUY" | "SELL"
            if i > 0:
                f_now, s_now = fast_smas[i], slow_smas[i]
                f_prev, s_prev = fast_smas[i - 1], slow_smas[i - 1]
                if (
                    f_now is not None
                    and s_now is not None
                    and f_prev is not None
                    and s_prev is not None
                ):
                    crossed_up = f_prev <= s_prev and f_now > s_now
                    crossed_down = f_prev >= s_prev and f_now < s_now
                    if crossed_up and shares == 0:
                        signal = "BUY"
                    elif crossed_down and shares > 0:
                        signal = "SELL"

            # Execute next-bar open (or current close fallback) on signal day.
            if signal == "BUY":
                exec_price = opens[i + 1] if i + 1 < n else closes[i]
                exec_date = dates[i + 1] if i + 1 < n else dates[i]
                lots = int((cash / exec_price) // 100)
                qty = lots * 100
                if qty > 0:
                    cash -= qty * exec_price
                    shares = qty
                    entry_date = exec_date
                    entry_price = exec_price
            elif signal == "SELL" and shares > 0:
                exec_price = opens[i + 1] if i + 1 < n else closes[i]
                exec_date = dates[i + 1] if i + 1 < n else dates[i]
                cash += shares * exec_price
                ret_pct = (exec_price - entry_price) / entry_price * 100
                holding_days = (exec_date - entry_date).days if entry_date else 0
                trades.append(
                    BacktestTrade(
                        entry_date=entry_date,
                        entry_price=round(entry_price, 4),
                        exit_date=exec_date,
                        exit_price=round(exec_price, 4),
                        return_pct=round(ret_pct, 2),
                        holding_days=holding_days,
                    )
                )
                shares = 0
                entry_date = None
                entry_price = 0.0

            # Mark equity at end of day (using current bar's close).
            equity = cash + shares * closes[i]
            equity_curve.append(EquityPoint(date=dates[i], value=round(equity, 2)))

        # Force-close any open position at last close.
        if shares > 0 and entry_date is not None:
            exit_price = closes[-1]
            exit_date = dates[-1]
            cash += shares * exit_price
            ret_pct = (exit_price - entry_price) / entry_price * 100
            holding_days = (exit_date - entry_date).days
            trades.append(
                BacktestTrade(
                    entry_date=entry_date,
                    entry_price=round(entry_price, 4),
                    exit_date=exit_date,
                    exit_price=round(exit_price, 4),
                    return_pct=round(ret_pct, 2),
                    holding_days=holding_days,
                )
            )
            shares = 0

        final_equity = cash  # all positions closed
        total_return_pct = (final_equity - req.initial_capital) / req.initial_capital * 100

        num_days = (req.end_date - req.start_date).days
        if num_days >= 30:
            annualized = total_return_pct * 365 / num_days
            annualized_return_pct: float | None = round(annualized, 2)
        else:
            annualized_return_pct = None

        if trades:
            wins = sum(1 for t in trades if t.return_pct > 0)
            win_rate_pct = wins / len(trades) * 100
        else:
            win_rate_pct = 0.0

        # Max drawdown over equity curve.
        peak = float("-inf")
        max_dd = 0.0
        for pt in equity_curve:
            if pt.value > peak:
                peak = pt.value
            if peak > 0:
                dd = (peak - pt.value) / peak * 100
                if dd > max_dd:
                    max_dd = dd

        return BacktestResult(
            code=req.code,
            strategy=req.strategy,
            start_date=req.start_date,
            end_date=req.end_date,
            total_return_pct=round(total_return_pct, 2),
            annualized_return_pct=annualized_return_pct,
            win_rate_pct=round(win_rate_pct, 2),
            max_drawdown_pct=round(max_dd, 2),
            trade_count=len(trades),
            final_equity=round(final_equity, 2),
            initial_capital=round(float(req.initial_capital), 2),
            trades=trades,
            equity_curve=equity_curve,
        )

    # ------------------------------------------------------------------
    # Screener walk-forward backtest engine
    # ------------------------------------------------------------------

    async def run_screener_backtest(self, req: ScreenerBacktestRequest) -> ScreenerBacktestResult:
        """Walk-forward simulation: run a screener on a schedule and hold the picks.

        The engine builds the full trading-day grid from the union of all bars
        within ``[start_date, end_date]``, computes rebalance anchors based on
        ``req.rebalance``, and steps day-by-day applying intraday risk-control
        exits, end-of-day mark-to-market, and rebalance trades that execute at
        the *next* trading day's open price.

        T+1 invariant: a code purchased on day d cannot be sold on day d
        (tracked via ``entry_dates[code]``). Intraday SL/TP signals always
        check ``entry_date < today`` so a freshly-acquired position is immune
        to same-day exits.

        See the project brief for full semantics around suspended stocks,
        cost application, score weighting and benchmark construction.
        """
        # Resolve full universe & their bars in one shot.
        codes_with_bars = await self.market_data.repo.get_codes_with_daily_bars()
        # Restrict to listed stocks (with names) so the output has them.
        stocks = await self.market_data.repo.get_stocks()
        name_by_code: dict[str, str] = {s.code: s.name for s in stocks}
        candidate_codes = [c for c in codes_with_bars if c in name_by_code]

        # Apply market-segment + ST filter at candidate stage so we don't
        # prefetch / precompute bars for excluded boards.
        _override = req.screen_params_override
        _markets = _override.markets if _override is not None else None
        _include_st = _override.include_st if _override is not None else False
        if _markets or not _include_st:
            candidate_codes = [
                c
                for c in candidate_codes
                if passes_market_filter(c, name_by_code.get(c), _markets, _include_st)
            ]

        # We need a comfortable window prior to start_date so the screener has
        # 20 bars of history available on the very first rebalance day. Pull
        # bars from start_date - 60 calendar days through end_date.
        prefetch_start = req.start_date - timedelta(days=60)
        bars_by_code: dict[
            str, list[DailyBar]
        ] = await self.market_data.repo.get_daily_bars_for_codes(
            candidate_codes, prefetch_start, req.end_date
        )
        # Drop codes with no data in the window.
        bars_by_code = {c: bars for c, bars in bars_by_code.items() if bars}

        # Build per-code lookup (date -> bar) and trading-day list within
        # [start_date, end_date].
        bar_index: dict[str, dict[date, DailyBar]] = {}
        all_dates: set[date] = set()
        for code, bars in bars_by_code.items():
            bar_index[code] = {b.trade_date: b for b in bars}
            for b in bars:
                if req.start_date <= b.trade_date <= req.end_date:
                    all_dates.add(b.trade_date)

        trading_days: list[date] = sorted(all_dates)
        if not trading_days:
            raise NotFoundError("No trading days with bars in the requested range")

        rebalance_days = _compute_rebalance_dates(trading_days, req.rebalance)

        # Cache: rebalance_date -> [(code, score)] picks ordered by screen rank.
        screener_cache: dict[date, list[tuple[str, float]]] = {}
        params = req.screen_params_override or StockScreenParams()
        # Ensure we get enough picks to fall back from after filtering.
        params = params.model_copy(update={"limit": max(params.limit, req.top_n * 3)})

        # NOTE (perf): screen the universe in-memory using the already-
        # prefetched ``bars_by_code`` map. This avoids ~N_codes × N_rebalances
        # round-trips through ``MarketDataService.screen_stocks`` -> repo,
        # which previously dominated the engine latency (~40s for 6mo windows
        # caused the front-end dev proxy to time out).
        # Precompute indicator series per code once over the full window.
        # For daily-rebalance backtests this turns ~N_codes × N_rebalances
        # pandas/TA invocations into one per code, then O(log N) point-in-
        # time lookups per rebalance.
        precomputed = self.market_data.precompute_screen_series(bars_by_code)

        # For lhb_follow, prefetch the full LHB range once and bucket by date
        # so we can build per-rebalance lhb_recent maps without re-querying.
        lhb_by_date: dict[date, dict[str, dict]] = {}
        if req.screen_type == "lhb_follow" and trading_days:
            lhb_lookback = (
                params.lhb_lookback_days
                if params.lhb_lookback_days is not None
                else 1
            )
            lhb_lookback = max(1, min(lhb_lookback, 20))
            lhb_start = trading_days[0] - timedelta(days=lhb_lookback * 2 + 7)
            lhb_end = trading_days[-1]
            lhb_rows = await self.market_data.repo.get_dragon_tiger_in_range(
                lhb_start, lhb_end
            )
            for r in lhb_rows:
                bucket = lhb_by_date.setdefault(r.trade_date, {})
                cur = bucket.get(r.code)
                net_yi = (r.net_buy or 0.0) / 1e8
                if cur is None:
                    bucket[r.code] = {
                        "trade_date": r.trade_date,
                        "net_buy_yi": net_yi,
                        "reason": r.reason,
                    }
                else:
                    cur["net_buy_yi"] += net_yi

        # Map every trading_day to the list of preceding trading_days within
        # ``lhb_lookback`` sessions for fast per-rebalance aggregation.
        trading_day_index: dict[date, int] = {d: i for i, d in enumerate(trading_days)}

        def _lhb_recent_for(rday: date) -> dict[str, dict]:
            if not lhb_by_date or req.screen_type != "lhb_follow":
                return {}
            lookback = (
                params.lhb_lookback_days
                if params.lhb_lookback_days is not None
                else 1
            )
            lookback = max(1, min(lookback, 20))
            idx = trading_day_index.get(rday)
            if idx is None or idx == 0:
                return {}
            window = trading_days[max(0, idx - lookback) : idx]  # excl. rday
            agg: dict[str, dict] = {}
            for d in window:
                day_map = lhb_by_date.get(d) or {}
                for code, info in day_map.items():
                    cur = agg.get(code)
                    if cur is None:
                        agg[code] = {
                            "trade_date": info["trade_date"],
                            "net_buy_yi": info["net_buy_yi"],
                            "reason": info.get("reason"),
                        }
                    else:
                        cur["net_buy_yi"] += info["net_buy_yi"]
                        if info["trade_date"] > cur["trade_date"]:
                            cur["trade_date"] = info["trade_date"]
                            cur["reason"] = info.get("reason")
            return agg

        for rday in rebalance_days:
            res = self.market_data.screen_with_prefetched_bars(
                req.screen_type,
                params,
                as_of_date=rday,
                bars_by_code=bars_by_code,
                name_by_code=name_by_code,
                precomputed=precomputed,
                lhb_recent=_lhb_recent_for(rday),
            )
            screener_cache[rday] = [
                (item.symbol, max(0.0, item.return_20d_pct or 0.0)) for item in res.items
            ]

        # Engine state.
        cash = float(req.initial_capital)
        holdings: dict[str, int] = {}  # code -> shares
        entry_dates: dict[str, date] = {}
        entry_prices: dict[str, float] = {}  # effective entry price (after costs) for return calc
        # Per-position raw entry exec price (for SL/TP gating)
        raw_entry_prices: dict[str, float] = {}
        # Last known close for mark-to-market when a stock is suspended.
        last_known_close: dict[str, float] = {}

        equity_curve: list[EquityPoint] = []
        drawdown_curve: list[DrawdownPoint] = []
        trades: list[ScreenerBacktestTrade] = []
        holdings_history: list[HoldingSnapshot] = []

        total_commission = 0.0
        total_stamp = 0.0
        total_slippage = 0.0

        commission = req.commission_rate
        stamp = req.stamp_duty_rate
        slip = req.slippage_rate
        # Aggregate ``fee_bps`` shorthand: front-end forms only collect a
        # single fees field, so split it 50/50 between commission and
        # slippage. Stamp duty stays on its regulatory schedule.
        if req.fee_bps is not None:
            half = (req.fee_bps / 10_000) / 2
            commission = half
            slip = half
        # ``stop_profit_pct`` is an alias for ``take_profit_pct`` accepted
        # from front-end forms.
        take_profit_pct = (
            req.take_profit_pct if req.take_profit_pct is not None else req.stop_profit_pct
        )

        def _bar_for(code: str, dt: date) -> DailyBar | None:
            return bar_index.get(code, {}).get(dt)

        def _next_open(code: str, t_idx: int) -> tuple[date | None, float | None]:
            """Find next trading day for ``code`` strictly after ``t_idx``.

            Returns (date, open_price) — the per-stock next bar may differ
            from the universe-level next trading day if the stock is
            suspended on that day.
            """
            for j in range(t_idx + 1, len(trading_days)):
                bar = _bar_for(code, trading_days[j])
                if bar is not None:
                    return bar.trade_date, float(bar.open)
            return None, None

        def _execute_buy(code: str, exec_date: date, exec_price: float, shares: int) -> bool:
            nonlocal cash, total_commission, total_slippage
            if shares <= 0 or exec_price <= 0:
                return False
            gross = shares * exec_price
            fee_commission = gross * commission
            fee_slippage = gross * slip
            cost = gross + fee_commission + fee_slippage
            if cost > cash + 1e-9:
                return False
            cash -= cost
            total_commission += fee_commission
            total_slippage += fee_slippage
            holdings[code] = holdings.get(code, 0) + shares
            entry_dates[code] = exec_date
            raw_entry_prices[code] = exec_price
            # Effective entry basis (per share) including buy-side costs.
            entry_prices[code] = cost / shares
            return True

        def _execute_sell(
            code: str,
            exec_date: date,
            exec_price: float,
            shares: int,
            reason: RebalanceTradeReason,
        ) -> None:
            nonlocal cash, total_commission, total_stamp, total_slippage
            if shares <= 0 or exec_price <= 0:
                return
            gross = shares * exec_price
            fee_commission = gross * commission
            fee_stamp = gross * stamp
            fee_slippage = gross * slip
            proceeds = gross - fee_commission - fee_stamp - fee_slippage
            cash += proceeds
            total_commission += fee_commission
            total_stamp += fee_stamp
            total_slippage += fee_slippage

            entry_basis = entry_prices.get(code, exec_price)
            effective_exit_per_share = proceeds / shares
            ret_pct = (effective_exit_per_share - entry_basis) / entry_basis * 100
            ent_dt = entry_dates.get(code, exec_date)
            trades.append(
                ScreenerBacktestTrade(
                    code=code,
                    name=name_by_code.get(code, code),
                    entry_date=ent_dt,
                    entry_price=round(entry_basis, 4),
                    exit_date=exec_date,
                    exit_price=round(effective_exit_per_share, 4),
                    shares=shares,
                    return_pct=round(ret_pct, 2),
                    holding_days=(exec_date - ent_dt).days,
                    exit_reason=reason,
                )
            )
            # Reduce / clear holding.
            remaining = holdings.get(code, 0) - shares
            if remaining <= 0:
                holdings.pop(code, None)
                entry_dates.pop(code, None)
                entry_prices.pop(code, None)
                raw_entry_prices.pop(code, None)
            else:
                holdings[code] = remaining

        # Main daily loop.
        for t_idx, t in enumerate(trading_days):
            # (a) INTRADAY exits — SL / TP. Check every held code with a bar
            #     on t whose entry_date < t (T+1 + same-day buy guard).
            for code in list(holdings.keys()):
                if entry_dates.get(code, t) >= t:
                    continue  # bought today (next-open fills set entry_date=t),
                    # skip intraday signals.
                bar = _bar_for(code, t)
                if bar is None:
                    continue
                raw_entry = raw_entry_prices.get(code)
                if raw_entry is None or raw_entry <= 0:
                    continue
                triggered_reason: RebalanceTradeReason | None = None
                exit_price: float | None = None
                if req.stop_loss_pct is not None:
                    sl_threshold = raw_entry * (1 - req.stop_loss_pct / 100)
                    if float(bar.low) <= sl_threshold:
                        triggered_reason = RebalanceTradeReason.STOP_LOSS
                        exit_price = sl_threshold
                if triggered_reason is None and take_profit_pct is not None:
                    tp_threshold = raw_entry * (1 + take_profit_pct / 100)
                    if float(bar.high) >= tp_threshold:
                        triggered_reason = RebalanceTradeReason.TAKE_PROFIT
                        exit_price = tp_threshold
                if triggered_reason is not None and exit_price is not None:
                    shares = holdings.get(code, 0)
                    _execute_sell(code, t, exit_price, shares, triggered_reason)

            # (b) Rebalance.
            is_rebalance_day = t in screener_cache
            if is_rebalance_day:
                picks = screener_cache.get(t, [])
                # Restrict to codes tradable on next trading day (we'll
                # execute at next-open). We keep top_n that have a next bar.
                target_with_score: list[tuple[str, float]] = []
                for code, score in picks:
                    if code not in bar_index:
                        continue
                    nxt_date, _ = _next_open(code, t_idx)
                    if nxt_date is None:
                        continue
                    target_with_score.append((code, score))
                    if len(target_with_score) >= req.top_n:
                        break

                target_codes = [c for c, _ in target_with_score]
                target_set = set(target_codes)

                # SELL drops first to free cash. Skip codes whose entry_date == t
                # (T+1 prevents same-day round trips, though buys execute at
                # next-open so this is rare.)
                for code in list(holdings.keys()):
                    if code in target_set:
                        continue
                    if entry_dates.get(code) == t:
                        continue  # T+1 violation guard
                    nxt_date, nxt_open = _next_open(code, t_idx)
                    if nxt_date is None or nxt_open is None:
                        # Fall back to current close if no future bar.
                        bar = _bar_for(code, t)
                        if bar is None:
                            continue
                        nxt_date = t
                        nxt_open = float(bar.close)
                    shares = holdings.get(code, 0)
                    _execute_sell(
                        code,
                        nxt_date,
                        nxt_open,
                        shares,
                        RebalanceTradeReason.SCREENER_DROP,
                    )

                # Compute target weights.
                if target_codes:
                    if req.weighting == "score":
                        score_sum = sum(s for _, s in target_with_score)
                        if score_sum > 0:
                            weights = {c: s / score_sum for c, s in target_with_score}
                        else:
                            weights = {c: 1 / len(target_codes) for c in target_codes}
                    else:
                        weights = {c: 1 / len(target_codes) for c in target_codes}

                    # Snapshot equity for sizing (uses today's close for
                    # held-and-tradable, last_known_close otherwise).
                    snapshot_equity = cash
                    for code, shares in holdings.items():
                        bar = _bar_for(code, t)
                        if bar is not None:
                            snapshot_equity += shares * float(bar.close)
                        else:
                            snapshot_equity += shares * last_known_close.get(
                                code, raw_entry_prices.get(code, 0.0)
                            )

                    # BUY: bring each target to its target shares at next-open.
                    # First compute deltas, then execute deltas<0 (sells) before
                    # deltas>0 (buys) so that freed cash is available.
                    pending_deltas: list[tuple[str, date, float, int]] = []
                    for code, w in weights.items():
                        nxt_date, nxt_open = _next_open(code, t_idx)
                        if nxt_date is None or nxt_open is None or nxt_open <= 0:
                            continue
                        target_value = snapshot_equity * w
                        target_shares = int(math.floor((target_value / nxt_open) / 100) * 100)
                        current_shares = holdings.get(code, 0)
                        delta = target_shares - current_shares
                        if delta != 0:
                            pending_deltas.append((code, nxt_date, nxt_open, delta))

                    # Execute reductions first.
                    for code, nxt_date, nxt_open, delta in pending_deltas:
                        if delta < 0:
                            if entry_dates.get(code) == t:
                                continue  # T+1 guard
                            _execute_sell(
                                code,
                                nxt_date,
                                nxt_open,
                                -delta,
                                RebalanceTradeReason.SCREENER_DROP,
                            )
                    for code, nxt_date, nxt_open, delta in pending_deltas:
                        if delta > 0:
                            _execute_buy(code, nxt_date, nxt_open, delta)

            # (c) Mark-to-market end-of-day t.
            mtm_equity = cash
            holding_items_for_snapshot: list[tuple[str, int, float]] = []
            for code, shares in holdings.items():
                bar = _bar_for(code, t)
                if bar is not None:
                    last_known_close[code] = float(bar.close)
                    mv = shares * float(bar.close)
                else:
                    mv = shares * last_known_close.get(code, raw_entry_prices.get(code, 0.0))
                mtm_equity += mv
                holding_items_for_snapshot.append((code, shares, mv))

            equity_curve.append(EquityPoint(date=t, value=round(mtm_equity, 2)))

            # (d) Snapshot AFTER rebalance trades have settled (i.e., next-
            # day-open fills are not in this snapshot — they will appear in
            # the snapshot on day t+1's mark-to-market). For consistency we
            # record the snapshot on rebalance days using current holdings
            # state (post-SL/TP) — same convention as equity.
            if is_rebalance_day:
                holding_items: list[HoldingItem] = []
                for code, shares, mv in holding_items_for_snapshot:
                    weight_pct = (mv / mtm_equity * 100) if mtm_equity > 0 else 0.0
                    holding_items.append(
                        HoldingItem(
                            code=code,
                            name=name_by_code.get(code, code),
                            shares=shares,
                            market_value=round(mv, 2),
                            weight_pct=round(weight_pct, 2),
                        )
                    )
                holdings_history.append(
                    HoldingSnapshot(
                        date=t,
                        cash=round(cash, 2),
                        equity=round(mtm_equity, 2),
                        holdings=holding_items,
                    )
                )

        # Force-close any remaining holdings at last close.
        if trading_days:
            last_t = trading_days[-1]
            for code in list(holdings.keys()):
                bar = _bar_for(code, last_t)
                px = (
                    float(bar.close)
                    if bar is not None
                    else last_known_close.get(code, raw_entry_prices.get(code, 0.0))
                )
                if px <= 0:
                    continue
                shares = holdings.get(code, 0)
                _execute_sell(code, last_t, px, shares, RebalanceTradeReason.FINAL_CLOSE)

        final_equity = cash  # all closed
        # Append/replace last equity point with final cash.
        if equity_curve:
            last_pt = equity_curve[-1]
            if last_pt.date == trading_days[-1]:
                equity_curve[-1] = EquityPoint(date=last_pt.date, value=round(final_equity, 2))

        # Drawdown curve.
        peak = float("-inf")
        for pt in equity_curve:
            peak = max(peak, pt.value)
            dd_pct = (pt.value - peak) / peak * 100 if peak > 0 else 0.0
            drawdown_curve.append(DrawdownPoint(date=pt.date, drawdown_pct=round(dd_pct, 2)))
        max_dd = abs(min((p.drawdown_pct for p in drawdown_curve), default=0.0))

        # KPIs.
        total_return_pct = (final_equity - req.initial_capital) / req.initial_capital * 100
        num_days = (req.end_date - req.start_date).days
        if num_days >= 30:
            annualized_return_pct: float | None = round(total_return_pct * 365 / num_days, 2)
        else:
            annualized_return_pct = None

        if trades:
            wins = sum(1 for t in trades if t.return_pct > 0)
            win_rate_pct = wins / len(trades) * 100
        else:
            win_rate_pct = 0.0

        # Benchmark.
        benchmark_curve: list[EquityPoint] | None = None
        benchmark_kind: str | None = None
        if req.benchmark == "universe_buy_hold":
            benchmark_curve = _build_benchmark_curve(
                trading_days,
                bars_by_code,
                bar_index,
                req.initial_capital,
            )
            benchmark_kind = "universe_buy_hold"
        elif req.benchmark == "hs300":
            hs300_curve = await self._build_hs300_curve(trading_days, req.initial_capital)
            if hs300_curve is not None:
                benchmark_curve = hs300_curve
                benchmark_kind = "hs300"
            else:
                # Index data missing — fall back to the universe buy-and-hold
                # surrogate so the front-end always has *something* to plot.
                benchmark_curve = _build_benchmark_curve(
                    trading_days,
                    bars_by_code,
                    bar_index,
                    req.initial_capital,
                )
                benchmark_kind = "hs300_or_fallback"

        # Cost summary.
        total_costs = total_commission + total_stamp + total_slippage
        cost_drag = total_costs / req.initial_capital * 100 if req.initial_capital else 0.0
        costs = CostBreakdown(
            total_commission=round(total_commission, 2),
            total_stamp_duty=round(total_stamp, 2),
            total_slippage_cost=round(total_slippage, 2),
            cost_drag_pct=round(cost_drag, 2),
        )

        # Extended KPIs.
        sharpe_ratio = _compute_sharpe(equity_curve)
        sortino_ratio = _compute_sortino(equity_curve)
        calmar_ratio = (
            round(annualized_return_pct / max_dd, 4)
            if (annualized_return_pct is not None and max_dd > 0)
            else None
        )
        # Turnover %: (total notional traded) / (avg equity * 2).
        turnover_pct = _compute_turnover_pct(trades, equity_curve)
        # Alpha vs benchmark: total_return - benchmark_total_return.
        alpha_pct: float | None = None
        if benchmark_curve and len(benchmark_curve) >= 2:
            bench_first = benchmark_curve[0].value
            bench_last = benchmark_curve[-1].value
            if bench_first > 0:
                bench_ret_pct = (bench_last - bench_first) / bench_first * 100
                alpha_pct = round(total_return_pct - bench_ret_pct, 2)

        monthly_returns = _compute_period_returns(equity_curve, "month")
        yearly_returns = _compute_period_returns(equity_curve, "year")

        # Attribution: industry exposure + market-cap buckets across realized
        # trades (weighted by entry notional) + realized monthly/yearly P&L.
        stocks_by_code = {s.code: s for s in stocks}
        attribution = _build_attribution(trades, stocks_by_code, monthly_returns, yearly_returns)

        return ScreenerBacktestResult(
            screen_type=req.screen_type,
            rebalance=req.rebalance,
            top_n=req.top_n,
            weighting=req.weighting,
            start_date=req.start_date,
            end_date=req.end_date,
            total_return_pct=round(total_return_pct, 2),
            annualized_return_pct=annualized_return_pct,
            win_rate_pct=round(win_rate_pct, 2),
            max_drawdown_pct=round(max_dd, 2),
            trade_count=len(trades),
            final_equity=round(final_equity, 2),
            initial_capital=round(float(req.initial_capital), 2),
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            turnover_pct=turnover_pct,
            sharpe_ratio=sharpe_ratio,
            alpha_pct=alpha_pct,
            equity_curve=equity_curve,
            benchmark_curve=benchmark_curve,
            benchmark_kind=benchmark_kind,
            drawdown_curve=drawdown_curve,
            rebalance_dates=list(rebalance_days),
            holdings_history=holdings_history,
            trades=trades,
            costs=costs,
            monthly_returns=monthly_returns,
            yearly_returns=yearly_returns,
            attribution=attribution,
        )

    async def _build_hs300_curve(
        self, trading_days: list[date], initial_capital: float
    ) -> list[EquityPoint] | None:
        """Build an HS300 benchmark curve from local ``daily_bars``.

        Returns ``None`` when the index has no rows in the local DB. The
        engine then transparently falls back to ``universe_buy_hold``.
        """
        if not trading_days:
            return None
        # Probe a couple common HS300 index codes used by Tushare/AKShare.
        candidate_codes = ("000300.SH", "000300", "SH000300", "399300.SZ")
        index_bars: list[DailyBar] = []
        for code in candidate_codes:
            bars = await self.market_data.repo.get_daily_bars(
                code, trading_days[0], trading_days[-1]
            )
            if bars:
                index_bars = sorted(bars, key=lambda b: b.trade_date)
                break
        if not index_bars:
            return None
        by_date = {b.trade_date: float(b.close) for b in index_bars}
        # Anchor to the first trading day that has a bar.
        anchor: float | None = None
        for d in trading_days:
            if d in by_date:
                anchor = by_date[d]
                break
        if anchor is None or anchor <= 0:
            return None
        out: list[EquityPoint] = []
        last = anchor
        for d in trading_days:
            last = by_date.get(d, last)
            out.append(EquityPoint(date=d, value=round(initial_capital * last / anchor, 2)))
        return out


def _compute_rebalance_dates(trading_days: list[date], cadence: str) -> list[date]:
    """Pick rebalance anchors from the trading-day list.

    - daily: every trading day
    - weekly: last trading day of each ISO week
    - biweekly: every other weekly anchor (drop alternating ones)
    - monthly: last trading day of each calendar month
    """
    if not trading_days:
        return []
    if cadence == "daily":
        return list(trading_days)

    if cadence == "monthly":
        by_month: dict[tuple[int, int], date] = {}
        for d in trading_days:
            key = (d.year, d.month)
            if key not in by_month or d > by_month[key]:
                by_month[key] = d
        return sorted(by_month.values())

    # weekly / biweekly: last trading day per ISO week.
    by_week: dict[tuple[int, int], date] = {}
    for d in trading_days:
        iso = d.isocalendar()
        key = (iso[0], iso[1])
        if key not in by_week or d > by_week[key]:
            by_week[key] = d
    weekly = sorted(by_week.values())
    if cadence == "biweekly":
        return weekly[::2]
    return weekly


def _build_benchmark_curve(
    trading_days: list[date],
    bars_by_code: dict[str, list[DailyBar]],
    bar_index: dict[str, dict[date, DailyBar]],
    initial_capital: float,
) -> list[EquityPoint]:
    """Equal-weight buy-and-hold of the eligible universe (no costs).

    Uses every code that has a bar on the first trading day. Mark-to-market
    is computed daily with carry-on-suspension (last known close persists
    when a stock has no bar that day). Final curve is normalized so the
    starting value equals ``initial_capital``.
    """
    if not trading_days:
        return []
    first_day = trading_days[0]
    eligible: list[str] = [
        code for code, bars in bars_by_code.items() if any(b.trade_date == first_day for b in bars)
    ]
    if not eligible:
        return [EquityPoint(date=d, value=round(initial_capital, 2)) for d in trading_days]

    # Equal weighted index of normalized closes.
    base_close: dict[str, float] = {}
    for code in eligible:
        bar = bar_index.get(code, {}).get(first_day)
        if bar is None or float(bar.close) <= 0:
            continue
        base_close[code] = float(bar.close)
    eligible = [c for c in eligible if c in base_close]
    if not eligible:
        return [EquityPoint(date=d, value=round(initial_capital, 2)) for d in trading_days]

    last_close: dict[str, float] = dict(base_close)
    out: list[EquityPoint] = []
    for d in trading_days:
        index_sum = 0.0
        for code in eligible:
            bar = bar_index.get(code, {}).get(d)
            if bar is not None:
                last_close[code] = float(bar.close)
            index_sum += last_close[code] / base_close[code]
        index_value = index_sum / len(eligible)
        out.append(EquityPoint(date=d, value=round(initial_capital * index_value, 2)))
    return out


# ---------------------------------------------------------------------------
# Extended KPIs and attribution helpers.
# ---------------------------------------------------------------------------


def _equity_daily_returns(equity_curve: list[EquityPoint]) -> list[float]:
    rets: list[float] = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1].value
        cur = equity_curve[i].value
        if prev <= 0:
            continue
        rets.append((cur - prev) / prev)
    return rets


def _compute_sharpe(equity_curve: list[EquityPoint]) -> float | None:
    rets = _equity_daily_returns(equity_curve)
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    std = math.sqrt(var)
    if std == 0:
        return None
    return round(mean / std * math.sqrt(TRADING_DAYS_PER_YEAR), 4)


def _compute_sortino(equity_curve: list[EquityPoint]) -> float | None:
    rets = _equity_daily_returns(equity_curve)
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    downside = [r for r in rets if r < 0]
    if not downside:
        return None
    dn_var = sum(r * r for r in downside) / len(downside)
    dn_std = math.sqrt(dn_var)
    if dn_std == 0:
        return None
    return round(mean / dn_std * math.sqrt(TRADING_DAYS_PER_YEAR), 4)


def _compute_turnover_pct(
    trades: list[ScreenerBacktestTrade], equity_curve: list[EquityPoint]
) -> float | None:
    if not trades or not equity_curve:
        return None
    total_notional = 0.0
    for t in trades:
        # Round-trip notional ≈ entry + exit gross.
        total_notional += t.entry_price * t.shares + t.exit_price * t.shares
    avg_equity = sum(p.value for p in equity_curve) / len(equity_curve)
    if avg_equity <= 0:
        return None
    # Per-side turnover: divide round-trip notional by 2.
    return round(total_notional / (2 * avg_equity) * 100, 2)


def _compute_period_returns(
    equity_curve: list[EquityPoint], grain: str
) -> list[MonthlyReturn] | list[YearlyReturn]:
    """Compute period (month/year) total returns from a daily equity curve.

    Each period's start/end equity is the first/last point inside the period.
    Returns a list ordered chronologically.
    """
    if not equity_curve:
        return []
    by_period: dict[str, list[EquityPoint]] = defaultdict(list)
    for p in equity_curve:
        if grain == "month":
            key = f"{p.date.year:04d}-{p.date.month:02d}"
        else:
            key = f"{p.date.year:04d}"
        by_period[key].append(p)
    out: list = []
    for key in sorted(by_period.keys()):
        pts = by_period[key]
        if not pts:
            continue
        start_v = pts[0].value
        end_v = pts[-1].value
        if start_v <= 0:
            continue
        ret_pct = (end_v - start_v) / start_v * 100
        if grain == "month":
            out.append(MonthlyReturn(period=key, return_pct=round(ret_pct, 2)))
        else:
            out.append(YearlyReturn(period=key, return_pct=round(ret_pct, 2)))
    return out


def _market_cap_bucket_for_code(code: str) -> str:
    """Bucket a stock by ts_code prefix as a coarse cap-tier proxy.

    No locally-synced market-cap data exists yet; A-share board prefixes are
    a workable surrogate for the screener admin UI:

    - 688/300 → small/mid (STAR / ChiNext, mostly small-mid cap)
    - 002    → mid (深圳中小板)
    - 600/601/000 → large (主板)
    """
    if not code:
        return "mid"
    head = code[:3]
    if head.startswith("688") or head.startswith("300"):
        return "small"
    if head.startswith("002"):
        return "mid"
    return "large"


def _sector_for_stock(stock) -> str:  # type: ignore[no-untyped-def]
    if stock is None:
        return "未知"
    industry = getattr(stock, "industry", None)
    if industry:
        return industry
    code = getattr(stock, "code", "") or ""
    # Last-resort fallback: bucket by exchange.
    if code.startswith("6"):
        return "沪市主板"
    if code.startswith("0"):
        return "深市主板"
    if code.startswith("3"):
        return "创业板"
    if code.startswith("688"):
        return "科创板"
    return "其他"


def _build_attribution(
    trades: list[ScreenerBacktestTrade],
    stocks_by_code: dict[str, object],
    monthly_returns: list[MonthlyReturn],
    yearly_returns: list[YearlyReturn],
) -> AttributionOut:
    sector_weight: dict[str, float] = defaultdict(float)
    bucket_weight: dict[str, float] = defaultdict(float)
    total_notional = 0.0
    for t in trades:
        notional = t.entry_price * t.shares
        if notional <= 0:
            continue
        total_notional += notional
        stock = stocks_by_code.get(t.code)
        sector_weight[_sector_for_stock(stock)] += notional
        bucket_weight[_market_cap_bucket_for_code(t.code)] += notional

    if total_notional > 0:
        sector_exposure = [
            SectorWeight(
                sector=name,
                weight_pct=round(value / total_notional * 100, 2),
            )
            for name, value in sorted(sector_weight.items(), key=lambda kv: kv[1], reverse=True)
        ]
        market_cap_buckets = [
            MarketCapBucket(
                bucket=name,
                weight_pct=round(value / total_notional * 100, 2),
            )
            for name, value in sorted(bucket_weight.items(), key=lambda kv: kv[1], reverse=True)
        ]
    else:
        sector_exposure = []
        market_cap_buckets = []

    return AttributionOut(
        sector_exposure=sector_exposure,
        market_cap_buckets=market_cap_buckets,
        monthly_returns=list(monthly_returns),
        yearly_returns=list(yearly_returns),
    )
