"""Tests for MarketDataService.get_stock_quote fallback paths.

The endpoint must:
  1. Return (Quote, False) when realtime succeeds.
  2. Return (Quote, True) built from the latest+prev daily bars in DB.
  3. Return (Quote, True) with prev_close=None on the single-bar branch
     (DB empty, facade returns exactly one bar) — and not fabricate a prev_close
     from latest.open.
  4. Return None when realtime returns nothing and no bars are available.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.market_data.providers.base import Bar, Quote
from app.modules.market_data.service import MarketDataService


def _make_quote(code: str = "600519") -> Quote:
    return Quote(
        code=code,
        name="贵州茅台",
        price=1700.0,
        change=10.0,
        change_pct=0.6,
        volume=1000,
        amount=1_700_000.0,
        open=1690.0,
        high=1710.0,
        low=1685.0,
        prev_close=1690.0,
    )


def _make_db_bar(
    *,
    code: str = "600519",
    trade_date: date = date(2026, 5, 27),
    close: float = 1700.0,
    open_: float = 1690.0,
) -> SimpleNamespace:
    """DailyBar is an SQLAlchemy model — fake with SimpleNamespace."""
    return SimpleNamespace(
        code=code,
        trade_date=trade_date,
        open=open_,
        high=close,
        low=open_,
        close=close,
        volume=1000,
        amount=close * 1000,
        turnover=0.0,
    )


def _make_facade_bar(
    *,
    code: str = "600519",
    trade_date: date = date(2026, 5, 27),
    close: float = 1700.0,
    open_: float = 1690.0,
) -> Bar:
    return Bar(
        code=code,
        trade_date=trade_date,
        open=open_,
        high=close,
        low=open_,
        close=close,
        volume=1000,
        amount=close * 1000,
        turnover=0.0,
    )


@pytest.mark.asyncio
async def test_quote_realtime_success(monkeypatch):
    svc = MarketDataService()

    async def fake_realtime(codes):
        assert codes == ["600519"]
        return [_make_quote()]

    monkeypatch.setattr(svc.facade, "get_realtime_quote", fake_realtime)

    result = await svc.get_stock_quote("600519")

    assert result is not None
    quote, is_delayed = result
    assert quote.price == 1700.0
    assert is_delayed is False


@pytest.mark.asyncio
async def test_quote_fallback_db_two_bars(monkeypatch):
    svc = MarketDataService()

    async def fake_realtime(codes):
        return []

    latest = _make_db_bar(close=1700.0)
    prev = _make_db_bar(trade_date=date(2026, 5, 26), close=1680.0, open_=1675.0)

    async def fake_latest(code, before=None):
        # Repository returns the prev bar when called with `before=`,
        # otherwise the latest bar.
        return prev if before else latest

    async def fake_get_stock(code):
        return SimpleNamespace(name="贵州茅台")

    monkeypatch.setattr(svc.facade, "get_realtime_quote", fake_realtime)
    monkeypatch.setattr(svc.repo, "get_latest_daily_bar", fake_latest)
    monkeypatch.setattr(svc.repo, "get_stock", fake_get_stock)

    result = await svc.get_stock_quote("600519")

    assert result is not None
    quote, is_delayed = result
    assert is_delayed is True
    assert quote.price == 1700.0
    assert quote.prev_close == 1680.0
    assert quote.change == 20.0
    assert quote.change_pct == round(20.0 / 1680.0 * 100, 2)


@pytest.mark.asyncio
async def test_quote_fallback_facade_single_bar(monkeypatch):
    """DB empty + facade returns exactly one bar → prev_close must be None."""
    svc = MarketDataService()

    async def fake_realtime(codes):
        return []

    async def fake_latest(code, before=None):
        return None  # DB empty

    bar = _make_facade_bar(close=1700.0)
    facade_calls: list[tuple] = []

    async def fake_facade_bars(code, start, end):
        facade_calls.append((code, start, end))
        return [bar]

    async def fake_get_stock(code):
        return SimpleNamespace(name="贵州茅台")

    monkeypatch.setattr(svc.facade, "get_realtime_quote", fake_realtime)
    monkeypatch.setattr(svc.repo, "get_latest_daily_bar", fake_latest)
    monkeypatch.setattr(svc.facade, "get_daily_bars", fake_facade_bars)
    monkeypatch.setattr(svc.repo, "get_stock", fake_get_stock)

    result = await svc.get_stock_quote("600519")

    assert result is not None
    quote, is_delayed = result
    assert is_delayed is True
    assert quote.price == 1700.0
    assert quote.prev_close is None
    assert quote.change == 0.0
    assert quote.change_pct == 0.0
    # Sanity: the facade was called exactly once — confirms we no longer
    # round-trip through self.get_daily_bars (which would re-query the DB).
    assert len(facade_calls) == 1


@pytest.mark.asyncio
async def test_quote_no_data_anywhere(monkeypatch):
    svc = MarketDataService()

    async def fake_realtime(codes):
        return []

    async def fake_latest(code, before=None):
        return None

    async def fake_facade_bars(code, start, end):
        return []

    monkeypatch.setattr(svc.facade, "get_realtime_quote", fake_realtime)
    monkeypatch.setattr(svc.repo, "get_latest_daily_bar", fake_latest)
    monkeypatch.setattr(svc.facade, "get_daily_bars", fake_facade_bars)

    result = await svc.get_stock_quote("600519")

    assert result is None
