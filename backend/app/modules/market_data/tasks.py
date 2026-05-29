"""Celery tasks for market data syncing.

These tasks are thin wrappers around :class:`MarketDataService` async methods.
The Celery worker is sync, so each task uses ``asyncio.run`` to drive the
coroutine. ``sync_runs`` observability lives inside the service methods
themselves (P1-A/B); these wrappers only emit structured loguru entry/exit
logs so the worker output stays useful.
"""

from __future__ import annotations

import asyncio
from datetime import date

from celery import shared_task
from loguru import logger

from app.modules.market_data.service import MarketDataService


def _parse_trade_date(trade_date_iso: str | None) -> date | None:
    """Parse an ISO date string sent by Celery beat.

    ``None`` (the beat default) means "let the service pick today".
    """
    if trade_date_iso is None:
        return None
    return date.fromisoformat(trade_date_iso)


@shared_task(name="market_data.sync_stock_list")
def sync_stock_list() -> int:
    """Sync the A-share stock universe (codes / names / industries)."""
    name = "market_data.sync_stock_list"
    logger.info(f"task {name} start")
    try:
        svc = MarketDataService()
        count = asyncio.run(svc.sync_stock_list())
    except Exception as exc:
        logger.exception(f"task {name} failed error={exc}")
        raise
    logger.info(f"task {name} done synced={count}")
    return count


@shared_task(name="market_data.sync_dragon_tiger_list")
def sync_dragon_tiger_list(trade_date_iso: str | None = None) -> int:
    """Sync the dragon-tiger list (龙虎榜) for the given trade date."""
    name = "market_data.sync_dragon_tiger_list"
    logger.info(f"task {name} start trade_date={trade_date_iso}")
    try:
        svc = MarketDataService()
        result = asyncio.run(svc.sync_dragon_tiger_list(_parse_trade_date(trade_date_iso)))
    except Exception as exc:
        logger.exception(f"task {name} failed error={exc}")
        raise
    logger.info(f"task {name} done synced={result.synced}")
    return result.synced


@shared_task(name="market_data.sync_limit_up_board")
def sync_limit_up_board(trade_date_iso: str | None = None) -> int:
    """Sync the limit-up board (涨停板) for the given trade date."""
    name = "market_data.sync_limit_up_board"
    logger.info(f"task {name} start trade_date={trade_date_iso}")
    try:
        svc = MarketDataService()
        result = asyncio.run(svc.sync_limit_up_board(_parse_trade_date(trade_date_iso)))
    except Exception as exc:
        logger.exception(f"task {name} failed error={exc}")
        raise
    logger.info(f"task {name} done synced={result.synced}")
    return result.synced


@shared_task(name="market_data.sync_daily_news")
def sync_daily_news(trade_date_iso: str | None = None) -> int:
    """Sync daily news for the given trade date."""
    name = "market_data.sync_daily_news"
    logger.info(f"task {name} start trade_date={trade_date_iso}")
    try:
        svc = MarketDataService()
        result = asyncio.run(svc.sync_daily_news(_parse_trade_date(trade_date_iso)))
    except Exception as exc:
        logger.exception(f"task {name} failed error={exc}")
        raise
    logger.info(f"task {name} done synced={result.synced}")
    return result.synced


@shared_task(name="market_data.sync_daily_bars_batch")
def sync_daily_bars_batch(top_n: int = 50, days: int = 5) -> int:
    """Sync daily bars for the first ``top_n`` stocks, ``days`` lookback.

    Mirrors the serial pattern used by ``router.sync_market_data``. Future
    improvement: fan out the per-symbol calls via ``celery.group(...)`` so the
    worker pool can pull bars in parallel instead of one symbol at a time.
    """
    name = "market_data.sync_daily_bars_batch"
    logger.info(f"task {name} start top_n={top_n} days={days}")

    async def _run() -> tuple[int, int]:
        svc = MarketDataService()
        stocks = await svc.get_stocks()
        targets = stocks[:top_n]
        total = 0
        for stock in targets:
            try:
                total += await svc.sync_daily_bars(stock.code, days=days)
            except Exception as inner:
                # Per-symbol failures should not abort the whole batch — log
                # and keep going. Celery still sees the task succeed.
                logger.error(f"task {name} symbol={stock.code} failed error={inner}")
        return total, len(targets)

    try:
        total, processed = asyncio.run(_run())
    except Exception as exc:
        logger.exception(f"task {name} failed error={exc}")
        raise

    logger.info(f"task {name} done synced={total} symbols={processed}")
    return total
