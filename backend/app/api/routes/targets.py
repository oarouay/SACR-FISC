import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.ingestion.service import target_ingestion_service
from app.ingestion.sources import CsvTargetSource, ManualTargetSource
from app.models.enums import CrawlMode, TargetStatus
from app.schemas.target import (
    TargetCreate,
    TargetImportResponse,
    TargetResponse,
)
from app.services.query_service import query_service

router = APIRouter(prefix="/targets", tags=["Target Queue"])


@router.post(
    "",
    response_model=TargetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enqueue a new candidate Facebook Page target",
)
async def create_target(
    payload: TargetCreate,
    db: AsyncSession = Depends(get_db),
) -> TargetResponse:
    source = ManualTargetSource(url=payload.url, priority=payload.priority)
    result = await target_ingestion_service.ingest_from_source(db, source)

    if not result["targets"]:
        # If skipped because already existing, return existing target
        from app.ingestion.normalizer import normalize_facebook_url

        canonical = normalize_facebook_url(payload.url)
        from sqlalchemy import select

        from app.models.crawl_target import CrawlTarget

        stmt = select(CrawlTarget).where(CrawlTarget.canonical_url == canonical)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            return TargetResponse.model_validate(existing)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid target URL: {payload.url}",
        )

    return TargetResponse.model_validate(result["targets"][0])


@router.post(
    "/import-csv",
    response_model=TargetImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk import candidate Facebook Page URLs via CSV",
)
async def import_targets_csv(
    file: UploadFile | None = File(None),
    csv_content: str | None = Form(None),
    priority: int = Form(0),
    db: AsyncSession = Depends(get_db),
) -> TargetImportResponse:
    content: str = ""
    if file:
        raw_bytes = await file.read()
        content = raw_bytes.decode("utf-8", errors="replace")
    elif csv_content:
        content = csv_content
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either a CSV file or csv_content string must be provided.",
        )

    source = CsvTargetSource(content=content, default_priority=priority)
    result = await target_ingestion_service.ingest_from_source(db, source)

    return TargetImportResponse(
        total_submitted=result["total_submitted"],
        created_count=result["created_count"],
        duplicates_skipped=result["duplicates_skipped"],
        targets=[TargetResponse.model_validate(t) for t in result["targets"]],
    )


@router.get(
    "",
    response_model=list[TargetResponse],
    summary="List targets in the crawl queue with optional status and mode filters",
)
async def list_targets(
    status: TargetStatus | None = Query(None, description="Filter by target queue status"),
    crawl_mode: CrawlMode | None = Query(None, description="Filter by crawl mode (QUICK or DEEP)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[TargetResponse]:
    targets = await query_service.list_targets(
        db=db,
        status=status,
        crawl_mode=crawl_mode,
        limit=limit,
        offset=offset,
    )
    return [TargetResponse.model_validate(t) for t in targets]


@router.get(
    "/{target_id}",
    response_model=TargetResponse,
    summary="Get details and current status of a crawl target",
)
async def get_target(
    target_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TargetResponse:
    target = await query_service.get_target(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crawl target {target_id} not found",
        )
    return TargetResponse.model_validate(target)
