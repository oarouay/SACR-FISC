import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.ingestion.normalizer import UrlNormalizer
from app.models.crawl_target import CrawlTarget
from app.models.enums import CrawlMode, TargetStatus
from app.schemas.crawl_job import (
    CrawlJobCreate,
    CrawlJobCreateResponse,
    CrawlJobDetailResponse,
)
from app.schemas.evidence import EvidenceResponse
from app.services.crawl_service import crawl_service
from app.services.query_service import query_service

router = APIRouter(prefix="/crawl-jobs", tags=["Crawl Jobs"])


@router.post(
    "",
    response_model=CrawlJobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a new crawl job for a controlled Facebook Page",
)
async def create_crawl_job(
    payload: CrawlJobCreate,
    db: AsyncSession = Depends(get_db),
) -> CrawlJobCreateResponse:
    canonical = UrlNormalizer.normalize(payload.url)
    target_res = await db.execute(select(CrawlTarget).where(CrawlTarget.canonical_url == canonical))
    target = target_res.scalar_one_or_none()
    if not target:
        target = CrawlTarget(
            url=payload.url,
            canonical_url=canonical,
            platform="facebook",
            status=TargetStatus.PENDING,
            crawl_mode=CrawlMode.QUICK,
        )
        db.add(target)
        await db.commit()
        await db.refresh(target)

    job = await crawl_service.create_job(
        db=db,
        target_url=canonical,
        target_id=target.id,
        max_posts=payload.max_posts,
        max_scroll_cycles=payload.max_scroll_cycles,
    )

    return CrawlJobCreateResponse(
        job_id=job.id,
        status=job.status,
        message="Crawl job accepted and queued for execution by crawler worker.",
    )


@router.get(
    "/{job_id}",
    response_model=CrawlJobDetailResponse,
    summary="Check status and details of a crawl job",
)
async def get_crawl_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CrawlJobDetailResponse:
    details = await query_service.get_crawl_job_details(db, job_id)
    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crawl job {job_id} not found",
        )
    return CrawlJobDetailResponse(**details)


@router.get(
    "/{job_id}/evidence",
    response_model=list[EvidenceResponse],
    summary="List evidence artifacts captured during a crawl job",
)
async def get_crawl_job_evidence(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[EvidenceResponse]:
    evidence = await query_service.get_job_evidence(db, job_id)
    return [EvidenceResponse.model_validate(e) for e in evidence]
