from __future__ import annotations

from typing import Any

from app.modules.bot.adapters.base import BotMessage
from app.modules.bot.commands.base import CommandHandler, CommandRouter


class HelpCommand(CommandHandler):
    """List all available bot commands."""

    def __init__(self, router: CommandRouter) -> None:
        self._router = router

    @property
    def name(self) -> str:
        return "help"

    @property
    def description(self) -> str:
        return "显示可用命令列表"

    @property
    def usage(self) -> str:
        return "/help"

    async def handle(self, message: BotMessage, args: str) -> dict[str, Any]:
        commands = self._router.list_commands()
        if not commands:
            return {"text": "暂无可用命令"}

        elements: list[dict[str, Any]] = []
        for cmd in commands:
            elements.append({"type": "field", "label": cmd["usage"], "value": cmd["description"]})

        return {
            "card_type": "help",
            "title": "可用命令",
            "elements": elements,
        }
