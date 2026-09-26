import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    crawl_job_id: uuid.UUID
    page_id: uuid.UUID | None = None
    post_id: uuid.UUID | None = None
    evidence_type: str
    storage_reference: str
    content_hash: str
    captured_at: datetime
    evidence_metadata: dict[str, Any] = Field(default_factory=dict)
