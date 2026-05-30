from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StrategyKpiSnapshot(Base):
    __tablename__ = "strategy_kpi_snapshots"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date)
    lookback_days: Mapped[int] = mapped_column(Integer)
    annualized_return_pct: Mapped[float | None] = mapped_column(Float)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float)
    win_rate_pct: Mapped[float | None] = mapped_column(Float)
    total_return_pct: Mapped[float | None] = mapped_column(Float)
    trade_count: Mapped[int] = mapped_column(Integer)
    equity_sparkline_json: Mapped[str] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
