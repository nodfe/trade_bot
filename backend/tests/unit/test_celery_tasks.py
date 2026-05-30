"""Unit tests for Celery beat schedule + market_data task wrappers.

These tests do NOT spin up a Celery worker or Redis. They:

* Patch the async ``MarketDataService.sync_*`` methods with fakes that return
  known values, then invoke each ``@shared_task`` function directly (Celery
  tasks are still callable as regular Python functions in the local process).
* Assert ``celery_app.beat_schedule`` is wired with the expected names + tasks.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.market_data import tasks as market_tasks
from app.modules.market_data.schemas import SyncResult
from app.modules.market_data.service import MarketDataService
from celery_app import app, celery_app

# ---------------------------------------------------------------------------
# Task wrapper tests
# ---------------------------------------------------------------------------


def test_sync_stock_list_task_returns_service_count(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_sync_stock_list(self: MarketDataService) -> int:
        return 4321

    monkeypatch.setattr(MarketDataService, "sync_stock_list", fake_sync_stock_list)

    result = market_tasks.sync_stock_list.run()

    assert result == 4321


def test_sync_dragon_tiger_task_propagates_synced_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, date | None] = {}

    async def fake_sync_dragon_tiger_list(
        self: MarketDataService, trade_date: date | None = None
    ) -> SyncResult:
        captured["trade_date"] = trade_date
        return SyncResult(synced=12, message="ok")

    monkeypatch.setattr(
        MarketDataService, "sync_dragon_tiger_list", fake_sync_dragon_tiger_list
    )

    result = market_tasks.sync_dragon_tiger_list.run("2026-05-29")

    assert result == 12
    assert captured["trade_date"] == date(2026, 5, 29)


def test_sync_dragon_tiger_task_passes_none_when_no_arg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, date | None] = {"trade_date": date(1970, 1, 1)}

    async def fake_sync_dragon_tiger_list(
        self: MarketDataService, trade_date: date | None = None
    ) -> SyncResult:
        captured["trade_date"] = trade_date
        return SyncResult(synced=0, message="empty")

    monkeypatch.setattr(
        MarketDataService, "sync_dragon_tiger_list", fake_sync_dragon_tiger_list
    )

    result = market_tasks.sync_dragon_tiger_list.run()

    assert result == 0
    assert captured["trade_date"] is None


def test_sync_limit_up_task_propagates_synced_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_sync_limit_up(
        self: MarketDataService, trade_date: date | None = None
    ) -> SyncResult:
        return SyncResult(synced=7, message="ok")

    monkeypatch.setattr(MarketDataService, "sync_limit_up_board", fake_sync_limit_up)

    assert market_tasks.sync_limit_up_board.run() == 7


def test_sync_daily_news_task_propagates_synced_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_sync_news(
        self: MarketDataService, trade_date: date | None = None
    ) -> SyncResult:
        return SyncResult(synced=99, message="ok")

    monkeypatch.setattr(MarketDataService, "sync_daily_news", fake_sync_news)

    assert market_tasks.sync_daily_news.run("2026-05-29") == 99


def test_sync_daily_bars_batch_sums_per_symbol_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeStock:
        def __init__(self, code: str) -> None:
            self.code = code

    fake_stocks = [_FakeStock(f"00000{i}") for i in range(5)]

    async def fake_get_stocks(self: MarketDataService) -> list[_FakeStock]:
        return fake_stocks

    calls: list[tuple[str, int]] = []

    async def fake_sync_daily_bars(
        self: MarketDataService, code: str, days: int = 30
    ) -> int:
        calls.append((code, days))
        return 3  # each symbol "syncs" 3 bars

    monkeypatch.setattr(MarketDataService, "get_stocks", fake_get_stocks)
    monkeypatch.setattr(MarketDataService, "sync_daily_bars", fake_sync_daily_bars)

    total = market_tasks.sync_daily_bars_batch.run(top_n=3, days=7)

    assert total == 9  # 3 symbols x 3 bars
    assert [c[0] for c in calls] == ["000000", "000001", "000002"]
    assert all(c[1] == 7 for c in calls)


def test_sync_daily_bars_batch_keeps_going_after_per_symbol_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeStock:
        def __init__(self, code: str) -> None:
            self.code = code

    fake_stocks = [_FakeStock("000001"), _FakeStock("000002")]

    async def fake_get_stocks(self: MarketDataService) -> list[_FakeStock]:
        return fake_stocks

    async def fake_sync_daily_bars(
        self: MarketDataService, code: str, days: int = 30
    ) -> int:
        if code == "000001":
            raise RuntimeError("provider blew up")
        return 5

    monkeypatch.setattr(MarketDataService, "get_stocks", fake_get_stocks)
    monkeypatch.setattr(MarketDataService, "sync_daily_bars", fake_sync_daily_bars)

    total = market_tasks.sync_daily_bars_batch.run(top_n=2, days=3)

    assert total == 5  # only 000002 succeeded


def test_sync_stock_list_task_reraises_on_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_sync_stock_list(self: MarketDataService) -> int:
        raise RuntimeError("provider down")

    monkeypatch.setattr(MarketDataService, "sync_stock_list", fake_sync_stock_list)

    with pytest.raises(RuntimeError, match="provider down"):
        market_tasks.sync_stock_list.run()


# ---------------------------------------------------------------------------
# Beat schedule wiring tests
# ---------------------------------------------------------------------------


EXPECTED_SCHEDULE = {
    "sync-stock-list-daily": "market_data.sync_stock_list",
    "sync-limit-up-daily": "market_data.sync_limit_up_board",
    "sync-daily-bars-batch": "market_data.sync_daily_bars_batch",
    "sync-dragon-tiger-daily": "market_data.sync_dragon_tiger_list",
    "sync-news-daily": "market_data.sync_daily_news",
    "compute-strategy-kpi-snapshots-daily": "strategies.compute_kpi_snapshots",
}


def test_beat_schedule_has_five_expected_entries() -> None:
    schedule = celery_app.conf.beat_schedule

    assert set(schedule.keys()) == set(EXPECTED_SCHEDULE.keys())
    for beat_key, task_name in EXPECTED_SCHEDULE.items():
        entry = schedule[beat_key]
        assert entry["task"] == task_name, (
            f"beat entry {beat_key!r} should dispatch {task_name!r}, "
            f"got {entry['task']!r}"
        )
        assert "schedule" in entry


def test_celery_app_alias_is_exposed() -> None:
    # ``celery_app:app`` is the canonical handle for ``celery -A`` and tests.
    assert app is celery_app


def test_celery_timezone_is_utc() -> None:
    assert celery_app.conf.timezone == "UTC"
    assert celery_app.conf.enable_utc is True
