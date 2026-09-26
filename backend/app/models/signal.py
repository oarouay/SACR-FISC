import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.page import Page
    from app.models.post import Post

JSON_TYPE = JSON().with_variant(postgresql.JSONB, "postgresql")


class ExtractedSignal(Base):
    __tablename__ = "extracted_signals"

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
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    signal_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[Any] = mapped_column(JSON_TYPE, nullable=False)

    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)

    extraction_method: Mapped[str] = mapped_column(String(50), default="regex_v1", nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    page: Mapped["Page"] = relationship("Page", back_populates="signals")
    post: Mapped[Optional["Post"]] = relationship("Post", back_populates="signals")

    __table_args__ = (
        Index("idx_signal_page_type", "page_id", "signal_type"),
        Index("idx_signal_post_type", "post_id", "signal_type"),
    )
