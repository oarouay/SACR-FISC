import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.crawl_job import CrawlJob
    from app.models.page import Page
    from app.models.post import Post

JSON_TYPE = JSON().with_variant(postgresql.JSONB, "postgresql")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    crawl_job_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("crawl_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_id: Mapped[uuid.UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("pages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_reference: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    evidence_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON_TYPE, default=dict, nullable=False
    )

    # Relationships
    crawl_job: Mapped["CrawlJob"] = relationship("CrawlJob", back_populates="evidence")
    page: Mapped[Optional["Page"]] = relationship("Page", back_populates="evidence")
    post: Mapped[Optional["Post"]] = relationship("Post", back_populates="evidence")

    __table_args__ = (Index("idx_evidence_job_type", "crawl_job_id", "evidence_type"),)
