"""Backfill historical daily bars for ~600 stocks across ~400 days.

Bypasses ORM merge (which races on TimescaleDB hypertable unique index) and
uses PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` for safe concurrent upsert.

Run:
  docker exec tradebot-backend python /app/scripts/backfill_history.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import date, timedelta
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.database import async_session_factory
from app.modules.market_data.models import DailyBar, Stock
from app.modules.market_data.providers.facade import DataFacade, create_data_facade

DAYS = 400
TARGET_STOCKS = 600
CONCURRENCY = 1
RATE_LIMIT_SLEEP_SEC = 1.3  # Tushare 50 req/min ≈ 1.2s between calls
INDEX_CODES = ["000300.SH", "000905.SH"]


async def _pick_codes(limit: int) -> list[str]:
    async with async_session_factory() as session:
        rows = await session.execute(select(Stock.code).order_by(Stock.code))
        all_codes = [r[0] for r in rows.all()]
    selected = all_codes[:limit] if all_codes else []
    for ix in INDEX_CODES:
        if ix not in selected:
            selected.append(ix)
    return selected


async def _upsert_bars(rows: list[dict]) -> int:
    if not rows:
        return 0
    async with async_session_factory() as session:
        stmt = pg_insert(DailyBar).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["code", "trade_date"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "amount": stmt.excluded.amount,
                "turnover": stmt.excluded.turnover,
            },
        )
        await session.execute(stmt)
        await session.commit()
    return len(rows)


async def _sync_one(
    facade: DataFacade, code: str, sem: asyncio.Semaphore
) -> tuple[str, int, str]:
    end = date.today()
    start = end - timedelta(days=DAYS)
    async with sem:
        await asyncio.sleep(RATE_LIMIT_SLEEP_SEC)
        try:
            dtos = await facade.get_daily_bars(code, start, end)
            rows = [
                {
                    "code": b.code,
                    "trade_date": b.trade_date,
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": int(b.volume) if b.volume is not None else 0,
                    "amount": b.amount,
                    "turnover": b.turnover,
                }
                for b in dtos
            ]
            n = await _upsert_bars(rows)
            return code, n, "ok"
        except Exception as exc:  # noqa: BLE001
            return code, 0, f"err:{exc.__class__.__name__}:{str(exc)[:120]}"


async def main() -> None:
    facade = create_data_facade()
    codes = await _pick_codes(TARGET_STOCKS)
    logger.info(
        f"backfill start codes={len(codes)} days={DAYS} concurrency={CONCURRENCY}"
    )
    sem = asyncio.Semaphore(CONCURRENCY)
    started = time.monotonic()
    done = 0
    total_bars = 0
    failures: list[tuple[str, str]] = []

    tasks = [asyncio.create_task(_sync_one(facade, c, sem)) for c in codes]
    for fut in asyncio.as_completed(tasks):
        code, n, status = await fut
        done += 1
        if status == "ok":
            total_bars += n
        else:
            failures.append((code, status))
        if done % 25 == 0 or done == len(codes):
            elapsed = time.monotonic() - started
            logger.info(
                f"progress {done}/{len(codes)} bars={total_bars} "
                f"failures={len(failures)} elapsed={elapsed:.1f}s"
            )

    elapsed = time.monotonic() - started
    logger.info(
        f"backfill done codes={len(codes)} bars={total_bars} "
        f"failures={len(failures)} elapsed={elapsed:.1f}s"
    )
    if failures:
        logger.warning(f"failure samples: {failures[:10]}")


if __name__ == "__main__":
    asyncio.run(main())
