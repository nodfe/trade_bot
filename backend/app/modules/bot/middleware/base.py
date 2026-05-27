from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine

from app.modules.bot.adapters.base import BotMessage


# Middleware chain: each middleware calls next_handler to pass control downstream
NextHandler = Callable[[BotMessage], Coroutine[Any, Any, None]]


class BotMiddleware(ABC):
    """Base class for bot message middleware.

    Middlewares form a chain. Each one receives the message and a
    ``next_handler`` callable that invokes the next middleware (or the
    final command handler).  Typical uses: logging, authentication, rate
    limiting.
    """

    @abstractmethod
    async def process(self, message: BotMessage, next_handler: NextHandler) -> None:
        """Process an incoming message.

        Implementations MUST call ``await next_handler(message)`` to
        continue the chain, or silently drop the message to short-circuit.
        """
        ...
