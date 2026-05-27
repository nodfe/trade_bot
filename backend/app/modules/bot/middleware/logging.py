from __future__ import annotations

from loguru import logger

from app.modules.bot.adapters.base import BotMessage
from app.modules.bot.middleware.base import BotMiddleware, NextHandler


class LoggingMiddleware(BotMiddleware):
    """Log every incoming bot message with metadata."""

    async def process(self, message: BotMessage, next_handler: NextHandler) -> None:
        logger.info(
            "Bot message received",
            extra={
                "platform": "bot",
                "chat_id": message.chat_id,
                "user_id": message.user_id,
                "text": message.text[:200],
                "message_id": message.message_id,
            },
        )
        await next_handler(message)
