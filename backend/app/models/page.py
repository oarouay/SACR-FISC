import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.evidence import Evidence
    from app.models.page_score import PageScore
    from app.models.post import Post
    from app.models.registry_verification import RegistryVerification
    from app.models.signal import ExtractedSignal


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    platform: Mapped[str] = mapped_column(String(50), default="facebook", nullable=False)
    platform_page_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    canonical_url: Mapped[str] = mapped_column(
        String(2048), nullable=False, unique=True, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)

    public_phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    public_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    public_address: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="page",
        cascade="all, delete-orphan",
        order_by="desc(Post.first_seen_at)",
    )
    signals: Mapped[list["ExtractedSignal"]] = relationship(
        "ExtractedSignal", back_populates="page", cascade="all, delete-orphan"
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        "Evidence", back_populates="page", cascade="all, delete-orphan"
    )
    scores: Mapped[list["PageScore"]] = relationship(
        "PageScore", back_populates="page", cascade="all, delete-orphan"
    )
    registry_verification: Mapped["RegistryVerification | None"] = relationship(
        "RegistryVerification", back_populates="page", uselist=False, cascade="all, delete-orphan"
    )
