"""Smoke tests for the strategies catalog + KPI snapshot service.

The service composes two collaborators (the strategies repository and the
screener walk-forward backtest engine), both of which are mocked here so
the test stays hermetic.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import pytest

from app.modules.backtests.schemas import (
    CostBreakdown,
    EquityPoint,
    ScreenerBacktestResult,
)
from app.modules.strategies.catalog import STRATEGY_CATALOG
from app.modules.strategies.models import StrategyKpiSnapshot
from app.modules.strategies.service import StrategiesService


class _InMemoryRepo:
    def __init__(self) -> None:
        self.snapshots: dict[str, StrategyKpiSnapshot] = {}

    async def get_all_snapshots(self) -> dict[str, StrategyKpiSnapshot]:
        return dict(self.snapshots)

    async def upsert_snapshot(self, snapshot: StrategyKpiSnapshot) -> None:
        self.snapshots[snapshot.key] = snapshot


class _StubBacktestService:
    def __init__(self, result: ScreenerBacktestResult) -> None:
        self._result = result
        self.calls: list[Any] = []

    async def run_screener_backtest(self, req) -> ScreenerBacktestResult:
        self.calls.append(req)
        return self._result


def _build_result(days: int = 30) -> ScreenerBacktestResult:
    start = date(2026, 1, 1)
    equity_curve = [
        EquityPoint(date=start + timedelta(days=i), value=100_000.0 + i * 200.0)
        for i in range(days)
    ]
    return ScreenerBacktestResult(
        screen_type="strong_uptrend",
        rebalance="weekly",
        top_n=10,
        weighting="equal",
        start_date=equity_curve[0].date,
        end_date=equity_curve[-1].date,
        total_return_pct=5.8,
        annualized_return_pct=70.0,
        win_rate_pct=60.0,
        max_drawdown_pct=2.0,
        trade_count=4,
        final_equity=105_800.0,
        initial_capital=100_000.0,
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


@pytest.mark.asyncio
async def test_list_strategies_without_snapshots_returns_catalog() -> None:
    repo = _InMemoryRepo()
    backtest = _StubBacktestService(_build_result())
    svc = StrategiesService(repo=repo, backtest_service=backtest)  # type: ignore[arg-type]

    out = await svc.list_strategies()

    assert len(out.strategies) == 3
    keys = [s.key for s in out.strategies]
    assert keys == [d.key for d in STRATEGY_CATALOG]
    assert keys == ["strong_uptrend", "volume_breakout", "pullback_watch"]
    by_key = {s.key: s for s in out.strategies}
    assert "trend_following" in by_key["strong_uptrend"].tags
    assert "trending_market" in by_key["strong_uptrend"].tags
    assert "volume" in by_key["volume_breakout"].tags
    assert "mean_reversion" in by_key["pullback_watch"].tags
    for s in out.strategies:
        assert s.kpi is None


@pytest.mark.asyncio
async def test_compute_and_persist_snapshot_populates_kpi() -> None:
    repo = _InMemoryRepo()
    backtest = _StubBacktestService(_build_result(days=40))
    svc = StrategiesService(repo=repo, backtest_service=backtest)  # type: ignore[arg-type]

    snapshot = await svc.compute_and_persist_snapshot("strong_uptrend")

    assert snapshot.key == "strong_uptrend"
    assert snapshot.lookback_days == 180
    assert snapshot.trade_count == 4
    assert snapshot.total_return_pct == pytest.approx(5.8)
    assert snapshot.annualized_return_pct == pytest.approx(70.0)
    assert snapshot.max_drawdown_pct == pytest.approx(2.0)
    assert snapshot.win_rate_pct == pytest.approx(60.0)
    # Sharpe should be a finite positive number for a strictly-rising curve.
    assert snapshot.sharpe_ratio is not None
    assert snapshot.sharpe_ratio > 0
    sparkline = json.loads(snapshot.equity_sparkline_json)
    assert sparkline, "sparkline must be populated"
    assert len(sparkline) <= 60

    out = await svc.list_strategies()
    by_key = {s.key: s for s in out.strategies}
    populated = by_key["strong_uptrend"]
    assert populated.kpi is not None
    assert populated.kpi.trade_count == 4
    assert populated.kpi.equity_sparkline
    assert by_key["volume_breakout"].kpi is None
    assert by_key["pullback_watch"].kpi is None


@pytest.mark.asyncio
async def test_compute_all_snapshots_skips_failures() -> None:
    repo = _InMemoryRepo()

    class _FlakyBacktest:
        def __init__(self) -> None:
            self.count = 0

        async def run_screener_backtest(self, req) -> ScreenerBacktestResult:
            self.count += 1
            if self.count == 2:
                raise RuntimeError("boom")
            return _build_result()

    backtest = _FlakyBacktest()
    svc = StrategiesService(repo=repo, backtest_service=backtest)  # type: ignore[arg-type]

    successes = await svc.compute_all_snapshots()
    assert successes == 2
    assert len(repo.snapshots) == 2
