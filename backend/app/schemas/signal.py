import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    page_id: uuid.UUID
    post_id: uuid.UUID | None = None
    signal_type: str
    raw_value: str
    normalized_value: Any
    confidence: float
    evidence_text: str
    extraction_method: str
    extraction_version: str
    created_at: datetime


class SignalsSummaryResponse(BaseModel):
    total_signals: int
    signals_by_type: dict[str, int]
    signals: list[SignalResponse]
