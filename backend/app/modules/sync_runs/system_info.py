"""System health & info aggregator for the Settings page.

Probes optional dependencies (DB, Redis, Tushare, Feishu) and returns a
unified snapshot. Probes are best-effort — a single failed dependency
must NOT crash the endpoint, just surface the error string.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

from sqlalchemy import text

from app.config import settings
from app.core.database import async_session_factory
from app.core.redis import redis_client
from app.modules.sync_runs.schemas import ServiceHealth, SystemInfoOut


async def _probe_database() -> ServiceHealth:
    try:
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT version()"))
            version_str = result.scalar()
        return ServiceHealth(
            name="database",
            configured=True,
            connected=True,
            version=str(version_str).split(" on ", 1)[0] if version_str else None,
        )
    except Exception as e:  # noqa: BLE001 — surface any driver/network error
        return ServiceHealth(
            name="database",
            configured=True,
            connected=False,
            error=str(e)[:200],
        )


async def _probe_redis() -> ServiceHealth:
    try:
        info = await redis_client.info(section="server")
        return ServiceHealth(
            name="redis",
            configured=True,
            connected=True,
            version=info.get("redis_version") if isinstance(info, dict) else None,
        )
    except Exception as e:  # noqa: BLE001
        return ServiceHealth(
            name="redis",
            configured=True,
            connected=False,
            error=str(e)[:200],
        )


def _probe_tushare() -> ServiceHealth:
    """Tushare is configured-only — we don't burn API quota for a health check."""
    configured = bool(settings.tushare_token.strip())
    return ServiceHealth(
        name="tushare",
        configured=configured,
        connected=configured,  # Treat configured == reachable for display.
        version=None,
        error=None if configured else "TUSHARE_TOKEN not set",
    )


def _probe_feishu() -> ServiceHealth:
    """Feishu Bot is configured if both APP_ID and APP_SECRET are set."""
    has_app_id = bool(settings.feishu_app_id.strip())
    has_secret = bool(settings.feishu_app_secret.strip())
    configured = has_app_id and has_secret
    if configured:
        return ServiceHealth(
            name="feishu_bot", configured=True, connected=True, version=None
        )
    missing = []
    if not has_app_id:
        missing.append("FEISHU_APP_ID")
    if not has_secret:
        missing.append("FEISHU_APP_SECRET")
    return ServiceHealth(
        name="feishu_bot",
        configured=False,
        connected=False,
        error=f"Missing: {', '.join(missing)}",
    )


async def get_system_info() -> SystemInfoOut:
    db_health = await _probe_database()
    redis_health = await _probe_redis()
    tushare_health = _probe_tushare()
    feishu_health = _probe_feishu()

    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return SystemInfoOut(
        app_env=settings.app_env,
        app_version="0.1.0",
        python_version=py_ver,
        server_time=datetime.now(UTC),
        database=db_health,
        redis=redis_health,
        tushare=tushare_health,
        feishu_bot=feishu_health,
    )
