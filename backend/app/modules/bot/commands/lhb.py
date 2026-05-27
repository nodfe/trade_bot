from __future__ import annotations

from datetime import date
from typing import Any

from loguru import logger

from app.modules.bot.adapters.base import BotMessage
from app.modules.bot.commands.base import CommandHandler


class LhbCommand(CommandHandler):
    """查询/触发龙虎榜数据抓取。

    Usage: /lhb [YYYY-MM-DD]
    """

    @property
    def name(self) -> str:
        return "lhb"

    @property
    def description(self) -> str:
        return "查询龙虎榜数据"

    @property
    def usage(self) -> str:
        return "/lhb [日期]  例: /lhb 2025-05-27"

    async def handle(self, message: BotMessage, args: str) -> dict[str, Any]:
        trade_date = None
        if args.strip():
            try:
                trade_date = date.fromisoformat(args.strip())
            except ValueError:
                return {"text": "日期格式错误，请使用 YYYY-MM-DD 格式，例如: /lhb 2025-05-27"}

        try:
            from app.modules.market_data.service import MarketDataService

            svc = MarketDataService()
            result = await svc.sync_dragon_tiger_list(trade_date)

            if result.synced == 0 and "已存在" in result.message:
                # 数据已存在，直接展示
                if trade_date is None:
                    trade_date = date.today()
                items = await svc.get_dragon_tiger_list(trade_date)
                top_items = items[:10]
                return {
                    "card_type": "dragon_tiger",
                    "title": f"龙虎榜 {trade_date}",
                    "message": result.message,
                    "items_count": len(items),
                    "top_items": [
                        {
                            "code": item.code,
                            "name": item.name,
                            "change_pct": item.change_pct,
                            "net_buy": item.net_buy or 0,
                            "reason": item.reason or "",
                        }
                        for item in top_items
                    ],
                }
            elif result.synced == 0:
                return {"text": result.message}
            else:
                # 新抓取的数据
                if trade_date is None:
                    trade_date = date.today()
                items = await svc.get_dragon_tiger_list(trade_date)
                top_items = items[:10]
                return {
                    "card_type": "dragon_tiger",
                    "title": f"龙虎榜 {trade_date}",
                    "message": result.message,
                    "items_count": len(items),
                    "top_items": [
                        {
                            "code": item.code,
                            "name": item.name,
                            "change_pct": item.change_pct,
                            "net_buy": item.net_buy or 0,
                            "reason": item.reason or "",
                        }
                        for item in top_items
                    ],
                }
        except Exception as e:
            logger.error(f"LhbCommand error: {e}")
            return {"text": "龙虎榜查询失败，请稍后重试"}
