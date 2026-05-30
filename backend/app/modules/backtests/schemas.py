from datetime import date

from pydantic import BaseModel, Field


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
