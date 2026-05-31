from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.core.database import async_session_factory
from app.modules.strategies.models import StrategyKpiSnapshot, UserStrategy


class StrategiesRepository:
    async def get_all_snapshots(self) -> dict[str, StrategyKpiSnapshot]:
        async with async_session_factory() as session:
            result = await session.execute(select(StrategyKpiSnapshot))
            rows = list(result.scalars().all())
            return {row.key: row for row in rows}

    async def upsert_snapshot(self, snapshot: StrategyKpiSnapshot) -> None:
        async with async_session_factory() as session:
            await session.merge(snapshot)
            await session.commit()

    # ------------------------------------------------------------------
    # User-customized strategies CRUD.
    # ------------------------------------------------------------------

    async def list_user_strategies(self) -> list[UserStrategy]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(UserStrategy).order_by(UserStrategy.created_at.desc())
            )
            return list(result.scalars().all())

    async def get_user_strategy(self, sid: str) -> UserStrategy | None:
        async with async_session_factory() as session:
            result = await session.execute(select(UserStrategy).where(UserStrategy.id == sid))
            return result.scalar_one_or_none()

    async def create_user_strategy(
        self,
        *,
        name: str,
        base_template: str,
        params: dict,
        owner: str = "default",
        description: str | None = None,
    ) -> UserStrategy:
        async with async_session_factory() as session:
            row = UserStrategy(
                name=name,
                base_template=base_template,
                params_json=json.dumps(params),
                owner=owner,
                description=description,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def update_user_strategy(
        self,
        sid: str,
        *,
        name: str | None = None,
        params: dict | None = None,
        description: str | None = None,
    ) -> UserStrategy | None:
        async with async_session_factory() as session:
            result = await session.execute(select(UserStrategy).where(UserStrategy.id == sid))
            row = result.scalar_one_or_none()
            if row is None:
                return None
            if name is not None:
                row.name = name
            if params is not None:
                row.params_json = json.dumps(params)
            if description is not None:
                row.description = description
            row.updated_at = datetime.now()
            await session.commit()
            await session.refresh(row)
            return row

    async def delete_user_strategy(self, sid: str) -> bool:
        async with async_session_factory() as session:
            result = await session.execute(select(UserStrategy).where(UserStrategy.id == sid))
            row = result.scalar_one_or_none()
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True
