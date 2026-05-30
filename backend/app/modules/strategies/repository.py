from sqlalchemy import select

from app.core.database import async_session_factory
from app.modules.strategies.models import StrategyKpiSnapshot


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
