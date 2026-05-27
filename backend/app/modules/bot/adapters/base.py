from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


@dataclass
class BotMessage:
    """Platform-agnostic incoming message from a bot platform."""

    message_id: str
    chat_id: str
    user_id: str
    text: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CardAction:
    """A user action on an interactive card (e.g. button click)."""

    action_type: str  # e.g. "button"
    action_value: str  # value payload from the button
    card_token: str  # token for updating this card in-place
    raw: dict[str, Any] = field(default=dict)


@dataclass
class CardMessage:
    """Platform-agnostic card definition.

    Each adapter translates this into its native card JSON format.
    """

    title: str = ""
    subtitle: str = ""
    elements: list[dict[str, Any]] = field(default_factory=list)
    header_color: str = "blue"
    card_id: str | None = None  # set when card is sent, used for updates

    # -- convenience builders --

    def add_text(self, text: str) -> CardMessage:
        self.elements.append({"type": "text", "content": text})
        return self

    def add_field(self, label: str, value: str) -> CardMessage:
        self.elements.append({"type": "field", "label": label, "value": value})
        return self

    def add_separator(self) -> CardMessage:
        self.elements.append({"type": "separator"})
        return self

    def add_button(self, label: str, value: str, style: str = "default") -> CardMessage:
        self.elements.append({"type": "button", "label": label, "value": value, "style": style})
        return self

    def add_note(self, text: str) -> CardMessage:
        self.elements.append({"type": "note", "content": text})
        return self


# Callback type aliases
MessageCallback = Callable[[BotMessage], Coroutine[Any, Any, None]]
CardActionCallback = Callable[[CardAction], Coroutine[Any, Any, None]]


class BotAdapter(ABC):
    """Abstract base class for all bot platform adapters.

    Concrete adapters (Feishu, DingTalk, ...) implement this interface
    so the rest of the system stays platform-agnostic.
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform identifier, e.g. 'feishu'."""
        ...

    @abstractmethod
    async def start(self) -> None:
        """Connect to the platform and begin receiving events."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully disconnect from the platform."""
        ...

    @abstractmethod
    async def send_text(self, chat_id: str, text: str) -> str | None:
        """Send a plain text message. Returns the message_id or None on failure."""
        ...

    @abstractmethod
    async def send_card(self, chat_id: str, card: CardMessage) -> str | None:
        """Send an interactive card. Returns the card's update token or None."""
        ...

    @abstractmethod
    async def update_card(self, card_id: str, card: CardMessage) -> bool:
        """Update an existing card in-place. Returns True on success."""
        ...

    def on_message(self, callback: MessageCallback) -> None:
        """Register a handler for incoming text messages."""
        self._message_callbacks.append(callback)

    def on_card_action(self, callback: CardActionCallback) -> None:
        """Register a handler for card interaction events."""
        self._card_action_callbacks.append(callback)

    def __init__(self) -> None:
        self._message_callbacks: list[MessageCallback] = []
        self._card_action_callbacks: list[CardActionCallback] = []

    # -- internal dispatch helpers --

    async def _dispatch_message(self, msg: BotMessage) -> None:
        for cb in self._message_callbacks:
            try:
                await cb(msg)
            except Exception:
                import traceback
                traceback.print_exc()

    async def _dispatch_card_action(self, action: CardAction) -> None:
        for cb in self._card_action_callbacks:
            try:
                await cb(action)
            except Exception:
                import traceback
                traceback.print_exc()
