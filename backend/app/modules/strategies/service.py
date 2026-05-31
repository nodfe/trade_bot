from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta
from typing import Any

from loguru import logger

from app.modules.backtests.schemas import (
    ScreenerBacktestRequest,
    ScreenerBacktestResult,
)
from app.modules.backtests.service import BacktestService
from app.modules.market_data.schemas import StockScreenParams
from app.modules.strategies.catalog import (
    STRATEGY_CATALOG,
    StrategyDefinition,
    get_strategy,
)
from app.modules.strategies.models import StrategyKpiSnapshot, UserStrategy
from app.modules.strategies.repository import StrategiesRepository
from app.modules.strategies.schemas import (
    SparklinePoint,
    StrategiesListOut,
    StrategyAttributionOut,
    StrategyKpiOut,
    StrategyOut,
    UserStrategyOut,
)

LOOKBACK_DAYS = 180
SPARKLINE_MAX_POINTS = 60
TRADING_DAYS_PER_YEAR = 252
CUSTOM_PREFIX = "custom:"


def custom_key(sid: str) -> str:
    return f"{CUSTOM_PREFIX}{sid}"


def is_custom_key(key: str) -> bool:
    return key.startswith(CUSTOM_PREFIX)


class StrategiesService:
    def __init__(
        self,
        repo: StrategiesRepository | None = None,
        backtest_service: BacktestService | None = None,
    ) -> None:
        self.repo = repo or StrategiesRepository()
        self.backtest_service = backtest_service or BacktestService()

    # ------------------------------------------------------------------
    # Catalog listing.
    # ------------------------------------------------------------------

    async def list_strategies(self) -> StrategiesListOut:
        snapshots = await self.repo.get_all_snapshots()
        out: list[StrategyOut] = []
        for definition in STRATEGY_CATALOG:
            snapshot = snapshots.get(definition.key)
            kpi = _snapshot_to_kpi(snapshot) if snapshot is not None else None
            out.append(
                StrategyOut(
                    key=definition.key,
                    tags=list(definition.tags),
                    default_params=dict(definition.default_params),
                    kpi=kpi,
                    is_custom=False,
                )
            )

        # Append user-customized strategies after the built-in catalog.
        try:
            user_rows = await self.repo.list_user_strategies()
        except Exception as exc:  # pragma: no cover - DB errors propagated
            logger.warning(
                f"strategies.list_user_strategies failed; returning built-ins only. error={exc}"
            )
            user_rows = []
        for row in user_rows:
            ckey = custom_key(row.id)
            snapshot = snapshots.get(ckey)
            kpi = _snapshot_to_kpi(snapshot) if snapshot is not None else None
            params = _safe_load_params(row.params_json)
            base_def = get_strategy(row.base_template)
            tags = list(base_def.tags) if base_def is not None else []
            out.append(
                StrategyOut(
                    key=ckey,
                    tags=tags,
                    default_params=params,
                    kpi=kpi,
                    name=row.name,
                    base_template=row.base_template,
                    description=row.description,
                    is_custom=True,
                )
            )
        return StrategiesListOut(strategies=out)

    async def get_strategy_detail(self, key: str) -> StrategyOut | None:
        """Return a single ``StrategyOut`` for either a built-in or custom key."""
        snapshots = await self.repo.get_all_snapshots()
        if is_custom_key(key):
            row = await self.repo.get_user_strategy(_strip_custom(key))
            if row is None:
                return None
            kpi = _snapshot_to_kpi(snapshots.get(key)) if snapshots.get(key) is not None else None
            params = _safe_load_params(row.params_json)
            base_def = get_strategy(row.base_template)
            return StrategyOut(
                key=key,
                tags=list(base_def.tags) if base_def is not None else [],
                default_params=params,
                kpi=kpi,
                name=row.name,
                base_template=row.base_template,
                description=row.description,
                is_custom=True,
            )
        definition = get_strategy(key)
        if definition is None:
            return None
        snapshot = snapshots.get(definition.key)
        return StrategyOut(
            key=definition.key,
            tags=list(definition.tags),
            default_params=dict(definition.default_params),
            kpi=_snapshot_to_kpi(snapshot) if snapshot is not None else None,
            is_custom=False,
        )

    # ------------------------------------------------------------------
    # KPI snapshot computation (built-in + custom strategies).
    # ------------------------------------------------------------------

    async def _resolve_screen_definition(self, key: str) -> tuple[str, dict[str, Any]] | None:
        """Resolve a catalog key to ``(screen_type, default_params)``.

        For custom strategies, ``screen_type`` is the underlying built-in
        template and ``default_params`` is the saved override payload.
        """
        if is_custom_key(key):
            sid = _strip_custom(key)
            row = await self.repo.get_user_strategy(sid)
            if row is None:
                return None
            return row.base_template, _safe_load_params(row.params_json)
        definition = get_strategy(key)
        if definition is None:
            return None
        return definition.key, dict(definition.default_params)

    async def compute_and_persist_snapshot(self, key: str) -> StrategyKpiSnapshot:
        resolved = await self._resolve_screen_definition(key)
        if resolved is None:
            raise ValueError(f"Unknown strategy key: {key}")
        screen_type, params_dict = resolved

        end_date = date.today()
        start_date = end_date - timedelta(days=LOOKBACK_DAYS)
        params_override = StockScreenParams(**_filter_screen_params(params_dict))
        req = ScreenerBacktestRequest(
            screen_type=screen_type,
            screen_params_override=params_override,
            start_date=start_date,
            end_date=end_date,
            rebalance="weekly",
            top_n=10,
            weighting="equal",
        )

        result = await self.backtest_service.run_screener_backtest(req)
        snapshot = self._snapshot_from_result(key, end_date, result)
        await self.repo.upsert_snapshot(snapshot)
        return snapshot

    async def compute_all_snapshots(self) -> int:
        success = 0
        keys: list[str] = [d.key for d in STRATEGY_CATALOG]
        try:
            user_rows = await self.repo.list_user_strategies()
            keys.extend(custom_key(r.id) for r in user_rows)
        except Exception as exc:  # pragma: no cover
            logger.warning(
                f"strategies.compute_all_snapshots: list_user_strategies "
                f"failed, computing built-ins only. error={exc}"
            )
        for key in keys:
            try:
                await self.compute_and_persist_snapshot(key)
                success += 1
            except Exception as exc:
                logger.exception(
                    f"strategies.compute_and_persist_snapshot failed key={key} error={exc}"
                )
        return success

    # ------------------------------------------------------------------
    # Override-driven backtest runner.
    # ------------------------------------------------------------------

    async def run_backtest_override(
        self,
        key: str,
        *,
        params: dict[str, Any] | None = None,
        top_n: int | None = None,
        rebalance: str | None = None,
        weighting: str | None = None,
        fee_bps: float | None = None,
        stop_loss_pct: float | None = None,
        stop_profit_pct: float | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        benchmark: str | None = None,
        initial_capital: float | None = None,
    ) -> ScreenerBacktestResult:
        resolved = await self._resolve_screen_definition(key)
        if resolved is None:
            raise ValueError(f"Unknown strategy key: {key}")
        screen_type, default_params = resolved
        merged_params = dict(default_params)
        if params:
            merged_params.update(params)

        end_dt = end_date or date.today()
        start_dt = start_date or (end_dt - timedelta(days=LOOKBACK_DAYS))

        kwargs: dict[str, Any] = {
            "screen_type": screen_type,
            "screen_params_override": StockScreenParams(**_filter_screen_params(merged_params)),
            "start_date": start_dt,
            "end_date": end_dt,
        }
        if top_n is not None:
            kwargs["top_n"] = top_n
        if rebalance is not None:
            kwargs["rebalance"] = rebalance
        if weighting is not None:
            kwargs["weighting"] = weighting
        if fee_bps is not None:
            kwargs["fee_bps"] = fee_bps
        if stop_loss_pct is not None:
            kwargs["stop_loss_pct"] = stop_loss_pct
        if stop_profit_pct is not None:
            kwargs["stop_profit_pct"] = stop_profit_pct
        if benchmark is not None:
            kwargs["benchmark"] = benchmark
        if initial_capital is not None:
            kwargs["initial_capital"] = initial_capital

        req = ScreenerBacktestRequest(**kwargs)
        return await self.backtest_service.run_screener_backtest(req)

    # ------------------------------------------------------------------
    # Attribution endpoint.
    # ------------------------------------------------------------------

    async def get_attribution(
        self, key: str, lookback_days: int = LOOKBACK_DAYS
    ) -> StrategyAttributionOut | None:
        resolved = await self._resolve_screen_definition(key)
        if resolved is None:
            return None
        end_dt = date.today()
        start_dt = end_dt - timedelta(days=lookback_days)
        result = await self.run_backtest_override(key, start_date=start_dt, end_date=end_dt)
        attribution = result.attribution
        if attribution is None:
            return StrategyAttributionOut(
                key=key,
                lookback_days=lookback_days,
                sector_exposure=[],
                market_cap_buckets=[],
                monthly_returns=[],
                yearly_returns=[],
            )
        return StrategyAttributionOut(
            key=key,
            lookback_days=lookback_days,
            sector_exposure=[s.model_dump() for s in attribution.sector_exposure],
            market_cap_buckets=[b.model_dump() for b in attribution.market_cap_buckets],
            monthly_returns=[m.model_dump() for m in attribution.monthly_returns],
            yearly_returns=[y.model_dump() for y in attribution.yearly_returns],
        )

    # ------------------------------------------------------------------
    # User-customized strategies CRUD.
    # ------------------------------------------------------------------

    async def list_user_strategies(self) -> list[UserStrategyOut]:
        rows = await self.repo.list_user_strategies()
        snapshots = await self.repo.get_all_snapshots()
        return [self._user_strategy_to_out(row, snapshots) for row in rows]

    async def get_user_strategy(self, sid: str) -> UserStrategyOut | None:
        row = await self.repo.get_user_strategy(sid)
        if row is None:
            return None
        snapshots = await self.repo.get_all_snapshots()
        return self._user_strategy_to_out(row, snapshots)

    async def create_user_strategy(
        self,
        *,
        name: str,
        base_template: str,
        params: dict[str, Any],
        owner: str = "default",
        description: str | None = None,
    ) -> UserStrategyOut:
        if get_strategy(base_template) is None:
            raise ValueError(f"Unknown base_template: {base_template}")
        row = await self.repo.create_user_strategy(
            name=name,
            base_template=base_template,
            params=params,
            owner=owner,
            description=description,
        )
        return self._user_strategy_to_out(row, {})

    async def update_user_strategy(
        self,
        sid: str,
        *,
        name: str | None = None,
        params: dict[str, Any] | None = None,
        description: str | None = None,
    ) -> UserStrategyOut | None:
        row = await self.repo.update_user_strategy(
            sid, name=name, params=params, description=description
        )
        if row is None:
            return None
        snapshots = await self.repo.get_all_snapshots()
        return self._user_strategy_to_out(row, snapshots)

    async def delete_user_strategy(self, sid: str) -> bool:
        return await self.repo.delete_user_strategy(sid)

    # ------------------------------------------------------------------
    # Internal helpers.
    # ------------------------------------------------------------------

    @staticmethod
    def _user_strategy_to_out(
        row: UserStrategy, snapshots: dict[str, StrategyKpiSnapshot]
    ) -> UserStrategyOut:
        ckey = custom_key(row.id)
        snap = snapshots.get(ckey)
        kpi = _snapshot_to_kpi(snap) if snap is not None else None
        return UserStrategyOut(
            id=row.id,
            name=row.name,
            base_template=row.base_template,
            params=_safe_load_params(row.params_json),
            description=row.description,
            owner=row.owner,
            catalog_key=ckey,
            kpi=kpi,
        )

    @staticmethod
    def _snapshot_from_result(
        key: str, as_of: date, result: ScreenerBacktestResult
    ) -> StrategyKpiSnapshot:
        sparkline = _downsample_equity(result.equity_curve, SPARKLINE_MAX_POINTS)
        sparkline_json = json.dumps(
            [{"date": p.date.isoformat(), "value": p.value} for p in sparkline]
        )

        bench_sparkline_json: str | None = None
        if result.benchmark_curve:
            bench_pts = _downsample_equity(result.benchmark_curve, SPARKLINE_MAX_POINTS)
            bench_sparkline_json = json.dumps(
                [{"date": p.date.isoformat(), "value": p.value} for p in bench_pts]
            )

        monthly_json: str | None = None
        if result.monthly_returns:
            monthly_json = json.dumps([m.model_dump() for m in result.monthly_returns])

        sharpe = (
            result.sharpe_ratio
            if result.sharpe_ratio is not None
            else _compute_sharpe(result.equity_curve)
        )
        return StrategyKpiSnapshot(
            key=key,
            as_of_date=as_of,
            lookback_days=LOOKBACK_DAYS,
            annualized_return_pct=result.annualized_return_pct,
            sharpe_ratio=sharpe,
            max_drawdown_pct=result.max_drawdown_pct,
            win_rate_pct=result.win_rate_pct,
            total_return_pct=result.total_return_pct,
            trade_count=result.trade_count,
            equity_sparkline_json=sparkline_json,
            sortino_ratio=result.sortino_ratio,
            calmar_ratio=result.calmar_ratio,
            turnover_pct=result.turnover_pct,
            alpha_pct=result.alpha_pct,
            monthly_returns_json=monthly_json,
            benchmark_equity_sparkline_json=bench_sparkline_json,
            computed_at=datetime.now(),
        )


