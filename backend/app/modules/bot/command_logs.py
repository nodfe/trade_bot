"""Bot command audit log.

Records every bot command dispatch (success or failure) for observability.
The bot dispatch site is responsible for calling ``BotCommandLogRepository.create``
once a command finishes (or fails). Read API lives in
``app.modules.sync_runs.router`` under ``/api/v1/system/bot-command-logs``.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, async_session_factory


class BotCommandLog(Base):
    __tablename__ = "bot_command_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(20))
    chat_id: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[str | None] = mapped_column(String(100))
    command: Mapped[str] = mapped_column(String(50))
    args_text: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(String(1000))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )


class BotCommandLogRepository:
    async def create(
        self,
        *,
        platform: str,
        chat_id: str,
        command: str,
        status: str,
        user_id: str | None = None,
        args_text: str | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> BotCommandLog:
        async with async_session_factory() as session:
            log = BotCommandLog(
                platform=platform,
                chat_id=chat_id,
                user_id=user_id,
                command=command,
                args_text=args_text[:500] if args_text else None,
                status=status,
                error=error[:1000] if error else None,
                duration_ms=duration_ms,
                created_at=datetime.utcnow(),
            )
            session.add(log)
            await session.commit()
            await session.refresh(log)
            return log

    async def list_recent(self, limit: int = 50) -> list[BotCommandLog]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(BotCommandLog).order_by(BotCommandLog.created_at.desc()).limit(limit)
            )
            return list(result.scalars().all())
