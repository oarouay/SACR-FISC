import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RegistryStatus


class RegistryVerificationUpdate(BaseModel):
    status: RegistryStatus = Field(..., description="Verification classification")
    source: str | None = Field(None, description="External source consulted, e.g. RNE portal")
    external_reference: str | None = Field(None, description="Registration number / fiscal ID")
    verified_by: str | None = Field(None, description="Officer or auditor username")
    notes: str | None = Field(None, description="Context or findings")


class RegistryVerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    page_id: uuid.UUID
    status: RegistryStatus
    source: str | None = None
    external_reference: str | None = None
    verified_by: str | None = None
    verified_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