# ---------------------------------------------------------------------------
# Module-level helpers.
# ---------------------------------------------------------------------------


_ALLOWED_SCREEN_PARAM_KEYS = {
    "limit",
    "min_return_20d_pct",
    "min_return_5d_pct",
    "min_volume_ratio",
    "max_return_5d_pct",
    "require_macd_positive",
    "max_candidates",
}


def _filter_screen_params(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if k in _ALLOWED_SCREEN_PARAM_KEYS}


def _safe_load_params(payload: str | None) -> dict[str, Any]:
    if not payload:
        return {}
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _strip_custom(key: str) -> str:
    return key[len(CUSTOM_PREFIX) :] if is_custom_key(key) else key


def _snapshot_to_kpi(snapshot: StrategyKpiSnapshot) -> StrategyKpiOut:
    raw_points = json.loads(snapshot.equity_sparkline_json or "[]")
    sparkline = [
        SparklinePoint(date=date.fromisoformat(pt["date"]), value=float(pt["value"]))
        for pt in raw_points
    ]
    bench_points: list[SparklinePoint] = []
    if snapshot.benchmark_equity_sparkline_json:
        for pt in json.loads(snapshot.benchmark_equity_sparkline_json):
            bench_points.append(
                SparklinePoint(date=date.fromisoformat(pt["date"]), value=float(pt["value"]))
            )
    monthly_returns: list[dict[str, Any]] = []
    if snapshot.monthly_returns_json:
        try:
            monthly_returns = json.loads(snapshot.monthly_returns_json)
        except json.JSONDecodeError:
            monthly_returns = []
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
        sortino_ratio=snapshot.sortino_ratio,
        calmar_ratio=snapshot.calmar_ratio,
        turnover_pct=snapshot.turnover_pct,
        alpha_pct=snapshot.alpha_pct,
        monthly_returns=monthly_returns,
        benchmark_equity_sparkline=bench_points,
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
    "custom_key",
    "is_custom_key",
]
