import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StrategyKpiSnapshot(Base):
    __tablename__ = "strategy_kpi_snapshots"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date)
    lookback_days: Mapped[int] = mapped_column(Integer)
    annualized_return_pct: Mapped[float | None] = mapped_column(Float)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float)
    win_rate_pct: Mapped[float | None] = mapped_column(Float)
    total_return_pct: Mapped[float | None] = mapped_column(Float)
    trade_count: Mapped[int] = mapped_column(Integer)
    equity_sparkline_json: Mapped[str] = mapped_column(Text)
    # Extended KPI fields (added in revision 20260530_0009)
    sortino_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    calmar_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnover_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_returns_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    benchmark_equity_sparkline_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    alpha_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class UserStrategy(Base):
    """User-customized strategy: a saved tweak of a built-in template.

    The KPI cache uses ``custom:{id}`` as the catalog key so the snapshot
    table can house both built-in and custom rows side-by-side without
    primary-key collisions.
    """

    __tablename__ = "user_strategies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(120))
    base_template: Mapped[str] = mapped_column(String(50))
    params_json: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(64), default="default")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
