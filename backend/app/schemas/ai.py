import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AIAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    page_id: uuid.UUID | None = None
    post_id: uuid.UUID | None = None
    provider: str
    model: str
    analysis_type: str
    prompt_version: str
    schema_version: str
    input_hash: str
    input_post_ids: list[str] = Field(default_factory=list)
    output_json: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    status: str
    latency_ms: int
    error_message: str | None = None
    created_at: datetime


class ReanalyzeResponse(BaseModel):
    page_id: uuid.UUID
    status: str
    analysis_type: str
    message: str
    output: dict[str, Any] | None = None
