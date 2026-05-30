from fastapi import APIRouter, Query

from app.modules.bot.command_logs import BotCommandLogRepository
from app.modules.sync_runs.repository import SyncRunRepository
from app.modules.sync_runs.schemas import BotCommandLogOut, SyncRunOut, SystemInfoOut
from app.modules.sync_runs.system_info import get_system_info

router = APIRouter(prefix="/system", tags=["system"])

sync_repo = SyncRunRepository()
bot_log_repo = BotCommandLogRepository()


@router.get("/sync-runs", response_model=list[SyncRunOut])
async def list_sync_runs(
    limit: int = Query(50, ge=1, le=500, description="返回条数"),
    job_name: str | None = Query(None, description="按 job_name 过滤"),
) -> list[SyncRunOut]:
    runs = await sync_repo.list_recent(limit=limit, job_name=job_name)
    return [SyncRunOut.model_validate(run) for run in runs]


@router.get("/bot-command-logs", response_model=list[BotCommandLogOut])
async def list_bot_command_logs(
    limit: int = Query(50, ge=1, le=500, description="返回条数"),
) -> list[BotCommandLogOut]:
    logs = await bot_log_repo.list_recent(limit=limit)
    return [BotCommandLogOut.model_validate(log) for log in logs]


@router.get("/info", response_model=SystemInfoOut)
async def get_system_info_endpoint() -> SystemInfoOut:
    """Aggregated system status for the admin Settings page."""
    return await get_system_info()
