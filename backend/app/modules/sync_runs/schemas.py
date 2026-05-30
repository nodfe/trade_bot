from datetime import datetime

from pydantic import BaseModel


class SyncRunOut(BaseModel):
    id: int
    job_name: str
    target: str | None
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    synced_count: int | None
    error: str | None
    meta_json: str | None

    model_config = {"from_attributes": True}


class BotCommandLogOut(BaseModel):
    id: int
    platform: str
    chat_id: str
    user_id: str | None
    command: str
    args_text: str | None
    status: str
    error: str | None
    duration_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ServiceHealth(BaseModel):
    """Per-service connectivity & version snapshot.

    `connected` is the canonical "can we reach it right now?" flag.
    `version` is best-effort — None if probing failed or the backend doesn't
    expose one. `error` carries the short diagnostic when connected=False.
    `configured` is true when env credentials are populated, regardless of
    whether the service actually answered the probe.
    """

    name: str
    configured: bool
    connected: bool
    version: str | None = None
    error: str | None = None


class SystemInfoOut(BaseModel):
    """Aggregated system status for the admin Settings page."""

    app_env: str
    app_version: str
    python_version: str
    server_time: datetime
    database: ServiceHealth
    redis: ServiceHealth
    tushare: ServiceHealth
    feishu_bot: ServiceHealth
