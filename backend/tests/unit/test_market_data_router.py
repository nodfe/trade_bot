from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.modules.market_data.router import svc
from app.modules.market_data.schemas import MarketOverviewOut

client = TestClient(app)


def test_market_overview_endpoint(monkeypatch):
    async def fake_get_market_overview() -> MarketOverviewOut:
        return MarketOverviewOut(
            stock_count=5234,
            latest_trade_date=date(2026, 5, 27),
            latest_dragon_tiger_date=date(2026, 5, 27),
            latest_limit_up_date=date(2026, 5, 27),
            latest_news_date=date(2026, 5, 27),
            latest_dragon_tiger_count=42,
            latest_limit_up_count=18,
            latest_news_count=66,
        )

    monkeypatch.setattr(svc, "get_market_overview", fake_get_market_overview)

    response = client.get("/api/v1/market/overview")

    assert response.status_code == 200
    assert response.json() == {
        "stock_count": 5234,
        "latest_trade_date": "2026-05-27",
        "latest_dragon_tiger_date": "2026-05-27",
        "latest_limit_up_date": "2026-05-27",
        "latest_news_date": "2026-05-27",
        "latest_dragon_tiger_count": 42,
        "latest_limit_up_count": 18,
        "latest_news_count": 66,
    }


def test_stock_quote_endpoint(monkeypatch):
    async def fake_get_stock_quote(code: str):
        assert code == "600519"
        return (
            SimpleNamespace(
                code="600519",
                name="贵州茅台",
                price=1688.0,
                change=12.5,
                change_pct=0.75,
                volume=123456,
                amount=987654321.0,
                high=1690.0,
                low=1660.0,
                open=1670.0,
                prev_close=1675.5,
            ),
            False,
        )

    monkeypatch.setattr(svc, "get_stock_quote", fake_get_stock_quote)
    monkeypatch.setattr(svc, "quote_timestamp", lambda: datetime(2026, 5, 27, 10, 30, tzinfo=UTC))

    response = client.get("/api/v1/stocks/600519/quote")

    assert response.status_code == 200
    assert response.json() == {
        "symbol": "600519",
        "name": "贵州茅台",
        "price": 1688.0,
        "change": 12.5,
        "change_percent": 0.75,
        "volume": 123456,
        "turnover": 987654321.0,
        "high": 1690.0,
        "low": 1660.0,
        "open": 1670.0,
        "prev_close": 1675.5,
        "timestamp": "2026-05-27T10:30:00Z",
        "is_delayed": False,
    }


def test_stock_quote_endpoint_delayed(monkeypatch):
    """When realtime is unavailable, the router should propagate is_delayed=True."""

    async def fake_get_stock_quote(code: str):
        return (
            SimpleNamespace(
                code="600519",
                name="贵州茅台",
                price=1700.0,
                change=20.0,
                change_pct=1.19,
                volume=1000,
                amount=1_700_000.0,
                high=1710.0,
                low=1685.0,
                open=1690.0,
                prev_close=1680.0,
            ),
            True,
        )

    monkeypatch.setattr(svc, "get_stock_quote", fake_get_stock_quote)
    monkeypatch.setattr(svc, "quote_timestamp", lambda: datetime(2026, 5, 27, 10, 30, tzinfo=UTC))

    response = client.get("/api/v1/stocks/600519/quote")

    assert response.status_code == 200
    assert response.json()["is_delayed"] is True


def test_stock_detail_endpoint(monkeypatch):
    async def fake_get_stock(code: str):
        assert code == "600519"
        return SimpleNamespace(
            code="600519",
            name="贵州茅台",
            industry="饮料制造",
            market="SH",
            list_date=date(2001, 8, 27),
        )

    monkeypatch.setattr(svc, "get_stock", fake_get_stock)

    response = client.get("/api/v1/stocks/600519")

    assert response.status_code == 200
    assert response.json() == {
        "code": "600519",
        "name": "贵州茅台",
        "industry": "饮料制造",
        "market": "SH",
        "list_date": "2001-08-27",
    }


