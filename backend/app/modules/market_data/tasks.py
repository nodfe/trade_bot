import asyncio

from celery import shared_task
from loguru import logger

from app.modules.market_data.service import MarketDataService


@shared_task
def sync_daily_bars_task():
    """Celery task: sync daily bars for all tracked stocks"""
    svc = MarketDataService()
    loop = asyncio.get_event_loop()
    stocks = loop.run_until_complete(svc.get_stocks())
    total = 0
    for stock in stocks:
        try:
            count = loop.run_until_complete(svc.sync_daily_bars(stock.code, days=30))
            total += count
        except Exception as e:
            logger.error(f"Failed to sync {stock.code}: {e}")
    logger.info(f"Daily sync completed: {total} bars for {len(stocks)} stocks")
    return total


@shared_task
def sync_stock_list_task():
    """Celery task: sync stock list"""
    svc = MarketDataService()
    loop = asyncio.get_event_loop()
    count = loop.run_until_complete(svc.sync_stock_list())
    logger.info(f"Stock list sync completed: {count} stocks")
    return count


@shared_task
def sync_dragon_tiger_task():
    """Celery task: sync dragon tiger list"""
    svc = MarketDataService()
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(svc.sync_dragon_tiger_list())
    logger.info(f"Dragon tiger sync result: {result}")
    return result.synced


@shared_task
def sync_limit_up_task():
    """Celery task: sync limit up board"""
    svc = MarketDataService()
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(svc.sync_limit_up_board())
    logger.info(f"Limit up sync result: {result}")
    return result.synced


@shared_task
def sync_news_task():
    """Celery task: sync daily news"""
    svc = MarketDataService()
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(svc.sync_daily_news())
    logger.info(f"News sync result: {result}")
    return result.synced
