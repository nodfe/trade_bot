import asyncio

from celery import shared_task
from loguru import logger

from app.modules.watchlist.service import WatchlistService


@shared_task
def refresh_watchlist_task(watchlist_id: str):
    svc = WatchlistService()
    loop = asyncio.get_event_loop()
    refreshed = loop.run_until_complete(svc.refresh_watchlist(watchlist_id))
    if not refreshed:
        logger.warning(f"Watchlist {watchlist_id} not found during refresh")
        return 0

    logger.info(f"Refreshed watchlist {watchlist_id} with {len(refreshed.items)} items")
    return len(refreshed.items)


@shared_task
def refresh_auto_watchlists_task():
    svc = WatchlistService()
    loop = asyncio.get_event_loop()
    refreshed = loop.run_until_complete(svc.refresh_auto_watchlists())
    logger.info(f"Refreshed {len(refreshed)} auto watchlists")
    return len(refreshed)
