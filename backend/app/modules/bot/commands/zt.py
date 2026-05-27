from __future__ import annotations

from datetime import date
from typing import Any

from loguru import logger

from app.modules.bot.adapters.base import BotMessage
from app.modules.bot.commands.base import CommandHandler


class ZtCommand(CommandHandler):
    """查询/触发涨停板数据抓取。

    Usage: /zt [YYYY-MM-DD]
    """

    @property
    def name(self) -> str:
        return "zt"

    @property
    def description(self) -> str:
        return "查询涨停板数据"

    @property
    def usage(self) -> str:
        return "/zt [日期]  例: /zt 2025-05-27"

    async def handle(self, message: BotMessage, args: str) -> dict[str, Any]:
        trade_date = None
        if args.strip():
            try:
                trade_date = date.fromisoformat(args.strip())
            except ValueError:
                return {"text": "日期格式错误，请使用 YYYY-MM-DD 格式，例如: /zt 2025-05-27"}

        try:
            from app.modules.market_data.service import MarketDataService

            svc = MarketDataService()
            result = await svc.sync_limit_up_board(trade_date)

            if result.synced == 0 and "已存在" in result.message:
                if trade_date is None:
                    trade_date = date.today()
                items = await svc.get_limit_up_board(trade_date)
                top_items = items[:10]
                return {
                    "card_type": "limit_up",
                    "title": f"涨停板 {trade_date}",
                    "message": result.message,
                    "items_count": len(items),
                    "top_items": [
                        {
                            "code": item.code,
                            "name": item.name,
                            "change_pct": item.change_pct,
                            "open_times": item.open_times or 0,
                            "reason": item.reason or "",
                        }
                        for item in top_items
                    ],
                }
            elif result.synced == 0:
                return {"text": result.message}
            else:
                if trade_date is None:
                    trade_date = date.today()
                items = await svc.get_limit_up_board(trade_date)
                top_items = items[:10]
                return {
                    "card_type": "limit_up",
                    "title": f"涨停板 {trade_date}",
                    "message": result.message,
                    "items_count": len(items),
                    "top_items": [
                        {
                            "code": item.code,
                            "name": item.name,
                            "change_pct": item.change_pct,
                            "open_times": item.open_times or 0,
                            "reason": item.reason or "",
                        }
                        for item in top_items
                    ],
                }
        except Exception as e:
            logger.error(f"ZtCommand error: {e}")
            return {"text": "涨停板查询失败，请稍后重试"}
