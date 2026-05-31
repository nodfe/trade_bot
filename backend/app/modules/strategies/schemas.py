from datetime import date
from typing import Any

from pydantic import BaseModel, Field


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
    # Extended KPIs.
    sortino_ratio: float | None = None
    calmar_ratio: float | None = None
    turnover_pct: float | None = None
    alpha_pct: float | None = None
    monthly_returns: list[dict[str, Any]] = Field(default_factory=list)
    benchmark_equity_sparkline: list[SparklinePoint] = Field(default_factory=list)


class StrategyOut(BaseModel):
    key: str
    tags: list[str]
    default_params: dict[str, Any]
    kpi: StrategyKpiOut | None
    # Optional metadata for user-customized strategies.
    name: str | None = None
    base_template: str | None = None
    description: str | None = None
    is_custom: bool = False


class StrategiesListOut(BaseModel):
    strategies: list[StrategyOut]


# ---------------------------------------------------------------------------
# Run backtest endpoint payload.
# ---------------------------------------------------------------------------


class StrategyRunBacktestRequest(BaseModel):
    """Request body for ``POST /strategies/{key}/run-backtest``.

    All fields are optional — missing values fall back to the catalog default
    (``params``) or the engine default (``top_n``, ``rebalance``, ...).
    """

    params: dict[str, Any] | None = None
    top_n: int | None = Field(None, ge=1, le=50)
    rebalance: str | None = None
    weighting: str | None = None
    fee_bps: float | None = Field(None, ge=0, le=200)
    stop_loss_pct: float | None = Field(None, ge=0.5, le=50)
    stop_profit_pct: float | None = Field(None, ge=0.5, le=200)
    start_date: date | None = None
    end_date: date | None = None
    benchmark: str | None = None
    initial_capital: float | None = Field(None, gt=0)


# ---------------------------------------------------------------------------
# User-customized strategies CRUD.
# ---------------------------------------------------------------------------


class UserStrategyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    base_template: str = Field(..., description="Built-in catalog key to clone")
    params: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None
    owner: str = "default"


class UserStrategyUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    params: dict[str, Any] | None = None
    description: str | None = None


class UserStrategyOut(BaseModel):
    id: str
    name: str
    base_template: str
    params: dict[str, Any]
    description: str | None
    owner: str
    catalog_key: str  # "custom:{id}"
    kpi: StrategyKpiOut | None = None


# ---------------------------------------------------------------------------
# Attribution endpoint.
# ---------------------------------------------------------------------------


class StrategyAttributionOut(BaseModel):
    key: str
    lookback_days: int
    sector_exposure: list[dict[str, Any]]
    market_cap_buckets: list[dict[str, Any]]
    monthly_returns: list[dict[str, Any]]
    yearly_returns: list[dict[str, Any]]
