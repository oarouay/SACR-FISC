import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CrawlMode

if TYPE_CHECKING:
    from app.models.crawl_target import CrawlTarget
    from app.models.evidence import Evidence


class CrawlStatus(enum.StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class CrawlErrorCode(enum.StrEnum):
    INVALID_URL = "INVALID_URL"
    PAGE_NOT_FOUND = "PAGE_NOT_FOUND"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    ACCESS_RESTRICTED = "ACCESS_RESTRICTED"
    CAPTCHA = "CAPTCHA"
    LAYOUT_UNKNOWN = "LAYOUT_UNKNOWN"
    TIMEOUT = "TIMEOUT"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("crawl_targets.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), default="facebook", nullable=False)
    crawl_mode: Mapped[CrawlMode] = mapped_column(
        Enum(CrawlMode, name="crawl_mode_enum", native_enum=False),
        default=CrawlMode.QUICK,
        nullable=False,
    )
    status: Mapped[CrawlStatus] = mapped_column(
        Enum(CrawlStatus, name="crawl_status_enum", native_enum=False),
        default=CrawlStatus.PENDING,
        nullable=False,
        index=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    max_posts: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    max_scroll_cycles: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    posts_collected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    collector_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    target: Mapped["CrawlTarget | None"] = relationship("CrawlTarget", back_populates="jobs")
    evidence: Mapped[list["Evidence"]] = relationship(
        "Evidence", back_populates="crawl_job", cascade="all, delete-orphan"
    )
