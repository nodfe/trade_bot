"""Multi-strategy portfolio combo endpoint.

Runs N screener walk-forward backtests in parallel-ish (sequential await is
fine; the underlying engine is CPU-bound) and composes their equity curves
into a single weighted portfolio. Reports KPI and a correlation matrix of
per-strategy daily returns.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import date

from fastapi import APIRouter

from app.core.exceptions import BadRequestError
from app.modules.backtests.schemas import (
    EquityPoint,
    ScreenerBacktestRequest,
    ScreenerBacktestResult,
)
from app.modules.backtests.service import BacktestService
from app.modules.market_data.schemas import StockScreenParams
from app.modules.strategies.catalog import get_strategy
from app.modules.strategies.combo_schemas import (
    PerStrategyCurve,
    StrategyComboKpi,
    StrategyComboRequest,
    StrategyComboResponse,
)

router = APIRouter(prefix="/strategies", tags=["strategies"])

TRADING_DAYS_PER_YEAR = 252


def _normalize_weights(weights: Iterable[float]) -> list[float]:
    weights = list(weights)
    total = sum(weights)
    if total <= 0:
        raise BadRequestError("Sum of strategy weights must be positive")
    return [w / total for w in weights]


def _build_screener_request(item, req: StrategyComboRequest) -> ScreenerBacktestRequest:
    definition = get_strategy(item.strategy_key)
    if definition is None:
        raise BadRequestError(f"Unknown strategy: {item.strategy_key}")
    base_params: dict = dict(definition.default_params)
    if item.params_override:
        base_params.update(item.params_override)
    # Strip keys not accepted by StockScreenParams.
    allowed = set(StockScreenParams.model_fields.keys())
    base_params = {k: v for k, v in base_params.items() if k in allowed}
    params = StockScreenParams(**base_params) if base_params else StockScreenParams()
    return ScreenerBacktestRequest(
        screen_type=item.strategy_key,
        screen_params_override=params,
        start_date=req.start_date,
        end_date=req.end_date,
        rebalance=req.rebalance,
        top_n=req.top_n,
        weighting=req.weighting,
        initial_capital=req.initial_capital,
    )


def _align_curves(
    curves: list[list[EquityPoint]],
) -> tuple[list[date], list[list[float]]]:
    """Align by intersection of dates so per-day vectors are comparable.

    Returns the sorted union of dates and one normalized list per curve where
    missing days are forward-filled from the prior known value (and start at
    initial 1.0 if the curve has no value yet).
    """
    if not curves:
        return [], []
    all_dates_set: set[date] = set()
    for curve in curves:
        for pt in curve:
            all_dates_set.add(pt.date)
    all_dates = sorted(all_dates_set)
    aligned: list[list[float]] = []
    for curve in curves:
        by_date = {p.date: p.value for p in curve}
        out: list[float] = []
        last: float | None = None
        for d in all_dates:
            if d in by_date:
                last = by_date[d]
            if last is None:
                # Use first known value as base if we haven't seen any yet.
                first_val = curve[0].value if curve else 0.0
                out.append(first_val)
            else:
                out.append(last)
        aligned.append(out)
    return all_dates, aligned


def _daily_returns(values: list[float]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        if prev <= 0:
            out.append(0.0)
            continue
        out.append((values[i] - prev) / prev)
    return out


def _correlation(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    a = a[:n]
    b = b[:n]
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((x - mean_b) ** 2 for x in b)
    denom = math.sqrt(var_a * var_b)
    if denom == 0:
        return 0.0
    return cov / denom


def _compute_kpi(
    composite: list[float],
    initial_capital: float,
    start_date: date,
    end_date: date,
) -> StrategyComboKpi:
    if not composite:
        return StrategyComboKpi(
            total_return_pct=0.0,
            annualized_return_pct=None,
            sharpe_ratio=None,
            sortino_ratio=None,
            calmar_ratio=None,
            max_drawdown_pct=0.0,
        )
    final = composite[-1]
    total_return_pct = (final - initial_capital) / initial_capital * 100

    num_days = (end_date - start_date).days
    annualized_return_pct: float | None = None
    if num_days >= 30:
        annualized_return_pct = round(total_return_pct * 365 / num_days, 4)

    rets = _daily_returns(composite)
    sharpe: float | None = None
    sortino: float | None = None
    if len(rets) >= 2:
        mean = sum(rets) / len(rets)
        variance = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        std = math.sqrt(variance)
        if std > 0:
            sharpe = round(mean / std * math.sqrt(TRADING_DAYS_PER_YEAR), 4)
        downside = [r for r in rets if r < 0]
        if downside:
            d_var = sum(r**2 for r in downside) / len(downside)
            d_std = math.sqrt(d_var)
            if d_std > 0:
                sortino = round(mean / d_std * math.sqrt(TRADING_DAYS_PER_YEAR), 4)

    # Max drawdown.
    peak = float("-inf")
    max_dd = 0.0
    for v in composite:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd

    calmar: float | None = None
    if annualized_return_pct is not None and max_dd > 0:
        calmar = round(annualized_return_pct / max_dd, 4)

    return StrategyComboKpi(
        total_return_pct=round(total_return_pct, 4),
        annualized_return_pct=annualized_return_pct,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        max_drawdown_pct=round(max_dd, 4),
    )


async def run_combo_backtest(
    req: StrategyComboRequest,
    backtest_service: BacktestService | None = None,
) -> StrategyComboResponse:
    """Compose multiple screener backtests into a weighted portfolio."""
    if req.start_date >= req.end_date:
        raise BadRequestError("start_date must be earlier than end_date")
    bt = backtest_service or BacktestService()

    weights = _normalize_weights(item.weight for item in req.items)

    sub_results: list[ScreenerBacktestResult] = []
    for item in req.items:
        sr = await bt.run_screener_backtest(_build_screener_request(item, req))
        sub_results.append(sr)

    curves = [r.equity_curve for r in sub_results]
    aligned_dates, aligned_values = _align_curves(curves)

    # Composite equity = sum_i w_i * (equity_i / initial_capital_i) * initial_capital_combo
    composite: list[float] = []
    if aligned_dates:
        for d_idx in range(len(aligned_dates)):
            value = 0.0
            for i, sub_vals in enumerate(aligned_values):
                base = sub_results[i].initial_capital
                if base <= 0:
                    continue
                value += weights[i] * (sub_vals[d_idx] / base)
            composite.append(value * req.initial_capital)

    composite_curve = [
        EquityPoint(date=d, value=round(v, 4))
        for d, v in zip(aligned_dates, composite, strict=False)
    ]

    # Per-strategy normalized curves (same x-axis, scaled to combo capital
    # for visual comparability).
    per_strategy_curves: list[PerStrategyCurve] = []
    for i, item in enumerate(req.items):
        base = sub_results[i].initial_capital or 1.0
        scaled = [
            EquityPoint(date=d, value=round(v / base * req.initial_capital, 4))
            for d, v in zip(aligned_dates, aligned_values[i], strict=False)
        ]
        per_strategy_curves.append(
            PerStrategyCurve(
                strategy_key=item.strategy_key,
                weight_normalized=round(weights[i], 6),
                equity_curve=scaled,
            )
        )

    # Correlation matrix on daily returns.
    daily_rets = [_daily_returns(vals) for vals in aligned_values]
    keys = [item.strategy_key for item in req.items]
    # Resolve duplicate strategy keys (combo can repeat with different params).
    matrix_keys: list[str] = []
    seen: dict[str, int] = {}
    for k in keys:
        seen[k] = seen.get(k, 0) + 1
        matrix_keys.append(k if seen[k] == 1 else f"{k}#{seen[k]}")

    correlation: dict[str, dict[str, float]] = {}
    for i, ki in enumerate(matrix_keys):
        correlation[ki] = {}
        for j, kj in enumerate(matrix_keys):
            if i == j:
                correlation[ki][kj] = 1.0
            else:
                correlation[ki][kj] = round(_correlation(daily_rets[i], daily_rets[j]), 6)

    kpi = _compute_kpi(composite, req.initial_capital, req.start_date, req.end_date)

    return StrategyComboResponse(
        composite_equity_curve=composite_curve,
        per_strategy_curves=per_strategy_curves,
        correlation_matrix=correlation,
        kpi=kpi,
        start_date=req.start_date,
        end_date=req.end_date,
        rebalance=req.rebalance,
        initial_capital=req.initial_capital,
    )


@router.post("/combo", response_model=StrategyComboResponse)
async def post_strategies_combo(
    payload: StrategyComboRequest,
) -> StrategyComboResponse:
    return await run_combo_backtest(payload)
