import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.crawl_target import CrawlTarget
    from app.models.page import Page

UUID_TYPE = postgresql.UUID(as_uuid=True).with_variant(String(36), "sqlite")
JSON_TYPE = JSON().with_variant(postgresql.JSONB, "postgresql")


class PageScore(Base):
    __tablename__ = "page_scores"

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
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("crawl_targets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    quick_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    commercial_activity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    transaction_evidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    economic_activity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    review_priority_score: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False, index=True
    )

    scoring_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    page: Mapped["Page"] = relationship("Page", back_populates="scores")
    target: Mapped["CrawlTarget | None"] = relationship("CrawlTarget", back_populates="scores")
    reasons: Mapped[list["ScoreReason"]] = relationship(
        "ScoreReason", back_populates="page_score", cascade="all, delete-orphan"
    )


class ScoreReason(Base):
    __tablename__ = "score_reasons"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    page_score_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("page_scores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    component: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    weight_or_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    evidence_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="DETERMINISTIC", nullable=False)
    evidence_post_ids: Mapped[Any] = mapped_column(JSON_TYPE, default=list, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    page_score: Mapped["PageScore"] = relationship("PageScore", back_populates="reasons")
