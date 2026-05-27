from abc import ABC, abstractmethod
from datetime import date, datetime

from pydantic import BaseModel


class Bar(BaseModel):
    code: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    turnover: float | None = None


class Quote(BaseModel):
    code: str
    name: str
    price: float
    change: float
    change_pct: float
    volume: int
    amount: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    prev_close: float | None = None


class StockInfo(BaseModel):
    code: str
    name: str
    industry: str | None = None
    market: str | None = None
    list_date: date | None = None


class MarketDataSource(ABC):
    @abstractmethod
    async def get_daily_bars(self, code: str, start_date: date, end_date: date) -> list[Bar]:
        ...

    @abstractmethod
    async def get_realtime_quote(self, codes: list[str]) -> list[Quote]:
        ...

    @abstractmethod
    async def get_stock_list(self) -> list[StockInfo]:
        ...


class DragonTigerItem(BaseModel):
    trade_date: date
    code: str
    name: str
    close_price: float
    change_pct: float
    reason: str | None = None
    buy_amount: float | None = None
    sell_amount: float | None = None
    net_buy: float | None = None


class LimitUpItem(BaseModel):
    trade_date: date
    code: str
    name: str
    close_price: float
    change_pct: float
    limit_up_time: str | None = None
    open_times: int | None = None
    turnover: float | None = None
    reason: str | None = None


class NewsItem(BaseModel):
    trade_date: date
    title: str
    content: str | None = None
    source: str | None = None
    url: str | None = None
    code: str | None = None
    published_at: datetime | None = None
