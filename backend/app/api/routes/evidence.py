import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.evidence.storage import evidence_storage
from app.models.evidence import Evidence

router = APIRouter(prefix="/evidence", tags=["Evidence"])


@router.get(
    "/{evidence_id}/file",
    summary="Download or view raw evidence screenshot/artifact",
)
async def get_evidence_file(
    evidence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    stmt = select(Evidence).where(Evidence.id == evidence_id)
    result = await db.execute(stmt)
    evidence = result.scalar_one_or_none()

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence {evidence_id} not found",
        )

    file_bytes = evidence_storage.get_file_bytes(evidence.storage_reference)
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file not found on disk storage",
        )

    content_type = (
        "image/png" if evidence.storage_reference.endswith(".png") else "application/octet-stream"
    )

    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={
            "X-Content-Hash": evidence.content_hash,
            "X-Evidence-Type": evidence.evidence_type,
        },
    )
