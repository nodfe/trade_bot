from __future__ import annotations

from datetime import date
from typing import Any

from loguru import logger

from app.modules.bot.adapters.base import BotMessage
from app.modules.bot.commands.base import CommandHandler


class NewsCommand(CommandHandler):
    """查询/触发每日新闻抓取。

    Usage: /news [YYYY-MM-DD]
    """

    @property
    def name(self) -> str:
        return "news"

    @property
    def description(self) -> str:
        return "查询每日财经新闻"

    @property
    def usage(self) -> str:
        return "/news [日期]  例: /news 2025-05-27"

    async def handle(self, message: BotMessage, args: str) -> dict[str, Any]:
        trade_date = None
        if args.strip():
            try:
                trade_date = date.fromisoformat(args.strip())
            except ValueError:
                return {"text": "日期格式错误，请使用 YYYY-MM-DD 格式，例如: /news 2025-05-27"}

        try:
            from app.modules.market_data.service import MarketDataService

            svc = MarketDataService()
            result = await svc.sync_daily_news(trade_date)

            if result.synced == 0 and "已存在" in result.message:
                if trade_date is None:
                    trade_date = date.today()
                items = await svc.get_daily_news(trade_date, limit=10)
                return {
                    "card_type": "news",
                    "title": f"财经新闻 {trade_date}",
                    "message": result.message,
                    "items_count": len(items),
                    "top_items": [
                        {
                            "title": item.title,
                            "source": item.source or "",
                            "url": item.url or "",
                        }
                        for item in items
                    ],
                }
            elif result.synced == 0:
                return {"text": result.message}
            else:
                if trade_date is None:
                    trade_date = date.today()
                items = await svc.get_daily_news(trade_date, limit=10)
                return {
                    "card_type": "news",
                    "title": f"财经新闻 {trade_date}",
                    "message": result.message,
                    "items_count": len(items),
                    "top_items": [
                        {
                            "title": item.title,
                            "source": item.source or "",
                            "url": item.url or "",
                        }
                        for item in items
                    ],
                }
        except Exception as e:
            logger.error(f"NewsCommand error: {e}")
            return {"text": "新闻查询失败，请稍后重试"}
