import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RegistryStatus

if TYPE_CHECKING:
    from app.models.page import Page


class RegistryVerification(Base):
    __tablename__ = "registry_verifications"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("pages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[RegistryStatus] = mapped_column(
        Enum(RegistryStatus, name="registry_status_enum", native_enum=False),
        default=RegistryStatus.NOT_CHECKED,
        nullable=False,
    )
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

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

    page: Mapped["Page"] = relationship("Page", back_populates="registry_verification")
