"""Target queue, explainable page scoring, and registry verification

Revision ID: 0002_target_queue_and_scoring
Revises: 0001_initial_schema
Create Date: 2026-09-25 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_target_queue_and_scoring"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create crawl_targets table
    op.create_table(
        "crawl_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048), nullable=False),
        sa.Column("platform", sa.String(length=50), server_default="facebook", nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("crawl_mode", sa.String(length=20), server_default="QUICK", nullable=False),
        sa.Column("quick_score", sa.Float(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_crawl_targets_canonical_url", "crawl_targets", ["canonical_url"], unique=True
    )
    op.create_index("ix_crawl_targets_status", "crawl_targets", ["status"])
    op.create_index("ix_crawl_targets_priority", "crawl_targets", ["priority"])
    op.create_index("ix_crawl_targets_next_attempt_at", "crawl_targets", ["next_attempt_at"])

    # 2. Add target_id and crawl_mode to crawl_jobs
    op.add_column(
        "crawl_jobs",
        sa.Column(
            "target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crawl_targets.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "crawl_jobs",
        sa.Column("crawl_mode", sa.String(length=20), server_default="QUICK", nullable=False),
    )
    op.create_index("ix_crawl_jobs_target_id", "crawl_jobs", ["target_id"])

    # 3. Create page_scores table
    op.create_table(
        "page_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "page_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crawl_targets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("quick_score", sa.Float(), nullable=True),
        sa.Column("commercial_activity_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("transaction_evidence_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("economic_activity_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("review_priority_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("scoring_version", sa.String(length=50), server_default="1.0.0", nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_page_scores_page_id", "page_scores", ["page_id"])
    op.create_index("ix_page_scores_target_id", "page_scores", ["target_id"])
    op.create_index(
        "ix_page_scores_review_priority_score", "page_scores", ["review_priority_score"]
    )

    # 4. Create score_reasons table
    op.create_table(
        "score_reasons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "page_score_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("page_scores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("component", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("weight_or_value", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("evidence_reference", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_score_reasons_page_score_id", "score_reasons", ["page_score_id"])

    # 5. Create registry_verifications table
    op.create_table(
        "registry_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "page_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=50), server_default="NOT_CHECKED", nullable=False),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("verified_by", sa.String(length=100), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_registry_verifications_page_id", "registry_verifications", ["page_id"], unique=True
    )


def downgrade() -> None:
    op.drop_table("registry_verifications")
    op.drop_table("score_reasons")
    op.drop_table("page_scores")
    op.drop_column("crawl_jobs", "crawl_mode")
    op.drop_column("crawl_jobs", "target_id")
    op.drop_table("crawl_targets")
