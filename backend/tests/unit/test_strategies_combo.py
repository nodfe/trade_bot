"""Tests for the multi-strategy combo backtest endpoint."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.modules.backtests.schemas import (
    CostBreakdown,
    EquityPoint,
    ScreenerBacktestResult,
)
from app.modules.strategies.combo_router import run_combo_backtest
from app.modules.strategies.combo_schemas import (
    StrategyComboItem,
    StrategyComboRequest,
)


def _make_result(
    *,
    screen_type: str,
    start: date,
    days: int,
    daily_step: float,
    initial_capital: float = 100_000.0,
) -> ScreenerBacktestResult:
    equity_curve = [
        EquityPoint(
            date=start + timedelta(days=i),
            value=initial_capital + i * daily_step,
        )
        for i in range(days)
    ]
    return ScreenerBacktestResult(
        screen_type=screen_type,
        rebalance="weekly",
        top_n=10,
        weighting="equal",
        start_date=equity_curve[0].date,
        end_date=equity_curve[-1].date,
        total_return_pct=(equity_curve[-1].value - initial_capital) / initial_capital * 100,
        annualized_return_pct=10.0,
        win_rate_pct=55.0,
        max_drawdown_pct=2.0,
        trade_count=3,
        final_equity=equity_curve[-1].value,
        initial_capital=initial_capital,
        equity_curve=equity_curve,
        benchmark_curve=None,
        drawdown_curve=[],
        rebalance_dates=[],
        holdings_history=[],
        trades=[],
        costs=CostBreakdown(
            total_commission=0.0,
            total_stamp_duty=0.0,
            total_slippage_cost=0.0,
            cost_drag_pct=0.0,
        ),
    )


class _StubBacktestService:
    def __init__(self, results_by_key: dict[str, ScreenerBacktestResult]) -> None:
        self.results_by_key = results_by_key
        self.calls = []

    async def run_screener_backtest(self, req):
        self.calls.append(req)
        return self.results_by_key[req.screen_type]


@pytest.mark.asyncio
async def test_combo_returns_composite_curve_and_kpi() -> None:
    start = date(2026, 1, 1)
    end = date(2026, 4, 1)
    days = 60

    res_a = _make_result(screen_type="strong_uptrend", start=start, days=days, daily_step=200.0)
    res_b = _make_result(screen_type="volume_breakout", start=start, days=days, daily_step=100.0)
    bt = _StubBacktestService({"strong_uptrend": res_a, "volume_breakout": res_b})

    req = StrategyComboRequest(
        items=[
            StrategyComboItem(strategy_key="strong_uptrend", weight=2.0),
            StrategyComboItem(strategy_key="volume_breakout", weight=1.0),
        ],
        rebalance="weekly",
        start_date=start,
        end_date=end,
        top_n=5,
        weighting="equal",
        initial_capital=100_000.0,
    )

    out = await run_combo_backtest(req, backtest_service=bt)  # type: ignore[arg-type]

    assert len(out.composite_equity_curve) == days
    # First point should equal initial capital (both sub strategies start at base).
    assert out.composite_equity_curve[0].value == pytest.approx(100_000.0)
    # Final composite return should be a weighted blend in proportion 2:1.
    final_a = res_a.equity_curve[-1].value / res_a.initial_capital
    final_b = res_b.equity_curve[-1].value / res_b.initial_capital
    expected_final = (2 / 3 * final_a + 1 / 3 * final_b) * 100_000.0
    assert out.composite_equity_curve[-1].value == pytest.approx(expected_final, rel=1e-4)

    # Per-strategy curves
    assert len(out.per_strategy_curves) == 2
    keys = [c.strategy_key for c in out.per_strategy_curves]
    assert keys == ["strong_uptrend", "volume_breakout"]
    assert out.per_strategy_curves[0].weight_normalized == pytest.approx(2 / 3)
    assert out.per_strategy_curves[1].weight_normalized == pytest.approx(1 / 3)

    # Correlation matrix is NxN with 1.0 diagonal.
    matrix = out.correlation_matrix
    assert set(matrix.keys()) == {"strong_uptrend", "volume_breakout"}
    assert matrix["strong_uptrend"]["strong_uptrend"] == pytest.approx(1.0)
    # Two monotonically rising curves should be perfectly correlated.
    assert matrix["strong_uptrend"]["volume_breakout"] == pytest.approx(1.0, abs=1e-3)

    # KPI sanity
    assert out.kpi.total_return_pct > 0
    assert out.kpi.sharpe_ratio is None or out.kpi.sharpe_ratio > 0


@pytest.mark.asyncio
async def test_combo_rejects_zero_weight_total() -> None:
    # All weights must be positive and sum > 0 — pydantic enforces gt=0.
    with pytest.raises(Exception):
        StrategyComboRequest(
            items=[StrategyComboItem(strategy_key="strong_uptrend", weight=0.0)],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 1),
        )


@pytest.mark.asyncio
async def test_combo_handles_duplicate_strategy_keys() -> None:
    start = date(2026, 1, 1)
    end = date(2026, 2, 1)
    res = _make_result(screen_type="strong_uptrend", start=start, days=30, daily_step=50.0)
    bt = _StubBacktestService({"strong_uptrend": res})
    req = StrategyComboRequest(
        items=[
            StrategyComboItem(strategy_key="strong_uptrend", weight=1.0),
            StrategyComboItem(
                strategy_key="strong_uptrend",
                weight=1.0,
                params_override={"min_return_20d_pct": 10},
            ),
        ],
        start_date=start,
        end_date=end,
    )
    out = await run_combo_backtest(req, backtest_service=bt)  # type: ignore[arg-type]
    matrix = out.correlation_matrix
    assert "strong_uptrend" in matrix
    assert "strong_uptrend#2" in matrix
