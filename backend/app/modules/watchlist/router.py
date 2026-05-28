from fastapi import APIRouter

from app.core.exceptions import NotFoundError
from app.modules.watchlist.schemas import WatchlistCreate, WatchlistOut
from app.modules.watchlist.service import WatchlistService

router = APIRouter(prefix="/watchlists", tags=["watchlists"])

svc = WatchlistService()


@router.get("", response_model=list[WatchlistOut])
async def list_watchlists() -> list[WatchlistOut]:
    return await svc.list_watchlists()


@router.get("/{watchlist_id}", response_model=WatchlistOut)
async def get_watchlist(watchlist_id: str) -> WatchlistOut:
    watchlist = await svc.get_watchlist(watchlist_id)
    if not watchlist:
        raise NotFoundError(f"Watchlist {watchlist_id} not found")
    return watchlist


@router.post("", response_model=WatchlistOut)
async def create_watchlist(payload: WatchlistCreate) -> WatchlistOut:
    return await svc.create_watchlist(payload)


@router.post("/{watchlist_id}/refresh", response_model=WatchlistOut)
async def refresh_watchlist(watchlist_id: str) -> WatchlistOut:
    watchlist = await svc.refresh_watchlist(watchlist_id)
    if not watchlist:
        raise NotFoundError(f"Watchlist {watchlist_id} not found")
    return watchlist


@router.post("/refresh/auto", response_model=list[WatchlistOut])
async def refresh_auto_watchlists() -> list[WatchlistOut]:
    return await svc.refresh_auto_watchlists()
