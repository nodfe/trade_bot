from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.modules.sync_runs.service import RunHandle, SyncRunService


@dataclass
class _FakeRun:
    id: int
    job_name: str
    target: str | None = None
    meta: dict | None = None


@dataclass
class _FakeRepo:
    """In-memory fake of SyncRunRepository for unit tests."""

    next_id: int = 1
    runs: dict[int, _FakeRun] = field(default_factory=dict)
    success_calls: list[dict[str, Any]] = field(default_factory=list)
    failed_calls: list[dict[str, Any]] = field(default_factory=list)
    skipped_calls: list[dict[str, Any]] = field(default_factory=list)

    async def create(
        self,
        job_name: str,
        target: str | None = None,
        meta: dict | None = None,
    ) -> _FakeRun:
        run = _FakeRun(id=self.next_id, job_name=job_name, target=target, meta=meta)
        self.runs[run.id] = run
        self.next_id += 1
        return run

    async def mark_success(
        self,
        run_id: int,
        *,
        synced_count: int | None = None,
        duration_ms: int | None = None,
    ) -> None:
        self.success_calls.append(
            {"run_id": run_id, "synced_count": synced_count, "duration_ms": duration_ms}
        )

    async def mark_failed(self, run_id: int, *, error: str) -> None:
        self.failed_calls.append({"run_id": run_id, "error": error})

    async def mark_skipped(self, run_id: int, *, reason: str) -> None:
        self.skipped_calls.append({"run_id": run_id, "reason": reason})


@pytest.mark.asyncio
async def test_track_success_marks_success_with_synced_count() -> None:
    repo = _FakeRepo()
    svc = SyncRunService(repo=repo)  # type: ignore[arg-type]

    async with svc.track("daily_bars", target="600519", meta={"days": 30}) as handle:
        assert isinstance(handle, RunHandle)
        assert handle.run_id == 1
        handle.synced_count = 42

    assert len(repo.success_calls) == 1
    call = repo.success_calls[0]
    assert call["run_id"] == 1
    assert call["synced_count"] == 42
    assert call["duration_ms"] is not None
    assert call["duration_ms"] >= 0
    assert repo.failed_calls == []

    # Confirm meta was passed through to create.
    run = repo.runs[1]
    assert run.job_name == "daily_bars"
    assert run.target == "600519"
    assert run.meta == {"days": 30}


@pytest.mark.asyncio
async def test_track_failure_marks_failed_and_reraises() -> None:
    repo = _FakeRepo()
    svc = SyncRunService(repo=repo)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="boom"):
        async with svc.track("dragon_tiger") as handle:
            assert handle.run_id == 1
            raise RuntimeError("boom")

    assert len(repo.failed_calls) == 1
    assert repo.failed_calls[0] == {"run_id": 1, "error": "boom"}
    assert repo.success_calls == []


@pytest.mark.asyncio
async def test_track_failure_truncates_long_error_message() -> None:
    repo = _FakeRepo()
    svc = SyncRunService(repo=repo)  # type: ignore[arg-type]

    long_msg = "x" * 2000
    with pytest.raises(ValueError):
        async with svc.track("news"):
            raise ValueError(long_msg)

    assert len(repo.failed_calls) == 1
    assert len(repo.failed_calls[0]["error"]) == 1000


@pytest.mark.asyncio
async def test_mark_skipped_records_run_without_block() -> None:
    repo = _FakeRepo()
    svc = SyncRunService(repo=repo)  # type: ignore[arg-type]

    await svc.mark_skipped("limit_up", target=None, reason="non-trading day")

    assert len(repo.skipped_calls) == 1
    assert repo.skipped_calls[0] == {"run_id": 1, "reason": "non-trading day"}
