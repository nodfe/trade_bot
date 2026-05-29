from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Query

from app.core.exceptions import NotFoundError
from app.modules.market_data.schemas import (
    DailyBarOut,
    DragonTigerOut,
    LimitUpOut,
    MarketOverviewOut,
    NewsOut,
    StockAnalysisSummaryOut,
    StockKlineOut,
    StockOut,
    StockQuoteOut,
    StockScreenParams,
    StockScreenResultOut,
    SyncResult,
)
from app.modules.market_data.service import MarketDataService

router = APIRouter(tags=["market"])

svc = MarketDataService()


KlinePeriod = Literal["daily", "weekly", "monthly"]


@router.get("/stocks", response_model=list[StockOut])
async def list_stocks() -> list[StockOut]:
    stocks = await svc.get_stocks()
    return [StockOut.model_validate(stock) for stock in stocks]


@router.get("/stocks/kline", response_model=list[StockKlineOut])
async def get_stock_kline(
    symbol: str = Query(..., description="股票代码"),
    period: KlinePeriod = Query(
        "daily", description="K线周期: daily / weekly / monthly (服务端按日线重采样)"
    ),
    start: date | None = Query(None, description="开始日期"),
    end: date | None = Query(None, description="结束日期"),
    limit: int = Query(120, ge=1, le=1000, description="最大返回条数"),
) -> list[StockKlineOut]:
    bars = await svc.get_stock_kline(symbol, start, end, limit, period=period)
    if not bars:
        raise NotFoundError(f"No kline data found for {symbol}")
    return [
        StockKlineOut(
            timestamp=datetime.combine(bar.trade_date, datetime.min.time()),
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=int(bar.volume),
        )
        for bar in bars
    ]


@router.get("/stocks/{code}", response_model=StockOut)
async def get_stock(code: str) -> StockOut:
    stock = await svc.get_stock(code)
    if not stock:
        raise NotFoundError(f"No stock found for {code}")
    return StockOut.model_validate(stock)


@router.get("/stocks/{code}/analysis", response_model=StockAnalysisSummaryOut)
async def get_stock_analysis(code: str) -> StockAnalysisSummaryOut:
    summary = await svc.get_stock_analysis_summary(code)
    if not summary:
        raise NotFoundError(f"No analysis summary available for {code}")
    return summary


@router.get("/stocks/{code}/quote", response_model=StockQuoteOut)
async def get_stock_quote(code: str) -> StockQuoteOut:
    result = await svc.get_stock_quote(code)
    if not result:
        raise NotFoundError(f"No quote data found for {code}")
    quote, is_delayed = result
    return StockQuoteOut(
        symbol=quote.code,
        name=quote.name,
        price=quote.price,
        change=quote.change,
        change_percent=quote.change_pct,
        volume=quote.volume,
        turnover=quote.amount,
        high=quote.high,
        low=quote.low,
        open=quote.open,
        prev_close=quote.prev_close,
        timestamp=svc.quote_timestamp(),
        is_delayed=is_delayed,
    )


@router.get("/market/overview", response_model=MarketOverviewOut)
async def get_market_overview() -> MarketOverviewOut:
    return await svc.get_market_overview()


@router.get("/analysis/screen", response_model=StockScreenResultOut)
async def screen_stocks(
    screen_type: str = Query(
        ...,
        description="筛选类型: strong_uptrend / volume_breakout / pullback_watch",
    ),
    limit: int = Query(10, ge=1, le=50, description="返回条数"),
    min_return_20d_pct: float | None = Query(None, description="20日最小涨幅"),
    min_return_5d_pct: float | None = Query(None, description="5日最小涨幅"),
    min_volume_ratio: float | None = Query(None, description="最小量比"),
    max_return_5d_pct: float | None = Query(None, description="5日最大涨幅，用于回撤观察"),
) -> StockScreenResultOut:
    result = await svc.screen_stocks(
        screen_type,
        StockScreenParams(
            limit=limit,
            min_return_20d_pct=min_return_20d_pct,
            min_return_5d_pct=min_return_5d_pct,
            min_volume_ratio=min_volume_ratio,
            max_return_5d_pct=max_return_5d_pct,
        ),
    )
    if not result.items:
        raise NotFoundError(f"No screening results for {screen_type}")
    return result


