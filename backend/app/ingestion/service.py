from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.ingestion.sources import TargetSource
from app.models.crawl_target import CrawlTarget
from app.models.enums import CrawlMode, TargetStatus


class TargetIngestionService:
    @staticmethod
    async def ingest_from_source(
        db: AsyncSession,
        source: TargetSource,
    ) -> dict[str, Any]:
        candidates = source.extract_targets()
        if not candidates:
            return {
                "total_submitted": 0,
                "created_count": 0,
                "duplicates_skipped": 0,
                "targets": [],
            }

        # Deduplicate within batch first
        unique_by_canonical: dict[str, tuple[str, int]] = {}
        for c in candidates:
            if c.canonical_url not in unique_by_canonical:
                unique_by_canonical[c.canonical_url] = (c.raw_url, c.priority)

        canonical_urls = list(unique_by_canonical.keys())

        # Check existing in database
        stmt = select(CrawlTarget).where(CrawlTarget.canonical_url.in_(canonical_urls))
        result = await db.execute(stmt)
        existing_targets = {t.canonical_url: t for t in result.scalars().all()}

        created_targets: list[CrawlTarget] = []
        batch_duplicates = len(candidates) - len(unique_by_canonical)
        duplicates_skipped = batch_duplicates

        for canonical_url, (raw_url, priority) in unique_by_canonical.items():
            if canonical_url in existing_targets:
                duplicates_skipped += 1
                logger.debug(f"Target already queued: {canonical_url}")
                continue

            target = CrawlTarget(
                url=raw_url,
                canonical_url=canonical_url,
                platform="facebook",
                status=TargetStatus.PENDING,
                priority=priority,
                crawl_mode=CrawlMode.QUICK,
            )
            db.add(target)
            created_targets.append(target)

        await db.commit()
        for t in created_targets:
            await db.refresh(t)

        logger.info(
            f"Ingested {len(created_targets)} new crawl targets ({duplicates_skipped} duplicates skipped)"
        )

        return {
            "total_submitted": len(candidates),
            "created_count": len(created_targets),
            "duplicates_skipped": duplicates_skipped,
            "targets": created_targets,
        }


target_ingestion_service = TargetIngestionService()
