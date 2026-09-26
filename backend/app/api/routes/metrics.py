from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.metrics import MetricsSummaryResponse
from app.services.query_service import query_service

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get(
    "/summary",
    response_model=MetricsSummaryResponse,
    summary="Get internal operational metrics summary for queue, crawls, scoring, and review queue",
)
async def get_metrics_summary(
    db: AsyncSession = Depends(get_db),
) -> MetricsSummaryResponse:
    metrics = await query_service.get_metrics_summary(db)
    return MetricsSummaryResponse(**metrics)
