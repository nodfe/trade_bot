from datetime import date

from fastapi import APIRouter, Query

from app.modules.backtests.schemas import (
    BacktestRequest,
    BacktestResult,
    EligibleCodeOut,
    ScreenerBacktestRequest,
    ScreenerBacktestResult,
)
from app.modules.backtests.service import BacktestService
from app.modules.market_data.repository import MarketDataRepository
from app.modules.market_data.schemas import StockScreenItemOut, StockScreenParams
from app.modules.market_data.service import MarketDataService

router = APIRouter(prefix="/backtests", tags=["backtests"])

svc = BacktestService()
_repo = MarketDataRepository()
_market = MarketDataService()


@router.post("/simple", response_model=BacktestResult)
async def run_simple_backtest(req: BacktestRequest) -> BacktestResult:
    return await svc.run_simple_backtest(req)


@router.get("/eligible-codes", response_model=list[EligibleCodeOut])
async def list_eligible_codes() -> list[EligibleCodeOut]:
    """Stocks with locally synced daily bars, suitable for backtesting."""
    rows = await _repo.get_eligible_backtest_codes()
    return [
        EligibleCodeOut(code=code, name=name, bar_count=bar_count) for code, name, bar_count in rows
    ]


@router.post("/screener", response_model=ScreenerBacktestResult)
async def run_screener_backtest(
    req: ScreenerBacktestRequest,
) -> ScreenerBacktestResult:
    return await svc.run_screener_backtest(req)


@router.get("/screener/preview", response_model=list[StockScreenItemOut])
async def preview_screener(
    screen_type: str = Query(..., description="strong_uptrend / volume_breakout / pullback_watch"),
    as_of_date: date | None = Query(None, description="Historical screener anchor date"),
    top_n: int = Query(20, ge=1, le=50),
) -> list[StockScreenItemOut]:
    """Return the picks a screener would produce on a given historical date.

    Used by the admin UI to let users sanity-check the strategy/date combo
    before kicking off a full walk-forward backtest.
    """
    params = StockScreenParams(limit=top_n)
    result = await _market.screen_stocks(screen_type, params, as_of_date=as_of_date)
    return result.items
