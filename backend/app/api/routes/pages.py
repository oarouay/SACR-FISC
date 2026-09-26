import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import ai_service
from app.core.config import settings
from app.db.session import get_db
from app.models.page_score import PageScore, ScoreReason
from app.models.post import Post
from app.models.signal import ExtractedSignal
from app.schemas.ai import AIAnalysisResponse, ReanalyzeResponse
from app.schemas.page import PageDetailResponse, PageResponse
from app.schemas.post import PostResponse
from app.schemas.registry import (
    RegistryVerificationResponse,
    RegistryVerificationUpdate,
)
from app.schemas.score import PageScoreResponse, ScoreReasonResponse
from app.schemas.signal import SignalResponse, SignalsSummaryResponse
from app.scoring.priority import priority_scorer
from app.services.query_service import query_service

router = APIRouter(prefix="/pages", tags=["Pages"])


@router.get(
    "",
    response_model=list[PageResponse],
    summary="List collected pages",
)
async def list_pages(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[PageResponse]:
    pages = await query_service.list_pages(db, limit=limit, offset=offset)
    return [PageResponse.model_validate(p) for p in pages]


@router.get(
    "/{page_id}",
    response_model=PageDetailResponse,
    summary="Get detailed page profile with post and signal statistics",
)
async def get_page(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PageDetailResponse:
    page = await query_service.get_page(db, page_id)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found",
        )

    # Post count
    post_count_stmt = select(func.count(Post.id)).where(Post.page_id == page_id)
    posts_count = (await db.execute(post_count_stmt)).scalar() or 0

    # Signal count and summary
    sig_stmt = (
        select(ExtractedSignal.signal_type, func.count(ExtractedSignal.id))
        .where(ExtractedSignal.page_id == page_id)
        .group_by(ExtractedSignal.signal_type)
    )
    sig_summary = {}
    total_signals = 0
    for row in (await db.execute(sig_stmt)).all():
        sig_summary[row[0]] = row[1]
        total_signals += row[1]

    data = PageResponse.model_validate(page).model_dump()
    data["posts_count"] = posts_count
    data["signals_count"] = total_signals
    data["signals_summary"] = sig_summary

    return PageDetailResponse(**data)


@router.get(
    "/{page_id}/posts",
    response_model=list[PostResponse],
    summary="Get collected posts for a page",
)
async def get_page_posts(
    page_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[PostResponse]:
    page = await query_service.get_page(db, page_id)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found",
        )
    posts = await query_service.get_page_posts(db, page_id, limit=limit, offset=offset)
    return [PostResponse.model_validate(p) for p in posts]


@router.get(
    "/{page_id}/signals",
    response_model=SignalsSummaryResponse,
    summary="Get all extracted commercial signals for a page and its posts",
)
async def get_page_signals(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SignalsSummaryResponse:
    page = await query_service.get_page(db, page_id)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found",
        )

    signals = await query_service.get_page_signals(db, page_id)
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
    "/{page_id}/scores",
    response_model=list[PageScoreResponse],
    summary="Get explainable commercial and review priority scores for a page",
)
async def get_page_scores(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[PageScoreResponse]:
    page = await query_service.get_page(db, page_id)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found",
        )

    scores = await query_service.get_page_scores(db, page_id)
    results = []
    for sc in scores:
        reasons_resp = [ScoreReasonResponse.model_validate(r) for r in sc.reasons]
        score_resp = PageScoreResponse(
            id=sc.id,
            page_id=sc.page_id,
            target_id=sc.target_id,
            quick_score=sc.quick_score,
            commercial_activity_score=sc.commercial_activity_score,
            transaction_evidence_score=sc.transaction_evidence_score,
            economic_activity_score=sc.economic_activity_score,
            review_priority_score=sc.review_priority_score,
            scoring_version=sc.scoring_version,
            calculated_at=sc.calculated_at,
            reasons=reasons_resp,
        )
        results.append(score_resp)
    return results


