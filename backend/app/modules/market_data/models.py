from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base



class Stock(Base):
    __tablename__ = "stocks"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    industry: Mapped[str | None] = mapped_column(String(50))
    market: Mapped[str] = mapped_column(String(10))  # SH / SZ
    list_date: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now)


class DailyBar(Base):
    __tablename__ = "daily_bars"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(BigInteger)
    amount: Mapped[float] = mapped_column(Float)
    turnover: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (Index("ix_daily_bars_code_date", "code", "trade_date", unique=True),)


class DragonTigerList(Base):
    """龙虎榜"""

    __tablename__ = "dragon_tiger_lists"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    name: Mapped[str] = mapped_column(String(50))
    close_price: Mapped[float] = mapped_column(Float)
    change_pct: Mapped[float] = mapped_column(Float)
    reason: Mapped[str | None] = mapped_column(String(200))
    buy_amount: Mapped[float | None] = mapped_column(Float)
    sell_amount: Mapped[float | None] = mapped_column(Float)
    net_buy: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (Index("ix_lhb_date_code", "trade_date", "code", unique=True),)


class LimitUpBoard(Base):
    """涨停板"""

    __tablename__ = "limit_up_boards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    name: Mapped[str] = mapped_column(String(50))
    close_price: Mapped[float] = mapped_column(Float)
    change_pct: Mapped[float] = mapped_column(Float)
    limit_up_time: Mapped[str | None] = mapped_column(String(20))
    open_times: Mapped[int | None] = mapped_column(Integer)
    turnover: Mapped[float | None] = mapped_column(Float)
    reason: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (Index("ix_zt_date_code", "trade_date", "code", unique=True),)


class DailyNews(Base):
    """每日新闻"""

    __tablename__ = "daily_news"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(100))
    url: Mapped[str | None] = mapped_column(String(1000))
    code: Mapped[str | None] = mapped_column(String(10), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (Index("ix_news_date_title", "trade_date", "title", unique=True),)
