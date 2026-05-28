from __future__ import annotations

from datetime import datetime
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
                        "auto_refresh": item.auto_refresh,
                        "last_refreshed_at": self._format_timestamp(item.last_refreshed_at),
                        "params": self._summarize_params(item.screen_params_json),
                    }
                    for item in top_watchlists
                ],
            }
        except Exception as e:
            logger.error(f"WatchlistCommand error: {e}")
            return {"text": "读取候选池失败，请稍后重试"}

    @staticmethod
    def _format_timestamp(value: datetime | None) -> str:
        if value is None:
            return "未刷新"
        return value.strftime("%m-%d %H:%M")

    @staticmethod
    def _summarize_params(screen_params_json: str | None) -> str:
        if not screen_params_json:
            return "手动候选池"

        try:
            import json

            parsed = json.loads(screen_params_json)
        except Exception:
            return "参数不可读"

        parts: list[str] = []
        if parsed.get("limit") is not None:
            parts.append(f"数量 {parsed['limit']}")
        if parsed.get("min_return_20d_pct") is not None:
            parts.append(f"20日>={parsed['min_return_20d_pct']}%")
        if parsed.get("min_volume_ratio") is not None:
            parts.append(f"量比>={parsed['min_volume_ratio']}x")
        if parsed.get("max_return_5d_pct") is not None:
            parts.append(f"5日<={parsed['max_return_5d_pct']}%")

        return " / ".join(parts) if parts else "已保存筛选参数"
