from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pytest

from app.modules.market_data.providers.base import DragonTigerItem
from app.modules.market_data.service import MarketDataService


@dataclass
class _RecordedTrack:
    job_name: str
    target: str | None
    meta: dict | None
    entered: bool = False
    synced_count: int | None = None


class _RecordingSyncRuns:
    """Stand-in for SyncRunService that records track/skip calls."""

    def __init__(self) -> None:
        self.tracks: list[_RecordedTrack] = []
        self.skipped: list[dict[str, Any]] = []

    @asynccontextmanager
    async def track(
        self,
        job_name: str,
        *,
        target: str | None = None,
        meta: dict | None = None,
    ):
        record = _RecordedTrack(job_name=job_name, target=target, meta=meta, entered=True)
        self.tracks.append(record)

        class _Handle:
            synced_count: int | None = None

        handle = _Handle()
        try:
            yield handle
        finally:
            record.synced_count = handle.synced_count

    async def mark_skipped(
        self, job_name: str, *, target: str | None = None, reason: str
    ) -> None:
        self.skipped.append({"job_name": job_name, "target": target, "reason": reason})


class _FakeRepo:
    def __init__(self, *, has_data: bool, existing: list | None = None) -> None:
        self._has_data = has_data
        self._existing = existing or []
        self.saved: list[Any] = []

    async def has_dragon_tiger_data(self, trade_date: date) -> bool:
        return self._has_data

    async def get_dragon_tiger_list(self, trade_date: date) -> list:
        return list(self._existing)

    async def save_dragon_tiger_list(self, items: list) -> int:
        self.saved.extend(items)
        return len(items)


@dataclass
class _FakeFacade:
    items: list[DragonTigerItem] = field(default_factory=list)

    async def get_dragon_tiger_list(self, trade_date: date) -> list[DragonTigerItem]:
        return list(self.items)


def _make_service(
    repo: _FakeRepo, facade: _FakeFacade
) -> tuple[MarketDataService, _RecordingSyncRuns]:
    svc = MarketDataService.__new__(MarketDataService)
    svc.repo = repo  # type: ignore[assignment]
    svc.facade = facade  # type: ignore[assignment]
    sync_runs = _RecordingSyncRuns()
    svc.sync_runs = sync_runs  # type: ignore[assignment]
    return svc, sync_runs


@pytest.mark.asyncio
async def test_sync_dragon_tiger_list_happy_path_uses_track() -> None:
    facade_items = [
        DragonTigerItem(
            trade_date=date(2026, 5, 27),
            code="600519",
            name="贵州茅台",
            close_price=1688.0,
            change_pct=0.75,
            reason="日涨幅偏离值7%",
            buy_amount=1.0e8,
            sell_amount=2.0e7,
            net_buy=8.0e7,
        )
    ]
    repo = _FakeRepo(has_data=False)
    facade = _FakeFacade(items=facade_items)
    svc, sync_runs = _make_service(repo, facade)

    result = await svc.sync_dragon_tiger_list(date(2026, 5, 27))

    assert result.synced == 1
    assert sync_runs.skipped == []
    assert len(sync_runs.tracks) == 1
    track = sync_runs.tracks[0]
    assert track.job_name == "dragon_tiger"
    assert track.target == "2026-05-27"
    assert track.entered is True
    assert track.synced_count == 1
    assert len(repo.saved) == 1


@pytest.mark.asyncio
async def test_sync_dragon_tiger_list_skip_path_calls_mark_skipped() -> None:
    repo = _FakeRepo(has_data=True, existing=[object()])
    facade = _FakeFacade()
    svc, sync_runs = _make_service(repo, facade)

    result = await svc.sync_dragon_tiger_list(date(2026, 5, 27))

    assert result.synced == 0
    assert sync_runs.tracks == []
    assert len(sync_runs.skipped) == 1
    skip = sync_runs.skipped[0]
    assert skip["job_name"] == "dragon_tiger"
    assert skip["target"] == "2026-05-27"
    assert skip["reason"] == "data already present"
    # Facade must not be consulted on skip.
    assert repo.saved == []


@pytest.mark.asyncio
async def test_sync_dragon_tiger_list_empty_facade_still_tracked() -> None:
    repo = _FakeRepo(has_data=False)
    facade = _FakeFacade(items=[])
    svc, sync_runs = _make_service(repo, facade)

    result = await svc.sync_dragon_tiger_list(date(2026, 5, 27))

    assert result.synced == 0
    assert sync_runs.skipped == []
    assert len(sync_runs.tracks) == 1
    track = sync_runs.tracks[0]
    assert track.entered is True
    assert track.synced_count == 0
