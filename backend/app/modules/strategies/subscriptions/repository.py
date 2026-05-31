from __future__ import annotations

from sqlalchemy import select

from app.core.database import async_session_factory
from app.modules.strategies.subscriptions.models import StrategySubscription


class SubscriptionRepository:
    async def list_all(
        self,
        *,
        enabled: bool | None = None,
        user_id: str | None = None,
    ) -> list[StrategySubscription]:
        async with async_session_factory() as session:
            stmt = select(StrategySubscription)
            if enabled is not None:
                stmt = stmt.where(StrategySubscription.enabled == enabled)
            if user_id is not None:
                stmt = stmt.where(StrategySubscription.user_id == user_id)
            stmt = stmt.order_by(StrategySubscription.created_at.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get(self, sub_id: str) -> StrategySubscription | None:
        async with async_session_factory() as session:
            return await session.get(StrategySubscription, sub_id)

    async def create(self, sub: StrategySubscription) -> StrategySubscription:
        async with async_session_factory() as session:
            session.add(sub)
            await session.commit()
            await session.refresh(sub)
            return sub

    async def delete(self, sub_id: str) -> bool:
        async with async_session_factory() as session:
            obj = await session.get(StrategySubscription, sub_id)
            if obj is None:
                return False
            await session.delete(obj)
            await session.commit()
            return True

    async def update_dispatched_at(self, sub_id: str, when) -> None:
        async with async_session_factory() as session:
            obj = await session.get(StrategySubscription, sub_id)
            if obj is None:
                return
            obj.last_dispatched_at = when
            await session.commit()
