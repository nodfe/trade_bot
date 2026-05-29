import json
from datetime import datetime

from sqlalchemy import select

from app.core.database import async_session_factory
from app.modules.sync_runs.models import SyncRun


class SyncRunRepository:
    async def create(
        self,
        job_name: str,
        target: str | None = None,
        meta: dict | None = None,
    ) -> SyncRun:
        async with async_session_factory() as session:
            run = SyncRun(
                job_name=job_name,
                target=target,
                status="running",
                started_at=datetime.utcnow(),
                meta_json=json.dumps(meta) if meta is not None else None,
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run

    async def mark_success(
        self,
        run_id: int,
        *,
        synced_count: int | None = None,
        duration_ms: int | None = None,
    ) -> None:
        async with async_session_factory() as session:
            run = await session.get(SyncRun, run_id)
            if run is None:
                return
            now = datetime.utcnow()
            run.status = "success"
            run.finished_at = now
            run.synced_count = synced_count
            if duration_ms is not None:
                run.duration_ms = duration_ms
            else:
                run.duration_ms = int((now - run.started_at).total_seconds() * 1000)
            await session.commit()

    async def mark_failed(self, run_id: int, *, error: str) -> None:
        async with async_session_factory() as session:
            run = await session.get(SyncRun, run_id)
            if run is None:
                return
            now = datetime.utcnow()
            run.status = "failed"
            run.finished_at = now
            run.error = error[:1000]
            run.duration_ms = int((now - run.started_at).total_seconds() * 1000)
            await session.commit()

    async def mark_skipped(self, run_id: int, *, reason: str) -> None:
        async with async_session_factory() as session:
            run = await session.get(SyncRun, run_id)
            if run is None:
                return
            now = datetime.utcnow()
            run.status = "skipped"
            run.finished_at = now
            run.error = reason[:1000]
            run.duration_ms = int((now - run.started_at).total_seconds() * 1000)
            await session.commit()

    async def list_recent(
        self,
        limit: int = 50,
        job_name: str | None = None,
    ) -> list[SyncRun]:
        async with async_session_factory() as session:
            stmt = select(SyncRun).order_by(SyncRun.started_at.desc()).limit(limit)
            if job_name:
                stmt = stmt.where(SyncRun.job_name == job_name)
            result = await session.execute(stmt)
            return list(result.scalars().all())
