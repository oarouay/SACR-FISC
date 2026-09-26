from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.schemas.score import ReviewQueueItemResponse
from app.services.query_service import query_service

router = APIRouter(prefix="/review-queue", tags=["Human Review Queue"])


@router.get(
    "",
    response_model=list[ReviewQueueItemResponse],
    summary="Retrieve pages prioritized for human review based on observable commercial evidence",
)
async def get_human_review_queue(
    min_priority: float | None = Query(
        None,
        description="Minimum review priority threshold (defaults to REVIEW_THRESHOLD in config, e.g. 75.0)",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[ReviewQueueItemResponse]:
    effective_threshold = min_priority if min_priority is not None else settings.REVIEW_THRESHOLD
    items = await query_service.get_review_queue(
        db=db,
        min_priority=effective_threshold,
        limit=limit,
        offset=offset,
    )
    return items
