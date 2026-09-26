from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    database_connected: bool
    version: str
    environment: str
    collector_version: str
    extractor_version: str


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    detail: Any | None = None
