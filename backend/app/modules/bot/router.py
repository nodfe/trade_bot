from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from loguru import logger

from app.modules.bot.adapters.feishu.auth import FeishuAuth
from app.modules.bot.service import BotService

router = APIRouter(prefix="/bot", tags=["bot"])

bot_service = BotService()
feishu_auth = FeishuAuth()


@router.post("/feishu/webhook")
async def feishu_webhook(request: Request) -> dict[str, Any]:
    """Feishu webhook endpoint (backup to WebSocket mode).

    Feishu sends event payloads here when WebSocket is unavailable.
    This endpoint handles:
      - URL verification handshake (challenge)
      - Event dispatch for im.message.receive_v1
    """
    body = await request.body()
    body_str = body.decode("utf-8")

    # Verify signature
    timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
    nonce = request.headers.get("X-Lark-Request-Nonce", "")
    signature = request.headers.get("X-Lark-Signature", "")

    if not feishu_auth.verify_signature(timestamp, nonce, body_str, signature):
        return {"error": "signature verification failed"}

    import json

    payload = json.loads(body_str)

    # Handle URL verification challenge
    if "challenge" in payload:
        challenge = payload["challenge"]
        token = payload.get("token", "")
        return feishu_auth.handle_url_verification(challenge, token)

    # Handle event callback
    schema = payload.get("schema", "")
    header = payload.get("header", {})
    event_type = header.get("event_type", "")

    if event_type == "im.message.receive_v1":
        event = payload.get("event", {})
        message_data = event.get("message", {})
        sender_data = event.get("sender", {})

        from app.modules.bot.adapters.base import BotMessage

        content_str = message_data.get("content", "{}")
        content = json.loads(content_str) if isinstance(content_str, str) else content_str
        text = content.get("text", "") if message_data.get("msg_type") == "text" else ""

        if text:
            sender_id = sender_data.get("sender_id", {})
            bot_msg = BotMessage(
                message_id=message_data.get("message_id", ""),
                chat_id=message_data.get("chat_id", ""),
                user_id=sender_id.get("open_id", ""),
                text=text.strip(),
                raw=payload,
            )
            # Dispatch through the service pipeline
            await bot_service._on_message(bot_msg)

    return {}


@router.get("/status")
async def bot_status() -> dict[str, Any]:
    """Return the current status of the bot service and its adapters."""
    return bot_service.status()
