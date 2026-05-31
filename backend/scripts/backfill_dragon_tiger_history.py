"""Backfill historical 龙虎榜 (dragon-tiger) lists from AKShare.

AKShare's ``stock_lhb_detail_em`` accepts arbitrary ``start_date``/``end_date``
ranges, so we batch by month to keep memory and request size bounded while
amortizing the per-call setup cost. Rows are upserted with PostgreSQL
``INSERT ... ON CONFLICT (trade_date, code, reason) DO UPDATE`` so re-runs are
idempotent against the ``ix_lhb_date_code_reason`` unique index.

Run:
  docker exec tradebot-backend python /app/scripts/backfill_dragon_tiger_history.py
  docker exec tradebot-backend python /app/scripts/backfill_dragon_tiger_history.py --days 730
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import date, timedelta
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from loguru import logger
from sqlalchemy.dialects.postgresql import insert as pg_insert

import akshare as ak  # type: ignore[import-untyped]

from app.core.database import async_session_factory
from app.modules.market_data.models import DragonTigerList

DEFAULT_DAYS = 400
RATE_LIMIT_SLEEP_SEC = 0.6  # AKShare东财接口比较宽松，月级别请求 0.6s 间隔足够


def _month_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """Split [start, end] into monthly inclusive chunks."""
    chunks: list[tuple[date, date]] = []
    cur = start
    while cur <= end:
        if cur.month == 12:
            next_first = date(cur.year + 1, 1, 1)
        else:
            next_first = date(cur.year, cur.month + 1, 1)
        chunk_end = min(next_first - timedelta(days=1), end)
        chunks.append((cur, chunk_end))
        cur = chunk_end + timedelta(days=1)
    return chunks


def _fetch_chunk(start: date, end: date):
    """Synchronous AKShare call returning a DataFrame for the date range."""
    return ak.stock_lhb_detail_em(
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
    )


def _row_to_kwargs(row) -> dict | None:
    """Convert one DataFrame row to DragonTigerList constructor kwargs.

    Returns None if the row cannot be parsed (missing trade_date / code).
    """
    raw_date = row.get("上榜日")
    raw_code = row.get("代码")
    if raw_date is None or raw_code is None:
        return None
    # 上榜日 is a pandas Timestamp; coerce to ``date``.
    try:
        trade_date = raw_date.date() if hasattr(raw_date, "date") else date.fromisoformat(str(raw_date))
    except Exception:
        return None
    code = str(raw_code).zfill(6)
    name = str(row.get("名称") or "")

    def _f(key: str) -> float | None:
        v = row.get(key)
        if v is None:
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        # AKShare uses NaN for missing numerics
        if f != f:
            return None
        return f

    close_price = _f("收盘价") or 0.0
    change_pct = _f("涨跌幅") or 0.0
    reason_raw = row.get("上榜原因")
    reason = str(reason_raw) if reason_raw is not None and str(reason_raw) != "nan" else None
    return {
        "trade_date": trade_date,
        "code": code,
        "name": name,
        "close_price": close_price,
        "change_pct": change_pct,
        "reason": reason,
        # Range endpoint uses 龙虎榜* prefixed names; per-day endpoint uses
        # plain names. We backfill via the range endpoint.
        "buy_amount": _f("龙虎榜买入额"),
        "sell_amount": _f("龙虎榜卖出额"),
        "net_buy": _f("龙虎榜净买额"),
    }


async def _upsert_rows(rows: list[dict]) -> int:
    if not rows:
        return 0
    async with async_session_factory() as session:
        stmt = pg_insert(DragonTigerList).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["trade_date", "code", "reason"],
            set_={
                "name": stmt.excluded.name,
                "close_price": stmt.excluded.close_price,
                "change_pct": stmt.excluded.change_pct,
                "buy_amount": stmt.excluded.buy_amount,
                "sell_amount": stmt.excluded.sell_amount,
                "net_buy": stmt.excluded.net_buy,
            },
        )
        await session.execute(stmt)
        await session.commit()
    return len(rows)


async def _process_chunk(start: date, end: date) -> tuple[int, int, str]:
    """Fetch + upsert one month chunk. Returns (raw_rows, persisted, status)."""
    try:
        df = await asyncio.to_thread(_fetch_chunk, start, end)
    except Exception as exc:  # noqa: BLE001
        return 0, 0, f"fetch_err:{exc.__class__.__name__}:{str(exc)[:120]}"
    if df is None or df.empty:
        return 0, 0, "empty"
    raw = len(df)
    rows: list[dict] = []
    seen: set[tuple[date, str, str | None]] = set()
    for _, row in df.iterrows():
        kwargs = _row_to_kwargs(row)
        if kwargs is None:
            continue
        key = (kwargs["trade_date"], kwargs["code"], kwargs["reason"])
        # Same (date, code, reason) duplicated within a chunk would violate
        # the ON CONFLICT spec (cannot affect same row twice in one stmt).
        if key in seen:
            continue
        seen.add(key)
        rows.append(kwargs)
    try:
        persisted = await _upsert_rows(rows)
    except Exception as exc:  # noqa: BLE001
        return raw, 0, f"upsert_err:{exc.__class__.__name__}:{str(exc)[:120]}"
    return raw, persisted, "ok"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--days", type=int, default=DEFAULT_DAYS,
        help=f"Days back from today to backfill (default {DEFAULT_DAYS})",
    )
    parser.add_argument(
        "--start", type=str, default=None,
        help="Explicit start date YYYY-MM-DD (overrides --days)",
    )
    parser.add_argument(
        "--end", type=str, default=None,
        help="Explicit end date YYYY-MM-DD (default: today)",
    )
    args = parser.parse_args()

    end = date.fromisoformat(args.end) if args.end else date.today()
    if args.start:
        start = date.fromisoformat(args.start)
    else:
        start = end - timedelta(days=args.days)

    chunks = _month_chunks(start, end)
    logger.info(
        f"lhb backfill start range=[{start}, {end}] chunks={len(chunks)}"
    )

    started = time.monotonic()
    total_raw = 0
    total_persisted = 0
    failures: list[tuple[tuple[date, date], str]] = []

    for i, (cs, ce) in enumerate(chunks, 1):
        await asyncio.sleep(RATE_LIMIT_SLEEP_SEC)
        raw, persisted, status = await _process_chunk(cs, ce)
        total_raw += raw
        total_persisted += persisted
        if status not in ("ok", "empty"):
            failures.append(((cs, ce), status))
        elapsed = time.monotonic() - started
        logger.info(
            f"[{i}/{len(chunks)}] {cs}..{ce} raw={raw} persisted={persisted} "
            f"status={status} elapsed={elapsed:.1f}s"
        )

    elapsed = time.monotonic() - started
    logger.info(
        f"lhb backfill done range=[{start}, {end}] raw={total_raw} "
        f"persisted={total_persisted} failures={len(failures)} elapsed={elapsed:.1f}s"
    )
    if failures:
        logger.warning(f"failure samples: {failures[:10]}")


if __name__ == "__main__":
    asyncio.run(main())
