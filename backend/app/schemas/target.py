import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CrawlMode, TargetStatus


class TargetCreate(BaseModel):
    url: str = Field(..., description="Facebook Page URL to crawl")
    priority: int = Field(0, description="Higher priority targets are claimed earlier")


class TargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    canonical_url: str
    platform: str
    status: TargetStatus
    priority: int
    crawl_mode: CrawlMode
    quick_score: float | None = None
    final_score: float | None = None
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime | None = None
    last_crawled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TargetImportResponse(BaseModel):
    total_submitted: int
    created_count: int
    duplicates_skipped: int
    targets: list[TargetResponse]