@router.patch(
    "/{page_id}/registry-verification",
    response_model=RegistryVerificationResponse,
    summary="Optionally record manual or external registry verification findings for a page",
)
async def update_page_registry_verification(
    page_id: uuid.UUID,
    payload: RegistryVerificationUpdate,
    db: AsyncSession = Depends(get_db),
) -> RegistryVerificationResponse:
    page = await query_service.get_page(db, page_id)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found",
        )

    reg_ver = await query_service.update_page_registry_verification(db, page_id, payload)
    return RegistryVerificationResponse.model_validate(reg_ver)


@router.get(
    "/{page_id}/ai-analysis",
    response_model=list[AIAnalysisResponse],
    summary="Get all AI semantic analyses for a page",
)
async def get_page_ai_analyses(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[AIAnalysisResponse]:
    page = await query_service.get_page(db, page_id)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found",
        )
    records = await query_service.get_page_ai_analyses(db, page_id)
    return [AIAnalysisResponse.model_validate(r) for r in records]


@router.post(
    "/{page_id}/reanalyze",
    response_model=ReanalyzeResponse,
    summary="Rerun AI analysis for development without re-crawling Facebook",
)
async def reanalyze_page(
    page_id: uuid.UUID,
    force: bool = Query(False, description="Bypass cache and force reanalysis"),
    db: AsyncSession = Depends(get_db),
) -> ReanalyzeResponse:
    page = await query_service.get_page(db, page_id)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found",
        )

    posts = await query_service.get_page_posts(db, page_id, limit=75)
    signals = await query_service.get_page_signals(db, page_id)

    if not posts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reanalyze page: no stored posts found",
        )

    price_count = len([s for s in signals if s.signal_type == "PRICE"])
    order_count = len([s for s in signals if s.signal_type == "ORDER_METHOD"])
    delivery_count = len([s for s in signals if s.signal_type == "DELIVERY"])
    payment_count = len([s for s in signals if s.signal_type == "PAYMENT"])
    promo_count = len([s for s in signals if s.signal_type == "COMMERCIAL_KEYWORD"])

    summary = {
        "total_posts": len(posts),
        "price_count": price_count,
        "order_count": order_count,
        "delivery_count": delivery_count,
        "payment_count": payment_count,
        "promo_count": promo_count,
    }

    rep_posts = [
        {"post_id": str(p.platform_post_id or p.id), "text": p.text or ""}
        for p in posts
        if p.text and len(p.text.strip()) > 15
    ][:10]

    ai_analysis, was_cached = await ai_service.analyze_page(
        db=db,
        page_id=page.id,
        page_name=page.name or "",
        page_description=page.description,
        page_category=page.category,
        deterministic_summary=summary,
        representative_posts=rep_posts,
    )

    if not ai_analysis:
        return ReanalyzeResponse(
            page_id=page_id,
            status="FAILED",
            analysis_type="PAGE_ANALYSIS",
            message="L’analyse automatisée a échoué ou a été désactivée.",
            output=None,
        )

    # Recompute priority score with new AI findings
    deep_result = priority_scorer.calculate(
        page=page,
        posts=posts,
        signals=signals,
        ai_analysis=ai_analysis,
    )

    score_rec = PageScore(
        page_id=page.id,
        commercial_activity_score=deep_result.commercial_activity.score,
        transaction_evidence_score=deep_result.transaction_evidence.score,
        economic_activity_score=deep_result.economic_activity.score,
        review_priority_score=deep_result.review_priority,
        scoring_version=settings.SCORING_VERSION,
    )
    db.add(score_rec)
    await db.flush()

    for expl in deep_result.all_explanations:
        db.add(
            ScoreReason(
                page_score_id=score_rec.id,
                component=expl.component,
                reason=expl.reason,
                weight_or_value=expl.weight,
                evidence_reference=expl.evidence_reference,
                source=expl.source,
                evidence_post_ids=expl.evidence_post_ids,
            )
        )
    await db.commit()

    return ReanalyzeResponse(
        page_id=page_id,
        status="SUCCESS",
        analysis_type="PAGE_ANALYSIS",
        message=f"Reanalysis complete ({'cached' if was_cached else 'executed'}). Review priority: {deep_result.review_priority}",
        output=ai_analysis.model_dump(),
    )
