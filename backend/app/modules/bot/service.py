from __future__ import annotations

import time
from typing import Any

from loguru import logger

from app.config import settings
from app.modules.bot.adapters.base import BotAdapter, BotMessage, CardAction, CardMessage
from app.modules.bot.adapters.feishu.adapter import FeishuAdapter
from app.modules.bot.adapters.feishu.card_builder import FeishuCardBuilder
from app.modules.bot.command_logs import BotCommandLogRepository
from app.modules.bot.commands.analyze import AnalyzeCommand
from app.modules.bot.commands.base import CommandRouter
from app.modules.bot.commands.help import HelpCommand
from app.modules.bot.commands.lhb import LhbCommand
from app.modules.bot.commands.news import NewsCommand
from app.modules.bot.commands.screen import ScreenCommand
from app.modules.bot.commands.stock import StockCommand
from app.modules.bot.commands.watchlist import WatchlistCommand
from app.modules.bot.commands.zt import ZtCommand
from app.modules.bot.middleware.base import BotMiddleware, NextHandler
from app.modules.bot.session.manager import SessionManager


class BotService:
    """Central service that manages adapters, middleware, and command routing.

    Lifecycle:
        1. BotService is created during app startup.
        2. ``start()`` connects all adapters and begins receiving events.
        3. Incoming messages flow through: adapter -> middleware chain -> command router.
        4. ``stop()`` disconnects all adapters on shutdown.
    """

    def __init__(self) -> None:
        self.adapters: dict[str, BotAdapter] = {}
        self.router = CommandRouter()
        self.middlewares: list[BotMiddleware] = []
        self.sessions = SessionManager()
        self.command_logs = BotCommandLogRepository()

        self._register_commands()
        self._register_adapters()

    # -- public API --

    async def start(self) -> None:
        """Start all adapters."""
        for name, adapter in self.adapters.items():
            try:
                adapter.on_message(self._on_message)
                adapter.on_card_action(self._on_card_action)
                await adapter.start()
                logger.info(f"Bot adapter '{name}' started")
            except Exception as e:
                logger.error(f"Failed to start adapter '{name}': {e}")

    async def stop(self) -> None:
        """Stop all adapters."""
        for name, adapter in self.adapters.items():
            try:
                await adapter.stop()
                logger.info(f"Bot adapter '{name}' stopped")
            except Exception as e:
                logger.error(f"Failed to stop adapter '{name}': {e}")

    def status(self) -> dict[str, Any]:
        """Return the current status of all adapters."""
        return {
            "adapters": {
                name: {"platform": adapter.platform_name}
                for name, adapter in self.adapters.items()
            },
            "commands": self.router.list_commands(),
        }

    # -- internal: registration --

    def _register_commands(self) -> None:
        self.router.register(StockCommand())
        self.router.register(AnalyzeCommand())
        self.router.register(ScreenCommand())
        self.router.register(WatchlistCommand())
        self.router.register(LhbCommand())
        self.router.register(ZtCommand())
        self.router.register(NewsCommand())
        help_cmd = HelpCommand(self.router)
        self.router.register(help_cmd)

    def _register_adapters(self) -> None:
        if settings.feishu_app_id and settings.feishu_app_secret:
            feishu = FeishuAdapter()
            self.adapters["feishu"] = feishu
            return

        logger.info("Skipping Feishu adapter registration because credentials are not configured")

    # -- internal: message handling pipeline --

    async def _on_message(self, message: BotMessage) -> None:
        """Entry point for all incoming text messages.

        The message passes through the middleware chain before being
        dispatched to the appropriate command handler.
        """
        session = self.sessions.get_or_create(message.user_id, message.chat_id)
        session.data["last_message"] = message.text

        # Build the middleware chain: last middleware calls the command dispatcher
        handler: NextHandler = self._dispatch_command
        for mw in reversed(self.middlewares):
            # Capture loop variable correctly
            handler = self._wrap_middleware(mw, handler)

        await handler(message)

    def _wrap_middleware(self, mw: BotMiddleware, next_handler: NextHandler) -> NextHandler:
        """Create a NextHandler that runs a middleware then delegates."""

        async def wrapped(msg: BotMessage) -> None:
            await mw.process(msg, next_handler)

        return wrapped

    async def _dispatch_command(self, message: BotMessage) -> None:
        """Route a message to the correct CommandHandler."""
        handler, args = self.router.get_handler(message.text)
        # Resolve which platform delivered this message. Today only Feishu
        # registers, but plumbing through the platform name keeps the log
        # honest once additional adapters land.
        platform = next(iter(self.adapters.keys()), "unknown")

        if handler is None:
            await self._reply_text(message.chat_id, "未知命令，输入 /help 查看可用命令")
            await self._record_command_log(
                platform=platform,
                message=message,
                command="<no_command>",
                args_text=message.text or None,
                started=time.monotonic(),
                error=None,
            )
            return

        command_name = f"/{handler.name}"
        started = time.monotonic()
        try:
            result = await handler.handle(message, args)
        except Exception as exc:
            await self._record_command_log(
                platform=platform,
                message=message,
                command=command_name,
                args_text=args or None,
                started=started,
                error=str(exc)[:1000],
            )
            raise

        adapter = self.adapters.get(platform)
        if adapter is not None:
            await self._send_result(adapter, message.chat_id, result)

        await self._record_command_log(
            platform=platform,
            message=message,
            command=command_name,
            args_text=args or None,
            started=started,
            error=None,
        )

    async def _record_command_log(
        self,
        *,
        platform: str,
        message: BotMessage,
        command: str,
        args_text: str | None,
        started: float,
        error: str | None,
    ) -> None:
        duration_ms = int((time.monotonic() - started) * 1000)
        try:
            await self.command_logs.create(
                platform=platform,
                chat_id=message.chat_id,
                user_id=message.user_id,
                command=command,
                args_text=args_text,
                status="failed" if error else "success",
                error=error,
                duration_ms=duration_ms,
            )
        except Exception as log_exc:
            # Persistence failure should never break the user-facing reply.
            logger.error(f"Failed to persist bot command log: {log_exc}")

    async def _on_card_action(self, action: CardAction) -> None:
        """Handle card button clicks (e.g. 'analyze:600519')."""
        value = action.action_value
        if not value:
            return

        parts = value.split(":", 1)
        action_type = parts[0]
        code = parts[1] if len(parts) > 1 else ""

        adapter = self.adapters.get("feishu")
        if not adapter:
            return

        if action_type == "analyze" and code:
            # Send a loading card, then submit a Celery task (MVP: inline)
            name = code  # Will be resolved when data returns
            loading_card = FeishuCardBuilder.analysis_loading_card(code, name)
            card_id = (
                await adapter.send_card(action.card_token, loading_card)
                if not action.card_token
                else None
            )

            if card_id is None and action.card_token:
                # Update the existing card with loading state
                await adapter.update_card(action.card_token, loading_card)
                card_id = action.card_token

            # In production: submit Celery task here. For MVP we do inline.
            # from app.modules.bot.tasks import run_analysis
            # run_analysis.delay(code, card_id)

            logger.info(f"Analysis requested for {code}, card_id={card_id}")

        elif action_type == "kline" and code:
            await adapter.send_text(action.card_token, f"K线数据功能开发中: {code}")

    # -- internal: reply helpers --

    async def _reply_text(self, chat_id: str, text: str) -> None:
        adapter = self.adapters.get("feishu")
        if adapter:
            await adapter.send_text(chat_id, text)

    async def _send_result(self, adapter: BotAdapter, chat_id: str, result: dict[str, Any]) -> None:
        """Convert a command result dict into a text or card message."""
        if "text" in result:
            await adapter.send_text(chat_id, result["text"])
            return

        card_type = result.get("card_type", "")

        if card_type == "stock_quote":
            card = FeishuCardBuilder.stock_quote_card(
                code=result["code"],
                name=result["name"],
                price=result["price"],
                change=result["change"],
                change_pct=result["change_pct"],
                volume=result["volume"],
                amount=result["amount"],
                analysis_summary=result.get("analysis_summary"),
            )
            await adapter.send_card(chat_id, card)

        elif card_type == "help":
            card = CardMessage(
                title=result.get("title", "帮助"),
                header_color="blue",
            )
            for elem in result.get("elements", []):
                if elem.get("type") == "field":
                    card.add_field(elem["label"], elem["value"])
            await adapter.send_card(chat_id, card)

        elif card_type == "dragon_tiger":
            card = FeishuCardBuilder.dragon_tiger_card(
                title=result.get("title", "龙虎榜"),
                message=result.get("message", ""),
                items_count=result.get("items_count", 0),
                top_items=result.get("top_items", []),
            )
            await adapter.send_card(chat_id, card)

        elif card_type == "limit_up":
            card = FeishuCardBuilder.limit_up_card(
                title=result.get("title", "涨停板"),
                message=result.get("message", ""),
                items_count=result.get("items_count", 0),
                top_items=result.get("top_items", []),
            )
            await adapter.send_card(chat_id, card)

        elif card_type == "news":
            card = FeishuCardBuilder.news_card(
                title=result.get("title", "财经新闻"),
                message=result.get("message", ""),
                items_count=result.get("items_count", 0),
                top_items=result.get("top_items", []),
            )
            await adapter.send_card(chat_id, card)

        elif card_type == "analysis_result":
            card = FeishuCardBuilder.analysis_result_card(
                code=result["code"],
                name=result["name"],
                summary=result["summary"],
                signals=result.get("signals", []),
                score=result.get("score"),
            )
            await adapter.send_card(chat_id, card)

        elif card_type == "screen_result":
            card = FeishuCardBuilder.screen_result_card(
                title=result["title"],
                message=result["message"],
                items=result.get("items", []),
            )
            await adapter.send_card(chat_id, card)

        elif card_type == "watchlist_result":
            card = FeishuCardBuilder.watchlist_result_card(
                title=result["title"],
                message=result["message"],
                items=result.get("items", []),
            )
            await adapter.send_card(chat_id, card)

        else:
            # Generic card from result
            card = CardMessage(title=result.get("title", ""))
            for elem in result.get("elements", []):
                card.elements.append(elem)
            await adapter.send_card(chat_id, card)
