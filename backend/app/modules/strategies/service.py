from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta

from loguru import logger

from app.modules.backtests.schemas import ScreenerBacktestRequest
from app.modules.backtests.service import BacktestService
from app.modules.market_data.schemas import StockScreenParams
from app.modules.strategies.catalog import (
    STRATEGY_CATALOG,
    StrategyDefinition,
    get_strategy,
)
from app.modules.strategies.models import StrategyKpiSnapshot
from app.modules.strategies.repository import StrategiesRepository
from app.modules.strategies.schemas import (
    SparklinePoint,
    StrategiesListOut,
    StrategyKpiOut,
    StrategyOut,
)

LOOKBACK_DAYS = 180
SPARKLINE_MAX_POINTS = 60
TRADING_DAYS_PER_YEAR = 252


class StrategiesService:
    def __init__(
        self,
        repo: StrategiesRepository | None = None,
        backtest_service: BacktestService | None = None,
    ) -> None:
        self.repo = repo or StrategiesRepository()
        self.backtest_service = backtest_service or BacktestService()

    async def list_strategies(self) -> StrategiesListOut:
        snapshots = await self.repo.get_all_snapshots()
        out: list[StrategyOut] = []
        for definition in STRATEGY_CATALOG:
            snapshot = snapshots.get(definition.key)
            kpi: StrategyKpiOut | None = None
            if snapshot is not None:
                kpi = _snapshot_to_kpi(snapshot)
            out.append(
                StrategyOut(
                    key=definition.key,
                    tags=list(definition.tags),
                    default_params=dict(definition.default_params),
                    kpi=kpi,
                )
            )
        return StrategiesListOut(strategies=out)

    async def compute_and_persist_snapshot(self, key: str) -> StrategyKpiSnapshot:
        definition = get_strategy(key)
        if definition is None:
            raise ValueError(f"Unknown strategy key: {key}")

        end_date = date.today()
        start_date = end_date - timedelta(days=LOOKBACK_DAYS)
        params_override = StockScreenParams(**definition.default_params)
        req = ScreenerBacktestRequest(
            screen_type=definition.key,
            screen_params_override=params_override,
            start_date=start_date,
            end_date=end_date,
            rebalance="weekly",
            top_n=10,
            weighting="equal",
        )

        result = await self.backtest_service.run_screener_backtest(req)

        sharpe = _compute_sharpe(result.equity_curve)
        sparkline = _downsample_equity(result.equity_curve, SPARKLINE_MAX_POINTS)
        sparkline_json = json.dumps(
            [{"date": p.date.isoformat(), "value": p.value} for p in sparkline]
        )

        snapshot = StrategyKpiSnapshot(
            key=definition.key,
            as_of_date=end_date,
            lookback_days=LOOKBACK_DAYS,
            annualized_return_pct=result.annualized_return_pct,
            sharpe_ratio=sharpe,
            max_drawdown_pct=result.max_drawdown_pct,
            win_rate_pct=result.win_rate_pct,
            total_return_pct=result.total_return_pct,
            trade_count=result.trade_count,
            equity_sparkline_json=sparkline_json,
            computed_at=datetime.now(),
        )
        await self.repo.upsert_snapshot(snapshot)
        return snapshot

    async def compute_all_snapshots(self) -> int:
        success = 0
        for definition in STRATEGY_CATALOG:
            try:
                await self.compute_and_persist_snapshot(definition.key)
                success += 1
            except Exception as exc:
                logger.exception(
                    f"strategies.compute_and_persist_snapshot failed "
                    f"key={definition.key} error={exc}"
                )
        return success


def _snapshot_to_kpi(snapshot: StrategyKpiSnapshot) -> StrategyKpiOut:
    raw_points = json.loads(snapshot.equity_sparkline_json or "[]")
    sparkline = [
        SparklinePoint(date=date.fromisoformat(pt["date"]), value=float(pt["value"]))
        for pt in raw_points
    ]
    return StrategyKpiOut(
        as_of_date=snapshot.as_of_date,
        lookback_days=snapshot.lookback_days,
        annualized_return_pct=snapshot.annualized_return_pct,
        sharpe_ratio=snapshot.sharpe_ratio,
        max_drawdown_pct=snapshot.max_drawdown_pct,
        win_rate_pct=snapshot.win_rate_pct,
        total_return_pct=snapshot.total_return_pct,
        trade_count=snapshot.trade_count,
        equity_sparkline=sparkline,
    )


def _compute_sharpe(equity_curve: list) -> float | None:
    if len(equity_curve) < 2:
        return None
    daily_returns: list[float] = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1].value
        curr = equity_curve[i].value
        if prev <= 0:
            continue
        daily_returns.append((curr - prev) / prev)
    n = len(daily_returns)
    if n < 2:
        return None
    mean = sum(daily_returns) / n
    variance = sum((r - mean) ** 2 for r in daily_returns) / (n - 1)
    std = math.sqrt(variance)
    if std == 0:
        return None
    sharpe = mean / std * math.sqrt(TRADING_DAYS_PER_YEAR)
    return round(sharpe, 4)


def _downsample_equity(equity_curve: list, max_points: int) -> list:
    if not equity_curve:
        return []
    n = len(equity_curve)
    if n <= max_points:
        return list(equity_curve)
    stride = math.ceil(n / max_points)
    sampled = [equity_curve[i] for i in range(0, n, stride)]
    if sampled[-1] is not equity_curve[-1]:
        sampled.append(equity_curve[-1])
    return sampled


__all__ = [
    "StrategiesService",
    "StrategyDefinition",
]
