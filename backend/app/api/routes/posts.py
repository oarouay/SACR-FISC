import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.ai import AIAnalysisResponse
from app.schemas.post import PostDetailResponse, PostResponse
from app.schemas.signal import SignalResponse, SignalsSummaryResponse
from app.services.query_service import query_service

router = APIRouter(prefix="/posts", tags=["Posts"])


@router.get(
    "/{post_id}",
    response_model=PostDetailResponse,
    summary="Get post details along with its extracted signals",
)
async def get_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PostDetailResponse:
    post = await query_service.get_post(db, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post {post_id} not found",
        )
    signals = await query_service.get_post_signals(db, post_id)
    data = PostResponse.model_validate(post).model_dump()
    data["signals"] = [SignalResponse.model_validate(s) for s in signals]
    return PostDetailResponse(**data)


@router.get(
    "/{post_id}/signals",
    response_model=SignalsSummaryResponse,
    summary="Get commercial signals extracted from a specific post",
)
async def get_post_signals(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SignalsSummaryResponse:
    post = await query_service.get_post(db, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post {post_id} not found",
        )
    signals = await query_service.get_post_signals(db, post_id)
    summary: dict[str, int] = {}
    sig_responses = []
    for s in signals:
        summary[s.signal_type] = summary.get(s.signal_type, 0) + 1
        sig_responses.append(SignalResponse.model_validate(s))

    return SignalsSummaryResponse(
        total_signals=len(signals),
        signals_by_type=summary,
        signals=sig_responses,
    )


@router.get(
    "/{post_id}/ai-analysis",
    response_model=list[AIAnalysisResponse],
    summary="Get AI analyses associated with a specific post",
)
async def get_post_ai_analysis(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[AIAnalysisResponse]:
    post = await query_service.get_post(db, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post {post_id} not found",
        )
    analyses = await query_service.get_post_ai_analyses(db, post_id)
    return [AIAnalysisResponse.model_validate(a) for a in analyses]
