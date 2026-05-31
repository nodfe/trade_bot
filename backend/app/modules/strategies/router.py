from fastapi import APIRouter, HTTPException, Query

from app.modules.backtests.schemas import ScreenerBacktestResult
from app.modules.strategies.schemas import (
    StrategiesListOut,
    StrategyAttributionOut,
    StrategyOut,
    StrategyRunBacktestRequest,
    UserStrategyCreate,
    UserStrategyOut,
    UserStrategyUpdate,
)
from app.modules.strategies.service import StrategiesService

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=StrategiesListOut)
async def list_strategies() -> StrategiesListOut:
    return await StrategiesService().list_strategies()


# ---------------------------------------------------------------------------
# User-customized strategies CRUD. Mounted BEFORE the parameterised
# ``/{key}`` routes so the static path takes precedence.
# ---------------------------------------------------------------------------


@router.get("/custom", response_model=list[UserStrategyOut])
async def list_user_strategies() -> list[UserStrategyOut]:
    return await StrategiesService().list_user_strategies()


@router.post("/custom", response_model=UserStrategyOut, status_code=201)
async def create_user_strategy(
    payload: UserStrategyCreate,
) -> UserStrategyOut:
    try:
        return await StrategiesService().create_user_strategy(
            name=payload.name,
            base_template=payload.base_template,
            params=payload.params,
            owner=payload.owner,
            description=payload.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/custom/{sid}", response_model=UserStrategyOut)
async def get_user_strategy(sid: str) -> UserStrategyOut:
    out = await StrategiesService().get_user_strategy(sid)
    if out is None:
        raise HTTPException(status_code=404, detail="user strategy not found")
    return out


@router.put("/custom/{sid}", response_model=UserStrategyOut)
async def update_user_strategy(sid: str, payload: UserStrategyUpdate) -> UserStrategyOut:
    out = await StrategiesService().update_user_strategy(
        sid,
        name=payload.name,
        params=payload.params,
        description=payload.description,
    )
    if out is None:
        raise HTTPException(status_code=404, detail="user strategy not found")
    return out


@router.delete("/custom/{sid}", status_code=204)
async def delete_user_strategy(sid: str) -> None:
    ok = await StrategiesService().delete_user_strategy(sid)
    if not ok:
        raise HTTPException(status_code=404, detail="user strategy not found")


# ---------------------------------------------------------------------------
# Per-strategy detail / run-backtest / attribution.
# ---------------------------------------------------------------------------


@router.get("/{key:path}/attribution", response_model=StrategyAttributionOut)
async def get_strategy_attribution(
    key: str,
    lookback_days: int = Query(180, ge=30, le=720),
) -> StrategyAttributionOut:
    out = await StrategiesService().get_attribution(key, lookback_days=lookback_days)
    if out is None:
        raise HTTPException(status_code=404, detail="strategy not found")
    return out


@router.post("/{key:path}/run-backtest", response_model=ScreenerBacktestResult)
async def run_strategy_backtest(
    key: str, payload: StrategyRunBacktestRequest
) -> ScreenerBacktestResult:
    try:
        return await StrategiesService().run_backtest_override(
            key,
            params=payload.params,
            top_n=payload.top_n,
            rebalance=payload.rebalance,
            weighting=payload.weighting,
            fee_bps=payload.fee_bps,
            stop_loss_pct=payload.stop_loss_pct,
            stop_profit_pct=payload.stop_profit_pct,
            start_date=payload.start_date,
            end_date=payload.end_date,
            benchmark=payload.benchmark,
            initial_capital=payload.initial_capital,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{key:path}", response_model=StrategyOut)
async def get_strategy_detail(key: str) -> StrategyOut:
    out = await StrategiesService().get_strategy_detail(key)
    if out is None:
        raise HTTPException(status_code=404, detail="strategy not found")
    return out
