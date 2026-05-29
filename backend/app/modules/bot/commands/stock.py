from __future__ import annotations

from typing import Any

from loguru import logger

from app.modules.bot.adapters.base import BotMessage
from app.modules.bot.commands.base import CommandHandler


class StockCommand(CommandHandler):
    """Query real-time stock quote and return a card.

    Usage: /stock 600519
    """

    @property
    def name(self) -> str:
        return "stock"

    @property
    def description(self) -> str:
        return "查询股票实时行情"

    @property
    def usage(self) -> str:
        return "/stock <股票代码>"

    async def handle(self, message: BotMessage, args: str) -> dict[str, Any]:
        code = args.strip().split()[0] if args.strip() else ""

        if not code:
            return {"text": "请提供股票代码，例如: /stock 600519"}

        try:
            from app.modules.market_data.service import MarketDataService

            svc = MarketDataService()
            result = await svc.get_stock_quote(code)
            analysis = await svc.get_stock_analysis_summary(code)

            if not result:
                return {"text": f"未找到股票 {code}，请检查代码是否正确"}

            quote, is_delayed = result
            return {
                "card_type": "stock_quote",
                "code": quote.code,
                "name": quote.name,
                "price": quote.price,
                "change": quote.change,
                "change_pct": quote.change_pct,
                "volume": quote.volume,
                "amount": quote.amount,
                "is_delayed": is_delayed,
                "analysis_summary": analysis.summary if analysis else "分析摘要暂不可用",
                "trend_bias": analysis.trend_bias if analysis else "neutral",
            }
        except Exception as e:
            logger.error(f"StockCommand error for {code}: {e}")
            return {"text": f"查询 {code} 行情失败，请稍后重试"}
