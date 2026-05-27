from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class Session:
    """A single user's conversation session."""

    user_id: str
    chat_id: str
    data: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)


class SessionManager:
    """In-memory session store with TTL-based expiration.

    Each session tracks multi-turn conversation state for a user.
    Can be upgraded to Redis later without changing the interface.
    """

    def __init__(self, ttl_seconds: int = 1800) -> None:
        """
        Args:
            ttl_seconds: Session time-to-live in seconds. Default 30 minutes.
        """
        self.ttl = ttl_seconds
        self._sessions: dict[str, Session] = {}

    def get(self, user_id: str) -> Session | None:
        """Retrieve a session if it exists and has not expired."""
        self._evict_expired()
        return self._sessions.get(user_id)

    def get_or_create(self, user_id: str, chat_id: str) -> Session:
        """Return an existing session or create a new one."""
        session = self.get(user_id)
        if session:
            session.last_active = time.time()
            return session

        session = Session(user_id=user_id, chat_id=chat_id)
        self._sessions[user_id] = session
        return session

    def set(self, user_id: str, key: str, value: Any) -> None:
        """Set a value in the user's session data."""
        session = self._sessions.get(user_id)
        if session:
            session.data[key] = value
            session.last_active = time.time()

    def delete(self, user_id: str) -> None:
        """Remove a session entirely."""
        self._sessions.pop(user_id, None)

    def _evict_expired(self) -> None:
        """Remove sessions that have exceeded the TTL."""
        now = time.time()
        expired = [
            uid for uid, s in self._sessions.items() if now - s.last_active > self.ttl
        ]
        for uid in expired:
            del self._sessions[uid]
            logger.debug(f"Evicted expired session for user {uid}")
