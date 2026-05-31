"""Celery task wrapper for the subscription dispatcher."""

from __future__ import annotations

import asyncio

from celery import shared_task
from loguru import logger

from app.modules.strategies.subscriptions.service import SubscriptionService


@shared_task(name="strategies.dispatch_subscriptions")
def dispatch_subscriptions() -> int:
    """Fire any strategy subscriptions whose schedule is due now."""
    name = "strategies.dispatch_subscriptions"
    logger.info(f"task {name} start")
    try:
        svc = SubscriptionService()
        ids = asyncio.run(svc.dispatch_due())
    except Exception as exc:
        logger.exception(f"task {name} failed error={exc}")
        raise
    logger.info(f"task {name} done dispatched={len(ids)}")
    return len(ids)
