from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import dataclass

from loguru import logger

from app.modules.sync_runs.repository import SyncRunRepository


@dataclass
class RunHandle:
    """Handle yielded by ``SyncRunService.track``.

    Set ``handle.synced_count`` inside the ``async with`` block so the service
    can persist it on success.
    """

    run_id: int
    synced_count: int | None = None


class SyncRunService:
    """Track lifecycle of sync jobs.

    Usage::

        svc = SyncRunService()
        async with svc.track("daily_bars", target="600519") as handle:
            count = await do_sync()
            handle.synced_count = count
    """

    def __init__(self, repo: SyncRunRepository | None = None) -> None:
        self.repo = repo or SyncRunRepository()

    @asynccontextmanager
    async def track(
        self,
        job_name: str,
        *,
        target: str | None = None,
        meta: dict | None = None,
    ):
        run = await self.repo.create(job_name, target=target, meta=meta)
        handle = RunHandle(run_id=run.id)
        started = time.monotonic()
        try:
            yield handle
        except Exception as exc:
            await self.repo.mark_failed(run.id, error=str(exc)[:1000])
            logger.exception(f"sync_run {job_name} failed target={target}")
            raise
        else:
            duration_ms = int((time.monotonic() - started) * 1000)
            await self.repo.mark_success(
                run.id,
                synced_count=handle.synced_count,
                duration_ms=duration_ms,
            )
            logger.info(
                f"sync_run {job_name} ok target={target} "
                f"synced={handle.synced_count} dur_ms={duration_ms}"
            )

    async def mark_skipped(self, job_name: str, *, target: str | None = None, reason: str) -> None:
        """Record a skipped run inline (not wrapping a block).

        Useful when a precondition fails before the sync block runs (e.g.
        non-trading day). Creates and immediately marks the run as skipped.
        """
        run = await self.repo.create(job_name, target=target)
        await self.repo.mark_skipped(run.id, reason=reason)
        logger.info(f"sync_run {job_name} skipped target={target} reason={reason}")
