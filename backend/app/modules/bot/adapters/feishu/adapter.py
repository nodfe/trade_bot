from __future__ import annotations

import json
from typing import Any

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    PatchMessageRequest,
    PatchMessageRequestBody,
)
from loguru import logger

from app.config import settings
from app.modules.bot.adapters.base import BotAdapter, BotMessage, CardAction, CardMessage
from app.modules.bot.adapters.feishu.card_builder import FeishuCardBuilder


class FeishuAdapter(BotAdapter):
    """Feishu bot adapter using lark-oapi SDK v2 with WebSocket mode.

    WebSocket mode does not require a public IP -- the SDK maintains a
    persistent connection to Feishu's event server.
    """

    def __init__(self) -> None:
        super().__init__()
        self.app_id = settings.feishu_app_id
        self.app_secret = settings.feishu_app_secret
        self.client: lark.Client | None = None
        self.ws_client: lark.ws.Client | None = None

    @property
    def platform_name(self) -> str:
        return "feishu"

    async def start(self) -> None:
        """Initialize the lark client and start the WebSocket event stream."""
        self.client = lark.Client(
            app_id=self.app_id,
            app_secret=self.app_secret,
            app_type=lark.AppType.SELF_BUILT,
        )

        # Register event handler for im.message.receive_v1
        def on_message_recv(ctx: lark.Context, conf: lark.Config, event: Any) -> None:
            self._handle_message_event(event)

        def on_card_action(ctx: lark.Context, conf: lark.Config, event: Any) -> None:
            self._handle_card_event(event)

        self.ws_client = lark.ws.Client(
            self.app_id,
            self.app_secret,
            event_handler=on_message_recv,
            log_level=lark.LogLevel.DEBUG,
        )

        # Register card action callback
        self.ws_client.card_handler = on_card_action

        logger.info("FeishuAdapter starting WebSocket connection...")
        # ws_client.start() is blocking; run it in a background thread
        import threading

        thread = threading.Thread(target=self.ws_client.start, daemon=True)
        thread.start()
        logger.info("FeishuAdapter WebSocket client started")

    async def stop(self) -> None:
        """Stop the WebSocket client."""
        if self.ws_client:
            # lark-oapi ws client does not expose a clean stop method;
            # the daemon thread will be killed when the process exits.
            logger.info("FeishuAdapter stopping (daemon thread will exit with process)")
        self.ws_client = None
        self.client = None

    async def send_text(self, chat_id: str, text: str) -> str | None:
        """Send a plain text message to a Feishu chat."""
        if not self.client:
            logger.error("FeishuAdapter not started -- call start() first")
            return None

        try:
            body = CreateMessageRequestBody(
                msg_type="text",
                content=json.dumps({"text": text}),
            )
            req = CreateMessageRequest(
                receive_id_type="chat_id",
                request_body=body,
            )
            req.receive_id = chat_id

            resp = self.client.im.v1.message.create(req)
            if not resp.success():
                logger.error(f"Feishu send_text failed: {resp.code} {resp.msg}")
                return None
            return resp.data.message_id
        except Exception as e:
            logger.error(f"Feishu send_text error: {e}")
            return None

    async def send_card(self, chat_id: str, card: CardMessage) -> str | None:
        """Send an interactive card message. Returns the message_id for updates."""
        if not self.client:
            logger.error("FeishuAdapter not started -- call start() first")
            return None

        try:
            card_json = FeishuCardBuilder.build(card)
            body = CreateMessageRequestBody(
                msg_type="interactive",
                content=json.dumps(card_json),
            )
            req = CreateMessageRequest(
                receive_id_type="chat_id",
                request_body=body,
            )
            req.receive_id = chat_id

            resp = self.client.im.v1.message.create(req)
            if not resp.success():
                logger.error(f"Feishu send_card failed: {resp.code} {resp.msg}")
                return None

            msg_id = resp.data.message_id
            card.card_id = msg_id
            return msg_id
        except Exception as e:
            logger.error(f"Feishu send_card error: {e}")
            return None

    async def update_card(self, card_id: str, card: CardMessage) -> bool:
        """Update an existing card message in-place by its message_id."""
        if not self.client:
            logger.error("FeishuAdapter not started -- call start() first")
            return False

        try:
            card_json = FeishuCardBuilder.build(card)
            body = PatchMessageRequestBody(content=json.dumps(card_json))
            req = PatchMessageRequest(message_id=card_id, request_body=body)

            resp = self.client.im.v1.message.patch(req)
            if not resp.success():
                logger.error(f"Feishu update_card failed: {resp.code} {resp.msg}")
                return False
            return True
        except Exception as e:
            logger.error(f"Feishu update_card error: {e}")
            return False

    # -- event handlers (called from SDK thread, dispatch to async) --

    def _handle_message_event(self, event: Any) -> None:
        """Parse im.message.receive_v1 event and dispatch to registered callbacks."""
        import asyncio

        try:
            event_data = event.event if hasattr(event, "event") else event
            msg = event_data.message
            sender = event_data.sender

            text = ""
            content = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            if msg.msg_type == "text":
                text = content.get("text", "")
            elif msg.msg_type == "interactive":
                # Card interaction handled separately via card_handler
                return

            if not text:
                return

            bot_msg = BotMessage(
                message_id=msg.message_id,
                chat_id=msg.chat_id,
                user_id=sender.sender_id.open_id if hasattr(sender.sender_id, "open_id") else str(sender.sender_id),
                text=text.strip(),
                raw={
                    "msg_type": msg.msg_type,
                    "chat_type": msg.chat_type,
                },
            )

            # Dispatch from SDK thread to async event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._dispatch_message(bot_msg))
            else:
                loop.run_until_complete(self._dispatch_message(bot_msg))
        except Exception as e:
            logger.error(f"Error handling Feishu message event: {e}")

    def _handle_card_event(self, event: Any) -> None:
        """Parse card action callback event."""
        import asyncio

        try:
            action = event.action if hasattr(event, "action") else event
            action_value = ""
            if hasattr(action, "value") and isinstance(action.value, dict):
                action_value = action.value.get("action", "")

            card_token = event.open_message_id if hasattr(event, "open_message_id") else ""

            card_action = CardAction(
                action_type="button",
                action_value=action_value,
                card_token=card_token,
                raw={
                    "open_id": event.open_id if hasattr(event, "open_id") else "",
                    "token": event.token if hasattr(event, "token") else "",
                },
            )

            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._dispatch_card_action(card_action))
            else:
                loop.run_until_complete(self._dispatch_card_action(card_action))
        except Exception as e:
            logger.error(f"Error handling Feishu card event: {e}")
