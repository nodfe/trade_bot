"""Pydantic schemas for the multi-strategy combo backtest endpoint."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.modules.backtests.schemas import EquityPoint


class StrategyComboItem(BaseModel):
    strategy_key: Literal["strong_uptrend", "volume_breakout", "pullback_watch"]
    weight: float = Field(..., gt=0, description="组合权重，相对值；后端会归一化")
    params_override: dict[str, Any] | None = None


class StrategyComboRequest(BaseModel):
    items: list[StrategyComboItem] = Field(..., min_length=1, max_length=10)
    rebalance: Literal["daily", "weekly", "biweekly", "monthly"] = "weekly"
    start_date: date
    end_date: date
    top_n: int = Field(10, ge=1, le=50)
    weighting: Literal["equal", "score"] = "equal"
    initial_capital: float = Field(100_000.0, gt=0)


class StrategyComboKpi(BaseModel):
    total_return_pct: float
    annualized_return_pct: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    calmar_ratio: float | None
    max_drawdown_pct: float


class PerStrategyCurve(BaseModel):
    strategy_key: str
    weight_normalized: float
    equity_curve: list[EquityPoint]


class StrategyComboResponse(BaseModel):
    composite_equity_curve: list[EquityPoint]
    per_strategy_curves: list[PerStrategyCurve]
    correlation_matrix: dict[str, dict[str, float]]
    kpi: StrategyComboKpi
    start_date: date
    end_date: date
    rebalance: str
    initial_capital: float
