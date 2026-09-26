import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.evidence import Evidence
    from app.models.page import Page
    from app.models.signal import ExtractedSignal

JSON_TYPE = JSON().with_variant(postgresql.JSONB, "postgresql")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    permalink: Mapped[str | None] = mapped_column(String(2048), nullable=True, index=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Relationships
    page: Mapped["Page"] = relationship("Page", back_populates="posts")
    signals: Mapped[list["ExtractedSignal"]] = relationship(
        "ExtractedSignal", back_populates="post", cascade="all, delete-orphan"
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        "Evidence", back_populates="post", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_page_platform_post", "page_id", "platform_post_id"),
        Index("idx_page_content_hash", "page_id", "content_hash"),
    )
