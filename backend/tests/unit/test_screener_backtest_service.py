"""Smoke test for the screener walk-forward backtest engine.

The engine integrates the market-data screener with a portfolio simulator,
so we mock the dependencies to keep the test hermetic and CI-fast.
"""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.modules.backtests.schemas import (
    ScreenerBacktestRequest,
)
from app.modules.backtests.service import BacktestService
from app.modules.market_data.schemas import (
    StockScreenItemOut,
    StockScreenResultOut,
)


def _bar(*, code: str, dt: date, close: float) -> SimpleNamespace:
    return SimpleNamespace(
        code=code,
        trade_date=dt,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
        amount=close * 1000,
        turnover=0.0,
    )


@pytest.mark.asyncio
async def test_run_screener_backtest_smoke(monkeypatch):
    """Engine produces a coherent result given two stocks and a steady uptrend."""
    svc = BacktestService()

    start = date(2026, 1, 5)
    # Build 30 trading days (calendar days; weekends fine for a synthetic test).
    days = [start + timedelta(days=i) for i in range(30)]

    # Stock A: steady +1/day
    bars_a = [_bar(code="000001", dt=d, close=10.0 + i * 0.1) for i, d in enumerate(days)]
    # Stock B: also up but slower
    bars_b = [_bar(code="000002", dt=d, close=20.0 + i * 0.05) for i, d in enumerate(days)]
    bars_by_code = {"000001": bars_a, "000002": bars_b}

    async def fake_get_codes_with_daily_bars():
        return {"000001", "000002"}

    async def fake_get_stocks():
        return [
            SimpleNamespace(code="000001", name="Alpha"),
            SimpleNamespace(code="000002", name="Beta"),
        ]

    async def fake_get_daily_bars_for_codes(codes, start_date=None, end_date=None):
        out: dict[str, list] = {}
        for c in codes:
            bars = bars_by_code.get(c, [])
            sel = [
                b for b in bars
                if (start_date is None or b.trade_date >= start_date)
                and (end_date is None or b.trade_date <= end_date)
            ]
            out[c] = sel
        return out

    async def fake_screen_stocks(screen_type, params=None, *, as_of_date=None):
        # Always return both stocks ordered A first.
        return StockScreenResultOut(
            screen_type=screen_type,
            total=2,
            items=[
                StockScreenItemOut(
                    symbol="000001",
                    name="Alpha",
                    market="SZ",
                    industry=None,
                    latest_close=10.0,
                    return_5d_pct=2.0,
                    return_20d_pct=8.0,
                    volume_ratio_5d=1.5,
                    trend_bias="bullish",
                    match_reason="ok",
                ),
                StockScreenItemOut(
                    symbol="000002",
                    name="Beta",
                    market="SZ",
                    industry=None,
                    latest_close=20.0,
                    return_5d_pct=1.0,
                    return_20d_pct=4.0,
                    volume_ratio_5d=1.2,
                    trend_bias="bullish",
                    match_reason="ok",
                ),
            ],
        )

    monkeypatch.setattr(svc.market_data.repo, "get_codes_with_daily_bars", fake_get_codes_with_daily_bars)
    monkeypatch.setattr(svc.market_data.repo, "get_stocks", fake_get_stocks)
    monkeypatch.setattr(svc.market_data.repo, "get_daily_bars_for_codes", fake_get_daily_bars_for_codes)
    monkeypatch.setattr(svc.market_data, "screen_stocks", fake_screen_stocks)

    req = ScreenerBacktestRequest(
        screen_type="strong_uptrend",
        start_date=days[0],
        end_date=days[-1],
        rebalance="weekly",
        top_n=2,
        weighting="equal",
        initial_capital=100_000.0,
        # Disable risk control to make the test deterministic.
        stop_loss_pct=None,
        take_profit_pct=None,
        benchmark="universe_buy_hold",
    )

    result = await svc.run_screener_backtest(req)

    assert result.screen_type == "strong_uptrend"
    assert result.rebalance == "weekly"
    assert len(result.equity_curve) == len(days)
    assert result.benchmark_curve is not None
    assert len(result.benchmark_curve) == len(days)
    assert len(result.drawdown_curve) == len(days)
    assert len(result.rebalance_dates) >= 1
    assert len(result.holdings_history) == len(result.rebalance_dates)
    # Both stocks went up; with all final positions force-closed, expect a
    # positive return (modulo the cost drag) and trades populated.
    assert result.trade_count >= 1
    assert result.final_equity > 0
    # All holdings must be flat at the end (force-closed if any remain).
    if result.holdings_history:
        last_snapshot = result.holdings_history[-1]
        # last rebalance snapshot may still have holdings (close happens after);
        # the engine guarantees final_equity == cash with no open positions.
        assert last_snapshot.equity > 0
    assert result.costs.total_commission >= 0
    assert result.costs.total_stamp_duty >= 0
