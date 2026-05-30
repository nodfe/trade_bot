"""Simple backtest engine.

Implements a double-moving-average crossover backtest on a single A-share
stock using historical daily bars fetched via :class:`MarketDataService`.

This module is pure computation — no DB writes, no new tables.
"""

from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.modules.backtests.schemas import (
    BacktestRequest,
    BacktestResult,
    BacktestTrade,
    EquityPoint,
)
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
