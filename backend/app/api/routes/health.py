from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """
    Health check endpoint verifying database connectivity and runtime versions.
    """
    db_ok = False
    try:
        res = await db.execute(text("SELECT 1"))
        db_ok = res.scalar() == 1
    except Exception:
        db_ok = False

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database_connected=db_ok,
        version="0.1.0",
        environment=settings.ENVIRONMENT,
        collector_version=settings.COLLECTOR_VERSION,
        extractor_version=settings.EXTRACTOR_VERSION,
    )