@router.get("/market/daily/{code}", response_model=list[DailyBarOut])
async def get_daily_bars(
    code: str,
    start_date: date | None = Query(None, description="开始日期"),
    end_date: date | None = Query(None, description="结束日期"),
) -> list[DailyBarOut]:
    bars = await svc.get_daily_bars(code, start_date, end_date)
    if not bars:
        raise NotFoundError(f"No daily bars found for {code}")
    return [DailyBarOut.model_validate(bar) for bar in bars]


@router.post("/market/sync", response_model=SyncResult)
async def sync_market_data(days: int = Query(30, description="同步天数")) -> SyncResult:
    stock_count = await svc.sync_stock_list()
    bars_count = 0
    stocks = await svc.get_stocks()
    for stock in stocks[:50]:
        count = await svc.sync_daily_bars(stock.code, days=days)
        bars_count += count
    return SyncResult(synced=bars_count, message=f"Synced {stock_count} stocks, {bars_count} bars")


@router.get("/market/dragon-tiger", response_model=list[DragonTigerOut])
async def get_dragon_tiger(
    trade_date: date = Query(..., description="交易日期"),
) -> list[DragonTigerOut]:
    items = await svc.get_dragon_tiger_list(trade_date)
    if not items:
        raise NotFoundError(f"No dragon tiger data for {trade_date}")
    return [DragonTigerOut.model_validate(item) for item in items]


@router.get("/market/limit-up", response_model=list[LimitUpOut])
async def get_limit_up(trade_date: date = Query(..., description="交易日期")) -> list[LimitUpOut]:
    items = await svc.get_limit_up_board(trade_date)
    if not items:
        raise NotFoundError(f"No limit up data for {trade_date}")
    return [LimitUpOut.model_validate(item) for item in items]


@router.get("/market/news", response_model=list[NewsOut])
async def get_news(
    trade_date: date = Query(..., description="交易日期"),
    limit: int = Query(50, description="返回条数"),
) -> list[NewsOut]:
    items = await svc.get_daily_news(trade_date, limit=limit)
    if not items:
        raise NotFoundError(f"No news data for {trade_date}")
    return [NewsOut.model_validate(item) for item in items]


@router.post("/market/sync/stock-list", response_model=SyncResult)
async def sync_stock_list_endpoint() -> SyncResult:
    count = await svc.sync_stock_list()
    return SyncResult(synced=count, message=f"股票列表同步成功，共 {count} 条")


@router.post("/market/sync/daily-bars/{code}", response_model=SyncResult)
async def sync_daily_bars_endpoint(
    code: str,
    days: int = Query(120, ge=1, le=3650, description="向前同步的自然日天数"),
) -> SyncResult:
    count = await svc.sync_daily_bars(code, days=days)
    return SyncResult(synced=count, message=f"{code} 日线同步成功，共 {count} 条")


@router.post("/market/sync/dragon-tiger", response_model=SyncResult)
async def sync_dragon_tiger(
    trade_date: date | None = Query(None, description="交易日期，默认今天"),
) -> SyncResult:
    return await svc.sync_dragon_tiger_list(trade_date)


@router.post("/market/sync/limit-up", response_model=SyncResult)
async def sync_limit_up(
    trade_date: date | None = Query(None, description="交易日期，默认今天"),
) -> SyncResult:
    return await svc.sync_limit_up_board(trade_date)


@router.post("/market/sync/news", response_model=SyncResult)
async def sync_news(
    trade_date: date | None = Query(None, description="交易日期，默认今天"),
) -> SyncResult:
    return await svc.sync_daily_news(trade_date)
