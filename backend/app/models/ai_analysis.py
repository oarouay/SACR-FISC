import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.page import Page
    from app.models.post import Post

UUID_TYPE = postgresql.UUID(as_uuid=True)
JSON_TYPE = JSON().with_variant(postgresql.JSONB, "postgresql")


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        primary_key=True,
        default=uuid.uuid4,
    )
    page_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID_TYPE,
        ForeignKey("pages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID_TYPE,
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    provider: Mapped[str] = mapped_column(String(50), default="gemini", nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    analysis_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    prompt_version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)

    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    input_post_ids: Mapped[Any] = mapped_column(JSON_TYPE, default=list, nullable=False)
    output_json: Mapped[Any] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="SUCCESS", nullable=False, index=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    page: Mapped["Page | None"] = relationship("Page", backref="ai_analyses", lazy="selectin")
    post: Mapped["Post | None"] = relationship("Post", backref="ai_analyses", lazy="selectin")

    __table_args__ = (Index("ix_ai_analyses_hash_status", "input_hash", "status"),)
