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
