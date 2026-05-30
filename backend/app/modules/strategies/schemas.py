from datetime import date
from typing import Any

from pydantic import BaseModel


class SparklinePoint(BaseModel):
    date: date
    value: float


class StrategyKpiOut(BaseModel):
    as_of_date: date
    lookback_days: int
    annualized_return_pct: float | None
    sharpe_ratio: float | None
    max_drawdown_pct: float | None
    win_rate_pct: float | None
    total_return_pct: float | None
    trade_count: int
    equity_sparkline: list[SparklinePoint]


class StrategyOut(BaseModel):
    key: str
    tags: list[str]
    default_params: dict[str, Any]
    kpi: StrategyKpiOut | None


class StrategiesListOut(BaseModel):
    strategies: list[StrategyOut]
