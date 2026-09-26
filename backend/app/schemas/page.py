import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: str
    platform_page_id: str | None = None
    name: str
    canonical_url: str
    description: str | None = None
    category: str | None = None
    public_phone: str | None = None
    public_email: str | None = None
    website: str | None = None
    public_address: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class PageDetailResponse(PageResponse):
    posts_count: int = 0
    signals_count: int = 0
    signals_summary: dict[str, int] = Field(default_factory=dict)
