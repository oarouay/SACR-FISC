"""Initial schema for digital commerce intelligence MVP

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-09-25 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. crawl_jobs table
    op.create_table(
        "crawl_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("target_url", sa.String(length=2048), nullable=False),
        sa.Column("platform", sa.String(length=50), server_default="facebook", nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_posts", sa.Integer(), server_default="20", nullable=False),
        sa.Column("max_scroll_cycles", sa.Integer(), server_default="10", nullable=False),
        sa.Column("posts_collected", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "collector_version", sa.String(length=50), server_default="1.0.0", nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_crawl_jobs_status", "crawl_jobs", ["status"])
    op.create_index("ix_crawl_jobs_target_url", "crawl_jobs", ["target_url"])

    # 2. pages table
    op.create_table(
        "pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(length=50), server_default="facebook", nullable=False),
        sa.Column("platform_page_id", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("public_phone", sa.String(length=100), nullable=True),
        sa.Column("public_email", sa.String(length=255), nullable=True),
        sa.Column("website", sa.String(length=2048), nullable=True),
        sa.Column("public_address", sa.Text(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("canonical_url", name="uq_pages_canonical_url"),
    )
    op.create_index("ix_pages_platform_page_id", "pages", ["platform_page_id"])
    op.create_index("ix_pages_canonical_url", "pages", ["canonical_url"])

    # 3. posts table
    op.create_table(
        "posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "page_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform_post_id", sa.String(length=255), nullable=True),
        sa.Column("permalink", sa.String(length=2048), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "raw_data", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_posts_page_id", "posts", ["page_id"])
    op.create_index("ix_posts_platform_post_id", "posts", ["platform_post_id"])
    op.create_index("ix_posts_permalink", "posts", ["permalink"])
    op.create_index("ix_posts_content_hash", "posts", ["content_hash"])
    op.create_index("idx_page_platform_post", "posts", ["page_id", "platform_post_id"])
    op.create_index("idx_page_content_hash", "posts", ["page_id", "content_hash"])

    # 4. evidence table
    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "crawl_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crawl_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "page_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("posts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("evidence_type", sa.String(length=50), nullable=False),
        sa.Column("storage_reference", sa.String(length=1024), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
    )
    op.create_index("ix_evidence_crawl_job_id", "evidence", ["crawl_job_id"])
    op.create_index("ix_evidence_page_id", "evidence", ["page_id"])
    op.create_index("ix_evidence_post_id", "evidence", ["post_id"])
    op.create_index("ix_evidence_content_hash", "evidence", ["content_hash"])
    op.create_index("idx_evidence_job_type", "evidence", ["crawl_job_id", "evidence_type"])

    # 5. extracted_signals table
    op.create_table(
        "extracted_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "page_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("signal_type", sa.String(length=50), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=False),
        sa.Column("normalized_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column(
            "extraction_method", sa.String(length=50), server_default="regex_v1", nullable=False
        ),
        sa.Column(
            "extraction_version", sa.String(length=50), server_default="1.0.0", nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_extracted_signals_page_id", "extracted_signals", ["page_id"])
    op.create_index("ix_extracted_signals_post_id", "extracted_signals", ["post_id"])
    op.create_index("ix_extracted_signals_signal_type", "extracted_signals", ["signal_type"])
    op.create_index("idx_signal_page_type", "extracted_signals", ["page_id", "signal_type"])
    op.create_index("idx_signal_post_type", "extracted_signals", ["post_id", "signal_type"])


def downgrade() -> None:
    op.drop_table("extracted_signals")
    op.drop_table("evidence")
    op.drop_table("posts")
    op.drop_table("pages")
    op.drop_table("crawl_jobs")
