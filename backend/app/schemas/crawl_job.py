import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.crawl_job import CrawlStatus


class CrawlJobCreate(BaseModel):
    url: str = Field(..., description="Target Facebook Page URL to crawl")
    max_posts: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of posts to collect",
    )
    max_scroll_cycles: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum scroll iterations to attempt",
    )


class CrawlJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_url: str
    platform: str
    status: CrawlStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    max_posts: int
    max_scroll_cycles: int
    posts_collected: int
    error_code: str | None = None
    error_message: str | None = None
    collector_version: str
    created_at: datetime


class CrawlJobCreateResponse(BaseModel):
    job_id: uuid.UUID
    status: CrawlStatus
    message: str = "Crawl job accepted and queued for execution."


class CrawlJobDetailResponse(CrawlJobResponse):
    page_id: uuid.UUID | None = None
    page_name: str | None = None
    evidence_count: int = 0
    signals_summary: dict[str, int] = Field(default_factory=dict)
