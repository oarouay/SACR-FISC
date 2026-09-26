import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.signal import SignalResponse


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    page_id: uuid.UUID
    platform_post_id: str | None = None
    permalink: str | None = None
    text: str | None = None
    published_at: datetime | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    raw_data: dict[str, Any]
    content_hash: str


class PostDetailResponse(PostResponse):
    signals: list[SignalResponse] = Field(default_factory=list)
