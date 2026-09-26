import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScoreReasonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    component: str
    reason: str
    weight_or_value: float
    evidence_reference: str | None = None
    source: str = "DETERMINISTIC"
    evidence_post_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class PageScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    page_id: uuid.UUID
    target_id: uuid.UUID | None = None
    quick_score: float | None = None
    commercial_activity_score: float
    transaction_evidence_score: float
    economic_activity_score: float
    review_priority_score: float
    scoring_version: str
    calculated_at: datetime
    reasons: list[ScoreReasonResponse] = Field(default_factory=list)


class ReviewReasonItem(BaseModel):
    reason: str
    source: str = "DETERMINISTIC"
    evidence_post_ids: list[str] = Field(default_factory=list)


class ReviewQueueItemResponse(BaseModel):
    page_id: uuid.UUID
    page_name: str
    canonical_url: str
    review_priority: float
    commercial_activity: float
    transaction_evidence: float
    economic_activity: float
    registry_status: str = "NOT_CHECKED"
    deterministic_summary: dict[str, int] = Field(default_factory=dict)
    ai_summary: dict[str, Any] | None = None
    reasons: list[str] = Field(default_factory=list)
    structured_reasons: list[ReviewReasonItem] = Field(default_factory=list)
    calculated_at: datetime
