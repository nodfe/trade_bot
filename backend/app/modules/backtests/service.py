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
from datetime import date, timedelta

from app.core.exceptions import NotFoundError
from app.modules.backtests.schemas import (
    BacktestRequest,
    BacktestResult,
    BacktestTrade,
    CostBreakdown,
    DrawdownPoint,
    EquityPoint,
    HoldingItem,
    HoldingSnapshot,
    RebalanceTradeReason,
    ScreenerBacktestRequest,
    ScreenerBacktestResult,
    ScreenerBacktestTrade,
)
from app.modules.market_data.models import DailyBar
from app.modules.market_data.schemas import StockScreenParams
from app.modules.market_data.service import MarketDataService


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
        bars = await self.market_data.get_daily_bars(
            req.code, req.start_date, req.end_date
        )

        if len(bars) < req.slow_period + 2:
            raise NotFoundError("Insufficient bars for backtest")

        # Sort bars chronologically (defensive — repo may return DESC).
        bars = sorted(bars, key=lambda b: b.trade_date)

        closes = [float(b.close) for b in bars]
        opens = [float(b.open) for b in bars]
        dates = [b.trade_date for b in bars]
        n = len(bars)

        fast_smas: list[float | None] = [
            _sma(closes, req.fast_period, i) for i in range(n)
        ]
        slow_smas: list[float | None] = [
            _sma(closes, req.slow_period, i) for i in range(n)
        ]

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
            equity_curve.append(
                EquityPoint(date=dates[i], value=round(equity, 2))
            )

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

    async def run_screener_backtest(
        self, req: ScreenerBacktestRequest
    ) -> ScreenerBacktestResult:
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

        # We need a comfortable window prior to start_date so the screener has
        # 20 bars of history available on the very first rebalance day. Pull
        # bars from start_date - 60 calendar days through end_date.
        prefetch_start = req.start_date - timedelta(days=60)
        bars_by_code: dict[str, list[DailyBar]] = (
            await self.market_data.repo.get_daily_bars_for_codes(
                candidate_codes, prefetch_start, req.end_date
            )
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
            raise NotFoundError(
                "No trading days with bars in the requested range"
            )

        rebalance_days = _compute_rebalance_dates(trading_days, req.rebalance)

        # Cache: rebalance_date -> [(code, score)] picks ordered by screen rank.
        screener_cache: dict[date, list[tuple[str, float]]] = {}
        params = req.screen_params_override or StockScreenParams()
        # Ensure we get enough picks to fall back from after filtering.
        params = params.model_copy(update={"limit": max(params.limit, req.top_n * 3)})

        # NOTE (perf): screen_stocks loops internally over ~200 codes calling
        # get_stock_analysis_summary per stock per rebalance day. For ~57
        # eligible codes × ~10 rebalance dates this is ~570 SQL queries.
        # Acceptable for v1; future optimization could vectorize bar loading.
        for rday in rebalance_days:
            res = await self.market_data.screen_stocks(
                req.screen_type, params, as_of_date=rday
            )
            screener_cache[rday] = [
                (item.symbol, max(0.0, item.return_20d_pct or 0.0))
                for item in res.items
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
                if (
                    triggered_reason is None
                    and req.take_profit_pct is not None
                ):
                    tp_threshold = raw_entry * (1 + req.take_profit_pct / 100)
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
                            weights = {
                                c: s / score_sum for c, s in target_with_score
                            }
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
                        target_shares = int(
                            math.floor((target_value / nxt_open) / 100) * 100
                        )
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
                    mv = shares * last_known_close.get(
                        code, raw_entry_prices.get(code, 0.0)
                    )
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
                px = float(bar.close) if bar is not None else last_known_close.get(
                    code, raw_entry_prices.get(code, 0.0)
                )
                if px <= 0:
                    continue
                shares = holdings.get(code, 0)
                _execute_sell(
                    code, last_t, px, shares, RebalanceTradeReason.FINAL_CLOSE
                )

        final_equity = cash  # all closed
        # Append/replace last equity point with final cash.
        if equity_curve:
            last_pt = equity_curve[-1]
            if last_pt.date == trading_days[-1]:
                equity_curve[-1] = EquityPoint(
                    date=last_pt.date, value=round(final_equity, 2)
                )

        # Drawdown curve.
        peak = float("-inf")
        for pt in equity_curve:
            peak = max(peak, pt.value)
            dd_pct = (pt.value - peak) / peak * 100 if peak > 0 else 0.0
            drawdown_curve.append(
                DrawdownPoint(date=pt.date, drawdown_pct=round(dd_pct, 2))
            )
        max_dd = abs(min((p.drawdown_pct for p in drawdown_curve), default=0.0))

        # KPIs.
        total_return_pct = (
            (final_equity - req.initial_capital) / req.initial_capital * 100
        )
        num_days = (req.end_date - req.start_date).days
        if num_days >= 30:
            annualized_return_pct: float | None = round(
                total_return_pct * 365 / num_days, 2
            )
        else:
            annualized_return_pct = None

        if trades:
            wins = sum(1 for t in trades if t.return_pct > 0)
            win_rate_pct = wins / len(trades) * 100
        else:
            win_rate_pct = 0.0

        # Benchmark.
        benchmark_curve: list[EquityPoint] | None = None
        if req.benchmark == "universe_buy_hold":
            benchmark_curve = _build_benchmark_curve(
                trading_days,
                bars_by_code,
                bar_index,
                req.initial_capital,
            )

        # Cost summary.
        total_costs = total_commission + total_stamp + total_slippage
        cost_drag = total_costs / req.initial_capital * 100 if req.initial_capital else 0.0
        costs = CostBreakdown(
            total_commission=round(total_commission, 2),
            total_stamp_duty=round(total_stamp, 2),
            total_slippage_cost=round(total_slippage, 2),
            cost_drag_pct=round(cost_drag, 2),
        )

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
            equity_curve=equity_curve,
            benchmark_curve=benchmark_curve,
            drawdown_curve=drawdown_curve,
            rebalance_dates=list(rebalance_days),
            holdings_history=holdings_history,
            trades=trades,
            costs=costs,
        )


def _compute_rebalance_dates(
    trading_days: list[date], cadence: str
) -> list[date]:
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
        code for code, bars in bars_by_code.items()
        if any(b.trade_date == first_day for b in bars)
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
