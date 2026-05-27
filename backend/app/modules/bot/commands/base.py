from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from app.modules.bot.adapters.base import BotMessage


class CommandHandler(ABC):
    """Abstract base for a single /command handler.

    Each command declares the keyword it responds to and implements
    ``handle`` which returns a dict that will be turned into a CardMessage
    by the caller (usually BotService).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Command keyword without the leading slash, e.g. 'stock'."""
        ...

    @property
    def description(self) -> str:
        """Short help text shown by /help."""
        return ""

    @property
    def usage(self) -> str:
        """Usage string, e.g. '/stock 600519'."""
        return f"/{self.name}"

    @abstractmethod
    async def handle(self, message: BotMessage, args: str) -> dict[str, Any]:
        """Execute the command.

        Args:
            message: The original BotMessage that triggered this command.
            args: The text after the command keyword, already stripped.

        Returns:
            A dict with card-building data (title, elements, etc.) or a
            ``{"text": "..."}`` for simple text responses.
        """
        ...


class CommandRouter:
    """Parse ``/command args`` and dispatch to the registered CommandHandler.

    Commands are identified by the leading ``/`` followed by a word.
    Everything after that word is passed as ``args``.
    """

    _COMMAND_RE = re.compile(r"^/(\w+)\s*(.*)", re.DOTALL)

    def __init__(self) -> None:
        self._handlers: dict[str, CommandHandler] = {}

    def register(self, handler: CommandHandler) -> None:
        self._handlers[handler.name] = handler

    def get_handler(self, text: str) -> tuple[CommandHandler | None, str]:
        """Try to parse ``text`` as a /command.

        Returns:
            (handler, args) if matched, (None, text) otherwise.
        """
        m = self._COMMAND_RE.match(text.strip())
        if not m:
            return None, text

        cmd_name = m.group(1).lower()
        args = m.group(2).strip()
        handler = self._handlers.get(cmd_name)
        return handler, args

    @property
    def handlers(self) -> dict[str, CommandHandler]:
        return self._handlers

    def list_commands(self) -> list[dict[str, str]]:
        """Return a summary of all registered commands for /help."""
        return [
            {
                "name": h.name,
                "description": h.description,
                "usage": h.usage,
            }
            for h in self._handlers.values()
        ]
