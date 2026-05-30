from __future__ import annotations

import asyncio

from celery import shared_task
from loguru import logger

from app.modules.strategies.service import StrategiesService


@shared_task(name="strategies.compute_kpi_snapshots")
def compute_kpi_snapshots() -> int:
    """Recompute all strategy KPI snapshots over the trailing 180-day window."""
    name = "strategies.compute_kpi_snapshots"
    logger.info(f"task {name} start")
    try:
        svc = StrategiesService()
        count = asyncio.run(svc.compute_all_snapshots())
    except Exception as exc:
        logger.exception(f"task {name} failed error={exc}")
        raise
    logger.info(f"task {name} done synced={count}")
    return count
