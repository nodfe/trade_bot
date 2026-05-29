from __future__ import annotations

from typing import Any

import pytest

from app.modules.bot.adapters.base import BotMessage
from app.modules.bot.commands.base import CommandHandler
from app.modules.bot.service import BotService


class _EchoCommand(CommandHandler):
    @property
    def name(self) -> str:
        return "echo"

    async def handle(self, message: BotMessage, args: str) -> dict[str, Any]:
        return {"text": f"echo: {args}"}


class _BoomCommand(CommandHandler):
    @property
    def name(self) -> str:
        return "boom"

    async def handle(self, message: BotMessage, args: str) -> dict[str, Any]:
        raise RuntimeError("kaboom")


class _RecordingLogRepo:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


def _build_service() -> tuple[BotService, _RecordingLogRepo]:
    service = BotService()
    # Force a deterministic platform name for the tests regardless of env config.
    service.adapters = {}  # no live adapters in unit tests
    recorder = _RecordingLogRepo()
    service.command_logs = recorder  # type: ignore[assignment]
    return service, recorder


@pytest.mark.asyncio
async def test_dispatch_records_success_log() -> None:
    service, recorder = _build_service()
    service.router.register(_EchoCommand())

    msg = BotMessage(
        message_id="m1",
        chat_id="chat-1",
        user_id="user-1",
        text="/echo hello world",
    )
    await service._dispatch_command(msg)

    assert len(recorder.calls) == 1
    entry = recorder.calls[0]
    assert entry["platform"] == "unknown"
    assert entry["chat_id"] == "chat-1"
    assert entry["user_id"] == "user-1"
    assert entry["command"] == "/echo"
    assert entry["args_text"] == "hello world"
    assert entry["status"] == "success"
    assert entry["error"] is None
    assert isinstance(entry["duration_ms"], int)
    assert entry["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_dispatch_records_unknown_command_log() -> None:
    service, recorder = _build_service()

    msg = BotMessage(
        message_id="m2",
        chat_id="chat-2",
        user_id="user-2",
        text="/nope",
    )
    await service._dispatch_command(msg)

    assert len(recorder.calls) == 1
    entry = recorder.calls[0]
    assert entry["command"] == "<no_command>"
    assert entry["args_text"] == "/nope"
    assert entry["status"] == "success"
    assert entry["error"] is None


@pytest.mark.asyncio
async def test_dispatch_records_failure_log_and_reraises() -> None:
    service, recorder = _build_service()
    service.router.register(_BoomCommand())

    msg = BotMessage(
        message_id="m3",
        chat_id="chat-3",
        user_id="user-3",
        text="/boom now",
    )
    with pytest.raises(RuntimeError, match="kaboom"):
        await service._dispatch_command(msg)

    assert len(recorder.calls) == 1
    entry = recorder.calls[0]
    assert entry["command"] == "/boom"
    assert entry["args_text"] == "now"
    assert entry["status"] == "failed"
    assert entry["error"] == "kaboom"


@pytest.mark.asyncio
async def test_dispatch_swallows_log_persistence_failure() -> None:
    """Persistence errors must never break the dispatch flow."""
    service, _ = _build_service()
    service.router.register(_EchoCommand())

    class _BrokenRepo:
        async def create(self, **_: Any) -> None:
            raise RuntimeError("db down")

    service.command_logs = _BrokenRepo()  # type: ignore[assignment]

    msg = BotMessage(
        message_id="m4",
        chat_id="chat-4",
        user_id="user-4",
        text="/echo ping",
    )
    # Must not raise even though the log repository blows up.
    await service._dispatch_command(msg)
