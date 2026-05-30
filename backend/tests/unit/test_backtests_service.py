"""Tests for the simple double-MA-crossover backtest engine."""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.core.exceptions import NotFoundError
from app.modules.backtests.schemas import BacktestRequest
from app.modules.backtests.service import BacktestService


def _bar(
    *,
    code: str = "600519",
    trade_date: date,
    open_: float,
    close: float,
) -> SimpleNamespace:
    return SimpleNamespace(
        code=code,
        trade_date=trade_date,
        open=open_,
        high=max(open_, close),
        low=min(open_, close),
        close=close,
        volume=1000,
        amount=close * 1000,
        turnover=0.0,
    )


def _make_bars(prices: list[float], start: date = date(2026, 1, 5)) -> list:
    """Build a list of fake daily bars from a close-price series.

    `open` is set to the previous bar's close (or the same close on day 0)
    so the next-bar-open execution price is well-defined.
    """
    bars = []
    cur = start
    for i, close in enumerate(prices):
        open_ = prices[i - 1] if i > 0 else close
        bars.append(_bar(trade_date=cur, open_=open_, close=close))
        cur += timedelta(days=1)
    return bars


@pytest.mark.asyncio
async def test_happy_path_uptrend_produces_profitable_trade(monkeypatch):
    svc = BacktestService()

    # 60-bar series: flat-ish for 25 bars, then a clear sustained uptrend.
    prices: list[float] = [100.0] * 25 + [
        100.0 + i * 2.0 for i in range(1, 36)
    ]
    assert len(prices) == 60
    bars = _make_bars(prices)

    async def fake_get_daily_bars(code, start, end):
        assert code == "600519"
        return bars

    monkeypatch.setattr(svc.market_data, "get_daily_bars", fake_get_daily_bars)

    req = BacktestRequest(
        code="600519",
        start_date=bars[0].trade_date,
        end_date=bars[-1].trade_date,
        fast_period=5,
        slow_period=20,
        initial_capital=100_000.0,
    )
    result = await svc.run_simple_backtest(req)

    assert result.trade_count >= 1
    assert result.total_return_pct > 0
    assert result.final_equity > req.initial_capital
    assert len(result.equity_curve) == len(bars)
    # All round-trip trades closed: shares should be 0, equity == cash.
    # Annualized must be set (60-day window > 30 days).
    assert result.annualized_return_pct is not None


@pytest.mark.asyncio
async def test_insufficient_bars_raises_not_found(monkeypatch):
    svc = BacktestService()

    bars = _make_bars([10.0, 11.0, 10.5, 11.2, 11.5])  # only 5 bars

    async def fake_get_daily_bars(code, start, end):
        return bars

    monkeypatch.setattr(svc.market_data, "get_daily_bars", fake_get_daily_bars)

    req = BacktestRequest(
        code="600519",
        start_date=bars[0].trade_date,
        end_date=bars[-1].trade_date,
        fast_period=5,
        slow_period=20,
        initial_capital=100_000.0,
    )
    with pytest.raises(NotFoundError):
        await svc.run_simple_backtest(req)


@pytest.mark.asyncio
async def test_monotonically_declining_no_trades(monkeypatch):
    svc = BacktestService()

    # Strictly declining series → fast SMA always below slow SMA, no
    # bullish cross ever occurs, so no buys, no trades.
    prices = [200.0 - i * 0.5 for i in range(60)]
    bars = _make_bars(prices)

    async def fake_get_daily_bars(code, start, end):
        return bars

    monkeypatch.setattr(svc.market_data, "get_daily_bars", fake_get_daily_bars)

    req = BacktestRequest(
        code="600519",
        start_date=bars[0].trade_date,
        end_date=bars[-1].trade_date,
        fast_period=5,
        slow_period=20,
        initial_capital=100_000.0,
    )
    result = await svc.run_simple_backtest(req)

    assert result.trade_count == 0
    # No positions ever taken → final equity == initial capital exactly.
    assert result.final_equity == pytest.approx(req.initial_capital)
    assert result.total_return_pct == 0.0
    assert result.win_rate_pct == 0.0
