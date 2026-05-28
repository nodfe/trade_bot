from datetime import datetime

from sqlalchemy import select

from app.core.database import async_session_factory
from app.modules.watchlist.models import Watchlist, WatchlistItem


class WatchlistRepository:
    async def list_watchlists(self) -> list[Watchlist]:
        async with async_session_factory() as session:
            result = await session.execute(select(Watchlist).order_by(Watchlist.created_at.desc()))
            return list(result.scalars().all())

    async def list_auto_refresh_watchlists(self) -> list[Watchlist]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Watchlist)
                .where(Watchlist.auto_refresh != "manual")
                .order_by(Watchlist.created_at.desc())
            )
            return list(result.scalars().all())

    async def get_watchlist(self, watchlist_id: str) -> Watchlist | None:
        async with async_session_factory() as session:
            result = await session.execute(select(Watchlist).where(Watchlist.id == watchlist_id))
            return result.scalar_one_or_none()

    async def get_watchlist_items(self, watchlist_id: str) -> list[WatchlistItem]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(WatchlistItem)
                .where(WatchlistItem.watchlist_id == watchlist_id)
                .order_by(WatchlistItem.created_at.desc())
            )
            return list(result.scalars().all())

    async def create_watchlist(self, watchlist: Watchlist, items: list[WatchlistItem]) -> Watchlist:
        async with async_session_factory() as session:
            session.add(watchlist)
            for item in items:
                session.add(item)
            await session.commit()
            await session.refresh(watchlist)
            return watchlist

    async def replace_watchlist_items(self, watchlist_id: str, items: list[WatchlistItem]) -> None:
        async with async_session_factory() as session:
            existing = await session.execute(
                select(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist_id)
            )
            for item in existing.scalars().all():
                await session.delete(item)
            for item in items:
                session.add(item)

            watchlist = await session.get(Watchlist, watchlist_id)
            if watchlist:
                now = datetime.now()
                watchlist.updated_at = now
                watchlist.last_refreshed_at = now

            await session.commit()
