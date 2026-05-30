from fastapi import APIRouter

from app.modules.backtests.schemas import BacktestRequest, BacktestResult, EligibleCodeOut
from app.modules.backtests.service import BacktestService
from app.modules.market_data.repository import MarketDataRepository

router = APIRouter(prefix="/backtests", tags=["backtests"])

svc = BacktestService()
_repo = MarketDataRepository()


@router.post("/simple", response_model=BacktestResult)
async def run_simple_backtest(req: BacktestRequest) -> BacktestResult:
    return await svc.run_simple_backtest(req)


@router.get("/eligible-codes", response_model=list[EligibleCodeOut])
async def list_eligible_codes() -> list[EligibleCodeOut]:
    """Stocks with locally synced daily bars, suitable for backtesting."""
    rows = await _repo.get_eligible_backtest_codes()
    return [
        EligibleCodeOut(code=code, name=name, bar_count=bar_count)
        for code, name, bar_count in rows
    ]
