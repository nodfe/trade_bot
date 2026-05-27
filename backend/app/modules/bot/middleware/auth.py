from __future__ import annotations

from loguru import logger

from app.modules.bot.adapters.base import BotMessage
from app.modules.bot.middleware.base import BotMiddleware, NextHandler


class AuthMiddleware(BotMiddleware):
    """Placeholder authentication middleware.

    In production this would verify user identity against an allow-list
    or check internal permission tokens. For the MVP it simply passes
    every message through.
    """

    # TODO: implement actual user allow-list or permission check
    ALLOWED_USERS: set[str] = set()

    async def process(self, message: BotMessage, next_handler: NextHandler) -> None:
        if self.ALLOWED_USERS and message.user_id not in self.ALLOWED_USERS:
            logger.warning(f"Unauthorized bot user: {message.user_id}")
            return
        await next_handler(message)
