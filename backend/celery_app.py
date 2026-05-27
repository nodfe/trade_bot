from app.config import settings
from celery import Celery

celery_app = Celery(
    "trade_bot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    beat_schedule={
        "sync-daily-bars": {
            "task": "app.modules.market_data.tasks.sync_daily_bars_task",
            "schedule": {"hour": 18, "minute": 0},  # 每日 18:00 (UTC+8)
        },
        "sync-dragon-tiger": {
            "task": "app.modules.market_data.tasks.sync_dragon_tiger_task",
            "schedule": {"hour": 18, "minute": 30},
        },
        "sync-limit-up": {
            "task": "app.modules.market_data.tasks.sync_limit_up_task",
            "schedule": {"hour": 18, "minute": 30},
        },
        "sync-news": {
            "task": "app.modules.market_data.tasks.sync_news_task",
            "schedule": {"hour": 20, "minute": 0},
        },
        # Dynamic watchlists can be refreshed by explicit task dispatch today.
        # Scheduled fan-out can be added once watchlist definitions stabilize.
    },
)
