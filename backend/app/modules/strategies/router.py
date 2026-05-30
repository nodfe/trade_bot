from fastapi import APIRouter

from app.modules.strategies.schemas import StrategiesListOut
from app.modules.strategies.service import StrategiesService

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=StrategiesListOut)
async def list_strategies() -> StrategiesListOut:
    return await StrategiesService().list_strategies()
