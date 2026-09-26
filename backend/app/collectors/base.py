import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models.crawl_job import CrawlStatus


@dataclass
class RawPageMetadata:
    name: str
    canonical_url: str
    platform_page_id: str | None = None
    description: str | None = None
    category: str | None = None
    public_phone: str | None = None
    public_email: str | None = None
    website: str | None = None
    public_address: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawPostData:
    platform_post_id: str | None
    permalink: str | None
    text: str | None
    published_at: datetime | None
    raw_data: dict[str, Any]
    content_hash: str


@dataclass
class EvidenceArtifact:
    evidence_type: str
    data: bytes
    filename_prefix: str
    metadata: dict[str, Any] = field(default_factory=dict)
    extension: str = ".png"
    post_index: int | None = None


@dataclass
class CrawlResult:
    status: CrawlStatus
    posts_collected: int = 0
    page_metadata: RawPageMetadata | None = None
    posts: list[RawPostData] = field(default_factory=list)
    evidence_items: list[EvidenceArtifact] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class BaseCollector(ABC):
    @abstractmethod
    def validate_target(self, url: str) -> bool:
        """Validate if the given URL is supported by this collector."""
        pass

    async def collect_page_metadata(self) -> RawPageMetadata:
        """Collect top-level identity and metadata for the target page."""
        raise NotImplementedError

    async def collect_public_contacts(self) -> dict[str, Any]:
        """Extract publicly visible contacts from intro/about sections."""
        raise NotImplementedError

    async def collect_posts(
        self, max_posts: int = 20, max_scroll_cycles: int = 10
    ) -> list[RawPostData]:
        """Collect up to max_posts using bounded scrolling."""
        raise NotImplementedError

    async def capture_evidence(
        self, evidence_type: str, metadata: dict[str, Any]
    ) -> EvidenceArtifact | None:
        """Capture screenshot or DOM artifact for evidentiary provenance."""
        raise NotImplementedError

    @abstractmethod
    async def run(
        self,
        job_id: uuid.UUID,
        target_url: str,
        max_posts: int = 20,
        max_scroll_cycles: int = 10,
    ) -> CrawlResult:
        """Execute the full collection workflow deterministically."""
        pass
