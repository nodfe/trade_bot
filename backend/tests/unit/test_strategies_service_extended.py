"""Tests for the extended strategies service: KPI fields, run-backtest
override, custom strategies CRUD, and attribution."""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import pytest

from app.modules.backtests.schemas import (
    AttributionOut,
    CostBreakdown,
    EquityPoint,
    MarketCapBucket,
    MonthlyReturn,
    ScreenerBacktestResult,
    SectorWeight,
    YearlyReturn,
)
from app.modules.strategies.models import StrategyKpiSnapshot, UserStrategy
from app.modules.strategies.service import StrategiesService, custom_key


class _InMemoryRepo:
    def __init__(self) -> None:
        self.snapshots: dict[str, StrategyKpiSnapshot] = {}
        self.user_rows: dict[str, UserStrategy] = {}
        self._uuid_counter = 0

    async def get_all_snapshots(self) -> dict[str, StrategyKpiSnapshot]:
        return dict(self.snapshots)

    async def upsert_snapshot(self, snapshot: StrategyKpiSnapshot) -> None:
        self.snapshots[snapshot.key] = snapshot

    async def list_user_strategies(self) -> list[UserStrategy]:
        return list(self.user_rows.values())

    async def get_user_strategy(self, sid: str) -> UserStrategy | None:
        return self.user_rows.get(sid)

    async def create_user_strategy(
        self,
        *,
        name: str,
        base_template: str,
        params: dict,
        owner: str = "default",
        description: str | None = None,
    ) -> UserStrategy:
        self._uuid_counter += 1
        sid = f"u-{self._uuid_counter}"
        from datetime import datetime

        row = UserStrategy(
            id=sid,
            name=name,
            base_template=base_template,
            params_json=json.dumps(params),
            owner=owner,
            description=description,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        self.user_rows[sid] = row
        return row

    async def update_user_strategy(
        self,
        sid: str,
        *,
        name: str | None = None,
        params: dict | None = None,
        description: str | None = None,
    ) -> UserStrategy | None:
        row = self.user_rows.get(sid)
        if row is None:
            return None
        if name is not None:
            row.name = name
        if params is not None:
            row.params_json = json.dumps(params)
        if description is not None:
            row.description = description
        return row

    async def delete_user_strategy(self, sid: str) -> bool:
        return self.user_rows.pop(sid, None) is not None


def _build_result(*, with_attribution: bool = True) -> ScreenerBacktestResult:
    start = date(2026, 1, 1)
    equity_curve = [
        EquityPoint(date=start + timedelta(days=i), value=100_000.0 + i * 200.0) for i in range(40)
    ]
    benchmark_curve = [
        EquityPoint(date=p.date, value=100_000.0 + (p.value - 100_000.0) * 0.5)
        for p in equity_curve
    ]
    monthly = [
        MonthlyReturn(period="2026-01", return_pct=4.5),
        MonthlyReturn(period="2026-02", return_pct=2.0),
    ]
    yearly = [YearlyReturn(period="2026", return_pct=6.5)]
    attribution = (
        AttributionOut(
            sector_exposure=[SectorWeight(sector="电子", weight_pct=60.0)],
            market_cap_buckets=[MarketCapBucket(bucket="large", weight_pct=100.0)],
            monthly_returns=list(monthly),
            yearly_returns=list(yearly),
        )
        if with_attribution
        else None
    )
    return ScreenerBacktestResult(
        screen_type="strong_uptrend",
        rebalance="weekly",
        top_n=10,
        weighting="equal",
        start_date=equity_curve[0].date,
        end_date=equity_curve[-1].date,
        total_return_pct=7.8,
        annualized_return_pct=70.0,
        win_rate_pct=60.0,
        max_drawdown_pct=2.0,
        trade_count=4,
        final_equity=107_800.0,
        initial_capital=100_000.0,
        sortino_ratio=1.5,
        calmar_ratio=35.0,
        turnover_pct=120.0,
        sharpe_ratio=1.8,
        alpha_pct=3.9,
        equity_curve=equity_curve,
        benchmark_curve=benchmark_curve,
        benchmark_kind="hs300_or_fallback",
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
        monthly_returns=monthly,
        yearly_returns=yearly,
        attribution=attribution,
    )


class _StubBacktest:
    def __init__(self, result: ScreenerBacktestResult) -> None:
        self.result = result
        self.calls: list[Any] = []

    async def run_screener_backtest(self, req) -> ScreenerBacktestResult:
        self.calls.append(req)
        return self.result


@pytest.mark.asyncio
async def test_extended_kpi_fields_persisted_in_snapshot() -> None:
    repo = _InMemoryRepo()
    backtest = _StubBacktest(_build_result())
    svc = StrategiesService(repo=repo, backtest_service=backtest)  # type: ignore[arg-type]

    snap = await svc.compute_and_persist_snapshot("strong_uptrend")

    assert snap.sortino_ratio == pytest.approx(1.5)
    assert snap.calmar_ratio == pytest.approx(35.0)
    assert snap.turnover_pct == pytest.approx(120.0)
    assert snap.alpha_pct == pytest.approx(3.9)
    assert snap.benchmark_equity_sparkline_json is not None
    assert snap.monthly_returns_json is not None

    listing = await svc.list_strategies()
    by_key = {s.key: s for s in listing.strategies}
    kpi = by_key["strong_uptrend"].kpi
    assert kpi is not None
    assert kpi.sortino_ratio == pytest.approx(1.5)
    assert kpi.alpha_pct == pytest.approx(3.9)
    assert kpi.benchmark_equity_sparkline
    assert kpi.monthly_returns


@pytest.mark.asyncio
async def test_run_backtest_override_passes_through_params() -> None:
    repo = _InMemoryRepo()
    backtest = _StubBacktest(_build_result())
    svc = StrategiesService(repo=repo, backtest_service=backtest)  # type: ignore[arg-type]

    out = await svc.run_backtest_override(
        "volume_breakout",
        params={"min_volume_ratio": 1.5, "min_return_5d_pct": 0.5},
        top_n=5,
        rebalance="monthly",
        weighting="score",
        fee_bps=20,
        stop_loss_pct=8,
        stop_profit_pct=15,
        benchmark="hs300",
    )

    assert out.total_return_pct == pytest.approx(7.8)
    assert backtest.calls, "stub should have been invoked"
    req = backtest.calls[0]
    assert req.screen_type == "volume_breakout"
    assert req.top_n == 5
    assert req.rebalance == "monthly"
    assert req.fee_bps == 20
    assert req.stop_loss_pct == 8
    assert req.stop_profit_pct == 15
    assert req.benchmark == "hs300"
    assert req.screen_params_override is not None
    assert req.screen_params_override.min_volume_ratio == pytest.approx(1.5)


@pytest.mark.asyncio
async def test_run_backtest_override_unknown_key_raises() -> None:
    repo = _InMemoryRepo()
    backtest = _StubBacktest(_build_result())
    svc = StrategiesService(repo=repo, backtest_service=backtest)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        await svc.run_backtest_override("does_not_exist")


@pytest.mark.asyncio
async def test_user_strategy_crud_full_cycle() -> None:
    repo = _InMemoryRepo()
    backtest = _StubBacktest(_build_result())
    svc = StrategiesService(repo=repo, backtest_service=backtest)  # type: ignore[arg-type]

    created = await svc.create_user_strategy(
        name="My Volume Pick",
        base_template="volume_breakout",
        params={"min_volume_ratio": 1.5},
        description="hand-tuned",
    )
    assert created.id == "u-1"
    assert created.catalog_key == "custom:u-1"
    assert created.params == {"min_volume_ratio": 1.5}

    listed = await svc.list_user_strategies()
    assert len(listed) == 1

    fetched = await svc.get_user_strategy("u-1")
    assert fetched is not None and fetched.name == "My Volume Pick"

    updated = await svc.update_user_strategy(
        "u-1", name="Renamed", params={"min_volume_ratio": 1.8}
    )
    assert updated is not None and updated.name == "Renamed"
    assert updated.params == {"min_volume_ratio": 1.8}

    # Catalog merges custom strategies
    catalog = await svc.list_strategies()
    keys = [s.key for s in catalog.strategies]
    assert "custom:u-1" in keys

    # Custom strategy KPI snapshots also work
    snap = await svc.compute_and_persist_snapshot("custom:u-1")
    assert snap.key == "custom:u-1"

    # And compute_all_snapshots includes custom ones
    n = await svc.compute_all_snapshots()
    assert n >= 1 + 3  # 3 built-ins + 1 custom

    deleted = await svc.delete_user_strategy("u-1")
    assert deleted is True
    assert await svc.delete_user_strategy("u-1") is False


@pytest.mark.asyncio
async def test_create_user_strategy_rejects_unknown_template() -> None:
    repo = _InMemoryRepo()
    backtest = _StubBacktest(_build_result())
    svc = StrategiesService(repo=repo, backtest_service=backtest)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        await svc.create_user_strategy(name="bad", base_template="nonexistent", params={})


@pytest.mark.asyncio
async def test_get_attribution_returns_structured_payload() -> None:
    repo = _InMemoryRepo()
    backtest = _StubBacktest(_build_result())
    svc = StrategiesService(repo=repo, backtest_service=backtest)  # type: ignore[arg-type]

    out = await svc.get_attribution("strong_uptrend", lookback_days=120)
    assert out is not None
    assert out.key == "strong_uptrend"
    assert out.lookback_days == 120
    assert out.sector_exposure[0]["sector"] == "电子"
    assert out.market_cap_buckets[0]["bucket"] == "large"
    assert any(m["period"] == "2026-01" for m in out.monthly_returns)
    assert out.yearly_returns and out.yearly_returns[0]["period"] == "2026"


@pytest.mark.asyncio
async def test_get_strategy_detail_returns_builtin() -> None:
    repo = _InMemoryRepo()
    backtest = _StubBacktest(_build_result())
    svc = StrategiesService(repo=repo, backtest_service=backtest)  # type: ignore[arg-type]
    out = await svc.get_strategy_detail("strong_uptrend")
    assert out is not None
    assert out.key == "strong_uptrend"
    assert out.is_custom is False


@pytest.mark.asyncio
async def test_get_strategy_detail_returns_custom() -> None:
    repo = _InMemoryRepo()
    backtest = _StubBacktest(_build_result())
    svc = StrategiesService(repo=repo, backtest_service=backtest)  # type: ignore[arg-type]
    created = await svc.create_user_strategy(
        name="Custom 1",
        base_template="strong_uptrend",
        params={"min_return_20d_pct": 8},
    )
    out = await svc.get_strategy_detail(custom_key(created.id))
    assert out is not None
    assert out.is_custom is True
    assert out.name == "Custom 1"
