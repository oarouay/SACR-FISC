import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, Integer, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CrawlMode, TargetStatus

if TYPE_CHECKING:
    from app.models.crawl_job import CrawlJob
    from app.models.page_score import PageScore


class CrawlTarget(Base):
    __tablename__ = "crawl_targets"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    canonical_url: Mapped[str] = mapped_column(
        String(2048), nullable=False, unique=True, index=True
    )
    platform: Mapped[str] = mapped_column(String(50), default="facebook", nullable=False)
    status: Mapped[TargetStatus] = mapped_column(
        Enum(TargetStatus, name="target_status_enum", native_enum=False),
        default=TargetStatus.PENDING,
        nullable=False,
        index=True,
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    crawl_mode: Mapped[CrawlMode] = mapped_column(
        Enum(CrawlMode, name="crawl_mode_enum", native_enum=False),
        default=CrawlMode.QUICK,
        nullable=False,
    )
    quick_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    jobs: Mapped[list["CrawlJob"]] = relationship(
        "CrawlJob", back_populates="target", cascade="all, delete-orphan"
    )
    scores: Mapped[list["PageScore"]] = relationship(
        "PageScore", back_populates="target", cascade="all, delete-orphan"
    )
