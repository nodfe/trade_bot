from __future__ import annotations

from typing import Any

from loguru import logger

from app.modules.bot.adapters.base import BotMessage
from app.modules.bot.commands.base import CommandHandler


class AnalyzeCommand(CommandHandler):
    @property
    def name(self) -> str:
        return "analyze"

    @property
    def description(self) -> str:
        return "输出股票技术分析摘要"

    @property
    def usage(self) -> str:
        return "/analyze <股票代码>"

    async def handle(self, message: BotMessage, args: str) -> dict[str, Any]:
        code = args.strip().split()[0] if args.strip() else ""

        if not code:
            return {"text": "请提供股票代码，例如: /analyze 600519"}

        try:
            from app.modules.market_data.service import MarketDataService

            svc = MarketDataService()
            stock = await svc.get_stock(code)
            analysis = await svc.get_stock_analysis_summary(code)

            if not analysis:
                return {"text": f"未找到 {code} 的分析摘要，请先确认日线数据已同步"}

            name = stock.name if stock else code

            score = self._score_analysis(
                analysis.trend_bias,
                analysis.rsi14,
                analysis.macd_histogram,
            )
            return {
                "card_type": "analysis_result",
                "code": code,
                "name": name,
                "summary": analysis.summary,
                "signals": analysis.signals,
                "score": score,
            }
        except Exception as e:
            logger.error(f"AnalyzeCommand error for {code}: {e}")
            return {"text": f"分析 {code} 失败，请稍后重试"}

    @staticmethod
    def _score_analysis(trend_bias: str, rsi14: float | None, macd_histogram: float | None) -> int:
        score = 50

        if trend_bias == "bullish":
            score += 20
        elif trend_bias == "bearish":
            score -= 20

        if rsi14 is not None:
            if 45 <= rsi14 <= 70:
                score += 10
            elif rsi14 < 30 or rsi14 > 80:
                score -= 10

        if macd_histogram is not None:
            score += 10 if macd_histogram > 0 else -10

        return max(0, min(100, score))
