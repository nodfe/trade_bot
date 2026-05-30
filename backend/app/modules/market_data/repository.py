from datetime import date

from sqlalchemy import exists, func, select

from app.core.database import async_session_factory
from app.modules.market_data.models import DailyBar, DailyNews, DragonTigerList, LimitUpBoard, Stock


class MarketDataRepository:
    async def get_stocks(self) -> list[Stock]:
        async with async_session_factory() as session:
            result = await session.execute(select(Stock).order_by(Stock.code))
            return list(result.scalars().all())

    async def get_stock(self, code: str) -> Stock | None:
        async with async_session_factory() as session:
            result = await session.execute(select(Stock).where(Stock.code == code))
            return result.scalar_one_or_none()

    async def get_latest_daily_bar(
        self, code: str, before: date | None = None
    ) -> DailyBar | None:
        async with async_session_factory() as session:
            stmt = (
                select(DailyBar)
                .where(DailyBar.code == code)
                .order_by(DailyBar.trade_date.desc())
                .limit(1)
            )
            if before:
                stmt = stmt.where(DailyBar.trade_date < before)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_latest_trade_date_for_bars(self, code: str) -> date | None:
        async with async_session_factory() as session:
            result = await session.execute(
                select(DailyBar.trade_date)
                .where(DailyBar.code == code)
                .order_by(DailyBar.trade_date.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def get_latest_trade_date_for_all_bars(self) -> date | None:
        async with async_session_factory() as session:
            result = await session.execute(
                select(DailyBar.trade_date).order_by(DailyBar.trade_date.desc()).limit(1)
            )
            return result.scalar_one_or_none()

    async def get_codes_with_daily_bars(self) -> set[str]:
        """Return distinct stock codes that have at least one row in `daily_bars`.

        Used by the screener to skip stocks with no local data instead of
        falling back to remote API calls (which would block sequentially).
        """
        async with async_session_factory() as session:
            result = await session.execute(select(DailyBar.code).distinct())
            return set(result.scalars().all())

    async def get_eligible_backtest_codes(self) -> list[tuple[str, str, int]]:
        """Return `(code, name, bar_count)` for every stock with locally synced bars.

        Joins `daily_bars` aggregate counts against the `stocks` table so the UI
        can present a meaningful name beside each code. Sorted by bar_count DESC
        so the most-data-rich stocks appear first.
        """
        async with async_session_factory() as session:
            bar_count = func.count(DailyBar.id).label("bar_count")
            stmt = (
                select(DailyBar.code, Stock.name, bar_count)
                .join(Stock, Stock.code == DailyBar.code, isouter=True)
                .group_by(DailyBar.code, Stock.name)
                .order_by(bar_count.desc(), DailyBar.code)
            )
            result = await session.execute(stmt)
            return [(row[0], row[1] or "", int(row[2])) for row in result.all()]

    async def get_latest_trade_date_for_dragon_tiger(self) -> date | None:
        async with async_session_factory() as session:
            result = await session.execute(
                select(DragonTigerList.trade_date)
                .order_by(DragonTigerList.trade_date.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def get_latest_trade_date_for_limit_up(self) -> date | None:
        async with async_session_factory() as session:
            result = await session.execute(
                select(LimitUpBoard.trade_date)
                .order_by(LimitUpBoard.trade_date.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def get_latest_trade_date_for_news(self) -> date | None:
        async with async_session_factory() as session:
            result = await session.execute(
                select(DailyNews.trade_date).order_by(DailyNews.trade_date.desc()).limit(1)
            )
            return result.scalar_one_or_none()

    async def get_daily_bars(
        self, code: str, start_date: date | None = None, end_date: date | None = None
    ) -> list[DailyBar]:
        async with async_session_factory() as session:
            stmt = (
                select(DailyBar)
                .where(DailyBar.code == code)
                .order_by(DailyBar.trade_date.desc())
            )
            if start_date:
                stmt = stmt.where(DailyBar.trade_date >= start_date)
            if end_date:
                stmt = stmt.where(DailyBar.trade_date <= end_date)
            result = await session.execute(stmt.limit(500))
            return list(result.scalars().all())

    async def save_stocks(self, stocks: list[Stock]) -> int:
        async with async_session_factory() as session:
            for stock in stocks:
                await session.merge(stock)
            await session.commit()
            return len(stocks)

    async def save_daily_bars(self, bars: list[DailyBar]) -> int:
        async with async_session_factory() as session:
            for bar in bars:
                await session.merge(bar)
            await session.commit()
            return len(bars)

    # -- Dragon Tiger List (龙虎榜) --

    async def has_dragon_tiger_data(self, trade_date: date) -> bool:
        async with async_session_factory() as session:
            result = await session.execute(
                select(exists().where(DragonTigerList.trade_date == trade_date))
            )
            return bool(result.scalar())

    async def get_dragon_tiger_list(self, trade_date: date) -> list[DragonTigerList]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(DragonTigerList)
                .where(DragonTigerList.trade_date == trade_date)
                .order_by(DragonTigerList.net_buy.desc())
            )
            return list(result.scalars().all())

    async def save_dragon_tiger_list(self, items: list[DragonTigerList]) -> int:
        async with async_session_factory() as session:
            for item in items:
                await session.merge(item)
            await session.commit()
            return len(items)

    # -- Limit Up Board (涨停板) --

    async def has_limit_up_data(self, trade_date: date) -> bool:
        async with async_session_factory() as session:
            result = await session.execute(
                select(exists().where(LimitUpBoard.trade_date == trade_date))
            )
            return bool(result.scalar())

    async def get_limit_up_board(self, trade_date: date) -> list[LimitUpBoard]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(LimitUpBoard)
                .where(LimitUpBoard.trade_date == trade_date)
                .order_by(LimitUpBoard.change_pct.desc())
            )
            return list(result.scalars().all())

    async def save_limit_up_board(self, items: list[LimitUpBoard]) -> int:
        async with async_session_factory() as session:
            for item in items:
                await session.merge(item)
            await session.commit()
            return len(items)

    # -- Daily News (每日新闻) --

    async def has_news_data(self, trade_date: date) -> bool:
        async with async_session_factory() as session:
            result = await session.execute(
                select(exists().where(DailyNews.trade_date == trade_date))
            )
            return bool(result.scalar())

    async def get_daily_news(self, trade_date: date, limit: int = 50) -> list[DailyNews]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(DailyNews)
                .where(DailyNews.trade_date == trade_date)
                .order_by(DailyNews.id.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def save_daily_news(self, items: list[DailyNews]) -> int:
        async with async_session_factory() as session:
            for item in items:
                await session.merge(item)
            await session.commit()
            return len(items)
