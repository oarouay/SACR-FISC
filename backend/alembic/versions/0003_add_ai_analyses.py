"""Add AI analyses table for Gemini structured intelligence

Revision ID: 0003_add_ai_analyses
Revises: 0002_target_queue_and_scoring
Create Date: 2026-09-26 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_add_ai_analyses"
down_revision: str | None = "0002_target_queue_and_scoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB, "postgresql")
    uuid_type = postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite")

    op.create_table(
        "ai_analyses",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "page_id", uuid_type, sa.ForeignKey("pages.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column(
            "post_id", uuid_type, sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("provider", sa.String(length=50), server_default="gemini", nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("analysis_type", sa.String(length=50), nullable=False),
        sa.Column("prompt_version", sa.String(length=20), server_default="1.0.0", nullable=False),
        sa.Column("schema_version", sa.String(length=20), server_default="1.0.0", nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("input_post_ids", json_type, nullable=False),
        sa.Column("output_json", json_type, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="SUCCESS", nullable=False),
        sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index("ix_ai_analyses_page_id", "ai_analyses", ["page_id"])
    op.create_index("ix_ai_analyses_post_id", "ai_analyses", ["post_id"])
    op.create_index("ix_ai_analyses_analysis_type", "ai_analyses", ["analysis_type"])
    op.create_index("ix_ai_analyses_input_hash", "ai_analyses", ["input_hash"])
    op.create_index("ix_ai_analyses_status", "ai_analyses", ["status"])
    op.create_index("ix_ai_analyses_hash_status", "ai_analyses", ["input_hash", "status"])

    # 2. Add source and evidence_post_ids to score_reasons
    op.add_column(
        "score_reasons",
        sa.Column("source", sa.String(length=30), server_default="DETERMINISTIC", nullable=False),
    )
    op.add_column(
        "score_reasons",
        sa.Column("evidence_post_ids", json_type, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("score_reasons", "evidence_post_ids")
    op.drop_column("score_reasons", "source")
    op.drop_index("ix_ai_analyses_hash_status", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_status", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_input_hash", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_analysis_type", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_post_id", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_page_id", table_name="ai_analyses")
    op.drop_table("ai_analyses")
