from datetime import datetime

from pydantic import BaseModel, Field


class WatchlistItemCreate(BaseModel):
    stock_code: str
    stock_name: str
    match_reason: str | None = None
    hot_tags: list[str] = Field(default_factory=list)


class WatchlistCreate(BaseModel):
    name: str
    source_screen_type: str | None = None
    screen_params_json: str | None = None
    auto_refresh: str = "manual"
    notes: str | None = None
    items: list[WatchlistItemCreate]


class WatchlistItemOut(BaseModel):
    id: str
    stock_code: str
    stock_name: str
    match_reason: str | None
    hot_tags: list[str]
    created_at: datetime


class WatchlistOut(BaseModel):
    id: str
    name: str
    source_screen_type: str | None
    screen_params_json: str | None
    auto_refresh: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
    last_refreshed_at: datetime | None
    items: list[WatchlistItemOut]