def test_stock_analysis_endpoint(monkeypatch):
    async def fake_get_stock_analysis_summary(code: str):
        assert code == "600519"
        return SimpleNamespace(
            symbol="600519",
            latest_close=1688.0,
            ma5=1666.2,
            ma20=1610.5,
            rsi14=62.4,
            macd=4.12,
            macd_signal=3.88,
            macd_histogram=0.24,
            price_vs_ma5_pct=1.31,
            price_vs_ma20_pct=4.81,
            return_5d_pct=3.22,
            return_20d_pct=8.64,
            volume_ratio_5d=1.18,
            trend_bias="bullish",
            summary=(
                "短中期趋势偏强，较 MA5 +1.31%，较 MA20 +4.81%，"
                "近20日 +8.64%，量比(5日) 1.18x。"
            ),
            signals=[
                {"name": "趋势结构", "detail": "均线与阶段收益共振偏强"},
                {"name": "RSI", "detail": "RSI 位于中性区，动量平衡"},
            ],
        )

    monkeypatch.setattr(svc, "get_stock_analysis_summary", fake_get_stock_analysis_summary)

    response = client.get("/api/v1/stocks/600519/analysis")

    assert response.status_code == 200
    assert response.json() == {
        "symbol": "600519",
        "latest_close": 1688.0,
        "ma5": 1666.2,
        "ma20": 1610.5,
        "rsi14": 62.4,
        "macd": 4.12,
        "macd_signal": 3.88,
        "macd_histogram": 0.24,
        "price_vs_ma5_pct": 1.31,
        "price_vs_ma20_pct": 4.81,
        "return_5d_pct": 3.22,
        "return_20d_pct": 8.64,
        "volume_ratio_5d": 1.18,
        "trend_bias": "bullish",
        "summary": (
            "短中期趋势偏强，较 MA5 +1.31%，较 MA20 +4.81%，"
            "近20日 +8.64%，量比(5日) 1.18x。"
        ),
        "signals": [
            {"name": "趋势结构", "detail": "均线与阶段收益共振偏强"},
            {"name": "RSI", "detail": "RSI 位于中性区，动量平衡"},
        ],
    }


def test_stock_screen_endpoint(monkeypatch):
    async def fake_screen_stocks(screen_type: str, params):
        assert screen_type == "strong_uptrend"
        assert params.limit == 3
        assert params.min_return_20d_pct == 7
        return SimpleNamespace(
            screen_type="strong_uptrend",
            total=1,
            items=[
                {
                    "symbol": "600519",
                    "name": "贵州茅台",
                    "market": "SH",
                    "industry": "饮料制造",
                    "latest_close": 1688.0,
                    "return_5d_pct": 3.22,
                    "return_20d_pct": 8.64,
                    "volume_ratio_5d": 1.18,
                    "trend_bias": "bullish",
                    "match_reason": "多头趋势延续，20日收益与 RSI 共振偏强",
                    "is_on_dragon_tiger": True,
                    "is_limit_up_candidate": False,
                    "hot_tags": ["龙虎榜", "相关新闻"],
                    "related_news_headlines": ["茅台板块关注度上升"],
                }
            ],
        )

    monkeypatch.setattr(svc, "screen_stocks", fake_screen_stocks)

    response = client.get(
        "/api/v1/analysis/screen",
        params={"screen_type": "strong_uptrend", "limit": 3, "min_return_20d_pct": 7},
    )

    assert response.status_code == 200
    assert response.json() == {
        "screen_type": "strong_uptrend",
        "total": 1,
        "items": [
            {
                "symbol": "600519",
                "name": "贵州茅台",
                "market": "SH",
                "industry": "饮料制造",
                "latest_close": 1688.0,
                "return_5d_pct": 3.22,
                "return_20d_pct": 8.64,
                "volume_ratio_5d": 1.18,
                "trend_bias": "bullish",
                "match_reason": "多头趋势延续，20日收益与 RSI 共振偏强",
                "is_on_dragon_tiger": True,
                "is_limit_up_candidate": False,
                "hot_tags": ["龙虎榜", "相关新闻"],
                "related_news_headlines": ["茅台板块关注度上升"],
            }
        ],
    }


def test_stock_kline_endpoint(monkeypatch):
    async def fake_get_stock_kline(
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 120,
        period: str = "daily",
    ):
        assert code == "600519"
        assert limit == 2
        assert start_date == date(2026, 5, 26)
        assert end_date == date(2026, 5, 27)
        assert period == "daily"
        return [
            SimpleNamespace(
                trade_date=date(2026, 5, 26),
                open=1660.0,
                high=1678.0,
                low=1652.0,
                close=1671.0,
                volume=100000,
            ),
            SimpleNamespace(
                trade_date=date(2026, 5, 27),
                open=1670.0,
                high=1690.0,
                low=1660.0,
                close=1688.0,
                volume=123456,
            ),
        ]

    monkeypatch.setattr(svc, "get_stock_kline", fake_get_stock_kline)

    response = client.get(
        "/api/v1/stocks/kline",
        params={
            "symbol": "600519",
            "start": "2026-05-26",
            "end": "2026-05-27",
            "limit": 2,
        },
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "timestamp": "2026-05-26T00:00:00",
            "open": 1660.0,
            "high": 1678.0,
            "low": 1652.0,
            "close": 1671.0,
            "volume": 100000,
        },
        {
            "timestamp": "2026-05-27T00:00:00",
            "open": 1670.0,
            "high": 1690.0,
            "low": 1660.0,
            "close": 1688.0,
            "volume": 123456,
        },
    ]
