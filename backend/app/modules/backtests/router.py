from fastapi import APIRouter

from app.modules.backtests.schemas import BacktestRequest, BacktestResult
from app.modules.backtests.service import BacktestService

router = APIRouter(prefix="/backtests", tags=["backtests"])

svc = BacktestService()


@router.post("/simple", response_model=BacktestResult)
async def run_simple_backtest(req: BacktestRequest) -> BacktestResult:
    return await svc.run_simple_backtest(req)
