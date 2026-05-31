from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "trade_bot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.modules.market_data.tasks",
        "app.modules.watchlist.tasks",
        "app.modules.strategies.tasks",
        "app.modules.strategies.subscriptions.tasks",
    ],
)

# Autodiscover tasks across feature modules. The explicit ``include`` list above
# already covers ``market_data`` and ``watchlist``; ``autodiscover_tasks`` keeps
# the pipeline open for future modules without re-editing this file.
celery_app.autodiscover_tasks(
    [
        "app.modules.market_data",
        "app.modules.watchlist",
        "app.modules.strategies",
    ]
)

# Expose ``app`` as the canonical handle expected by Celery beat / worker CLI
# (``celery -A celery_app:app``) and by tests/sanity scripts.
app = celery_app

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Beat schedule entries below are expressed in UTC. A-share regular session
    # closes at 15:00 CST (07:00 UTC); we add buffers per source freshness.
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    # Stock universe refresh — weekday 16:00 CST (08:00 UTC).
    "sync-stock-list-daily": {
        "task": "market_data.sync_stock_list",
        "schedule": crontab(hour=8, minute=0, day_of_week="1-5"),
    },
    # Limit-up board — weekday 16:10 CST (08:10 UTC); EOD aggregator publishes
    # shortly after close.
    "sync-limit-up-daily": {
        "task": "market_data.sync_limit_up_board",
        "schedule": crontab(hour=8, minute=10, day_of_week="1-5"),
    },
    # Daily bars batch fan-out — weekday 16:30 CST (08:30 UTC) for top N codes.
    "sync-daily-bars-batch": {
        "task": "market_data.sync_daily_bars_batch",
        "schedule": crontab(hour=8, minute=30, day_of_week="1-5"),
    },
    # Dragon-tiger list — weekday 18:30 CST (10:30 UTC); the exchange publishes
    # the EOD list a few hours after close.
    "sync-dragon-tiger-daily": {
        "task": "market_data.sync_dragon_tiger_list",
        "schedule": crontab(hour=10, minute=30, day_of_week="1-5"),
    },
    # News digest — every day 20:00 CST (12:00 UTC), including weekends.
    # Celery's ``day_of_week`` is 0-6 (Sun=0); ``"*"`` covers all 7 days.
    "sync-news-daily": {
        "task": "market_data.sync_daily_news",
        "schedule": crontab(hour=12, minute=0, day_of_week="*"),
    },
    # Strategy KPI snapshots — every day 17:00 CST (09:00 UTC), after the
    # daily-bars batch has settled, so the screener walk-forward backtest
    # has fresh inputs.
    "compute-strategy-kpi-snapshots-daily": {
        "task": "strategies.compute_kpi_snapshots",
        "schedule": crontab(hour=9, minute=0, day_of_week="*"),
    },
    # Strategy subscription dispatcher — every 5 minutes; the per-subscription
    # cron filtering happens inside the task body.
    "dispatch-strategy-subscriptions": {
        "task": "strategies.dispatch_subscriptions",
        "schedule": crontab(minute="*/5"),
    },
}
