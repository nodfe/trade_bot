from __future__ import annotations

from typing import Any

from loguru import logger

from app.modules.bot.adapters.base import BotMessage
from app.modules.bot.commands.base import CommandHandler


class WatchlistCommand(CommandHandler):
    @property
    def name(self) -> str:
        return "watchlist"

    @property
    def description(self) -> str:
        return "查看已保存候选池摘要"

    @property
    def usage(self) -> str:
        return "/watchlist [关键词]"

    async def handle(self, message: BotMessage, args: str) -> dict[str, Any]:
        keyword = args.strip().lower()

        try:
            from app.modules.watchlist.service import WatchlistService

            svc = WatchlistService()
            watchlists = await svc.list_watchlists()
            if keyword:
                watchlists = [item for item in watchlists if keyword in item.name.lower()]

            if not watchlists:
                return {"text": "当前没有匹配的候选池，请先在后台保存一组 watchlist"}

            top_watchlists = watchlists[:5]
            return {
                "card_type": "watchlist_result",
                "title": "候选池摘要",
                "message": f"共找到 {len(watchlists)} 个候选池，展示前 {len(top_watchlists)} 个",
                "items": [
                    {
                        "name": item.name,
                        "source": item.source_screen_type or "manual",
                        "count": len(item.items),
                    }
                    for item in top_watchlists
                ],
            }
        except Exception as e:
            logger.error(f"WatchlistCommand error: {e}")
            return {"text": "读取候选池失败，请稍后重试"}
