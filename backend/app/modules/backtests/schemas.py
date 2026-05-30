from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.market_data.schemas import StockScreenParams


class BacktestRequest(BaseModel):
    code: str = Field(..., description="股票代码，如 600519")
    start_date: date = Field(..., description="回测开始日期")
    end_date: date = Field(..., description="回测结束日期")
    strategy: str = Field("ma_cross", description="策略类型，目前仅支持 ma_cross")
    fast_period: int = Field(5, ge=2, le=120, description="快线周期")
    slow_period: int = Field(20, ge=3, le=250, description="慢线周期")
    initial_capital: float = Field(100_000.0, gt=0, description="初始资金 (CNY)")


class BacktestTrade(BaseModel):
    """A single round-trip trade: entry → exit."""

    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    return_pct: float  # (exit - entry) / entry * 100
    holding_days: int


class EquityPoint(BaseModel):
    date: date
    value: float  # 当前账户净值（现金 + 持仓市值）


class BacktestResult(BaseModel):
    code: str
    strategy: str
    start_date: date
    end_date: date
    total_return_pct: float
    annualized_return_pct: float | None
    win_rate_pct: float
    max_drawdown_pct: float
    trade_count: int
    final_equity: float
    initial_capital: float
    trades: list[BacktestTrade]
    equity_curve: list[EquityPoint]


class EligibleCodeOut(BaseModel):
    """A stock with locally synced daily bars, eligible for backtesting."""

    code: str
    name: str
    bar_count: int


# ---------------------------------------------------------------------------
# Screener walk-forward backtest
# ---------------------------------------------------------------------------


class ScreenerBacktestRequest(BaseModel):
    screen_type: Literal["strong_uptrend", "volume_breakout", "pullback_watch"]
    screen_params_override: StockScreenParams | None = None
    start_date: date
    end_date: date
    rebalance: Literal["daily", "weekly", "biweekly", "monthly"] = "weekly"
    top_n: int = Field(10, ge=1, le=50)
    weighting: Literal["equal", "score"] = "equal"
    initial_capital: float = Field(100_000.0, gt=0)
    # Cost model (decimals, e.g. 0.00025 = 万2.5)
    commission_rate: float = Field(0.00025, ge=0, le=0.01)
    stamp_duty_rate: float = Field(0.001, ge=0, le=0.01)
    slippage_rate: float = Field(0.001, ge=0, le=0.01)
    # Risk control (None = disabled)
    stop_loss_pct: float | None = Field(None, ge=0.5, le=50)
    take_profit_pct: float | None = Field(None, ge=0.5, le=200)
    # Benchmark
    benchmark: Literal["none", "universe_buy_hold"] = "universe_buy_hold"


class HoldingItem(BaseModel):
    code: str
    name: str
    shares: int
    market_value: float
    weight_pct: float


class HoldingSnapshot(BaseModel):
    date: date
    cash: float
    equity: float
    holdings: list[HoldingItem]


class RebalanceTradeReason(str, Enum):  # noqa: UP042 — API contract uses (str, Enum)
    SCREENER_PICK = "screener_pick"
    SCREENER_DROP = "screener_drop"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    FINAL_CLOSE = "final_close"


class ScreenerBacktestTrade(BaseModel):
    """Round-trip trade with exit reason."""

    code: str
    name: str
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    shares: int
    return_pct: float
    holding_days: int
    exit_reason: RebalanceTradeReason


class CostBreakdown(BaseModel):
    total_commission: float
    total_stamp_duty: float
    total_slippage_cost: float
    cost_drag_pct: float


class DrawdownPoint(BaseModel):
    date: date
    drawdown_pct: float


class ScreenerBacktestResult(BaseModel):
    # Configuration echo
    screen_type: str
    rebalance: str
    top_n: int
    weighting: str
    start_date: date
    end_date: date
    # Headline KPIs
    total_return_pct: float
    annualized_return_pct: float | None
    win_rate_pct: float
    max_drawdown_pct: float
    trade_count: int
    final_equity: float
    initial_capital: float
    # Time-series
    equity_curve: list[EquityPoint]
    benchmark_curve: list[EquityPoint] | None
    drawdown_curve: list[DrawdownPoint]
    # Snapshots and logs
    rebalance_dates: list[date]
    holdings_history: list[HoldingSnapshot]
    trades: list[ScreenerBacktestTrade]
    costs: CostBreakdown
