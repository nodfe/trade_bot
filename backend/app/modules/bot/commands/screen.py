from __future__ import annotations

from typing import Any

from loguru import logger

from app.modules.bot.adapters.base import BotMessage
from app.modules.bot.commands.base import CommandHandler


class ScreenCommand(CommandHandler):
    @property
    def name(self) -> str:
        return "screen"

    @property
    def description(self) -> str:
        return "筛选强势股、放量突破和回撤观察标的"

    @property
    def usage(self) -> str:
        return "/screen <type> [limit=5] [min_return_20d_pct=5] [min_volume_ratio=1.3]"

    async def handle(self, message: BotMessage, args: str) -> dict[str, Any]:
        parts = args.strip().split() if args.strip() else []
        screen_type = parts[0] if parts else "strong_uptrend"
        params = self._parse_params(parts[1:])

        try:
            from app.modules.market_data.service import MarketDataService
            from app.modules.market_data.schemas import StockScreenParams

            svc = MarketDataService()
            result = await svc.screen_stocks(screen_type, StockScreenParams(**params))

            if not result.items:
                return {"text": f"筛选器 {screen_type} 当前暂无结果，请先确认行情数据已同步"}

            title = {
                "strong_uptrend": "强势趋势股",
                "volume_breakout": "放量突破观察",
                "pullback_watch": "回撤观察池",
            }.get(screen_type, f"筛选结果 {screen_type}")

            return {
                "card_type": "screen_result",
                "title": title,
                "message": f"共命中 {result.total} 只，以下展示前 {len(result.items)} 只。参数: {params or {'limit': 5}}",
                "items": [
                    {
                        "symbol": item.symbol,
                        "name": item.name,
                        "match_reason": item.match_reason,
                        "return_20d_pct": item.return_20d_pct,
                        "hot_tags": item.hot_tags,
                    }
                    for item in result.items
                ],
            }
        except Exception as e:
            logger.error(f"ScreenCommand error for {screen_type}: {e}")
            return {"text": f"筛选 {screen_type} 失败，请稍后重试"}

    @staticmethod
    def _parse_params(tokens: list[str]) -> dict[str, int | float]:
        params: dict[str, int | float] = {"limit": 5}
        for token in tokens:
            if "=" not in token:
                continue
            key, raw_value = token.split("=", 1)
            if key == "limit":
                params[key] = int(raw_value)
            elif key in {"min_return_20d_pct", "min_return_5d_pct", "min_volume_ratio", "max_return_5d_pct"}:
                params[key] = float(raw_value)
        return params
