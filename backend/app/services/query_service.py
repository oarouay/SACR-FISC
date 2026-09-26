import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.service import ai_service
from app.core.config import settings
from app.models.ai_analysis import AIAnalysis
from app.models.crawl_job import CrawlJob
from app.models.crawl_target import CrawlTarget
from app.models.enums import CrawlMode, RegistryStatus, TargetStatus
from app.models.evidence import Evidence
from app.models.page import Page
from app.models.page_score import PageScore
from app.models.post import Post
from app.models.registry_verification import RegistryVerification
from app.models.signal import ExtractedSignal
from app.schemas.registry import RegistryVerificationUpdate
from app.schemas.score import ReviewQueueItemResponse, ReviewReasonItem


class QueryService:
    @staticmethod
    async def get_crawl_job(db: AsyncSession, job_id: uuid.UUID) -> CrawlJob | None:
        stmt = select(CrawlJob).where(CrawlJob.id == job_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_crawl_job_details(db: AsyncSession, job_id: uuid.UUID) -> dict[str, Any] | None:
        stmt = select(CrawlJob).where(CrawlJob.id == job_id)
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            return None

        evidence_stmt = select(func.count(Evidence.id)).where(Evidence.crawl_job_id == job_id)
        ev_count = (await db.execute(evidence_stmt)).scalar() or 0

        page_stmt = select(Page).where(Page.canonical_url == job.target_url)
        page = (await db.execute(page_stmt)).scalar_one_or_none()

        signals_summary: dict[str, int] = {}
        if page:
            sig_stmt = (
                select(ExtractedSignal.signal_type, func.count(ExtractedSignal.id))
                .where(ExtractedSignal.page_id == page.id)
                .group_by(ExtractedSignal.signal_type)
            )
            for row in (await db.execute(sig_stmt)).all():
                signals_summary[row[0]] = row[1]

        return {
            "id": job.id,
            "target_url": job.target_url,
            "platform": job.platform,
            "status": job.status,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "max_posts": job.max_posts,
            "max_scroll_cycles": job.max_scroll_cycles,
            "posts_collected": job.posts_collected,
            "error_code": job.error_code,
            "error_message": job.error_message,
            "collector_version": job.collector_version,
            "created_at": job.created_at,
            "page_id": page.id if page else None,
            "page_name": page.name if page else None,
            "evidence_count": ev_count,
            "signals_summary": signals_summary,
        }

    @staticmethod
    async def list_targets(
        db: AsyncSession,
        status: TargetStatus | None = None,
        crawl_mode: CrawlMode | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CrawlTarget]:
        stmt = select(CrawlTarget)
        if status:
            stmt = stmt.where(CrawlTarget.status == status)
        if crawl_mode:
            stmt = stmt.where(CrawlTarget.crawl_mode == crawl_mode)
        stmt = stmt.order_by(CrawlTarget.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_target(db: AsyncSession, target_id: uuid.UUID) -> CrawlTarget | None:
        stmt = select(CrawlTarget).where(CrawlTarget.id == target_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_pages(db: AsyncSession, limit: int = 50, offset: int = 0) -> list[Page]:
        stmt = select(Page).order_by(Page.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_page(db: AsyncSession, page_id: uuid.UUID) -> Page | None:
        stmt = select(Page).where(Page.id == page_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_page_posts(
        db: AsyncSession, page_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[Post]:
        stmt = (
            select(Post)
            .where(Post.page_id == page_id)
            .order_by(Post.first_seen_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_page_signals(db: AsyncSession, page_id: uuid.UUID) -> list[ExtractedSignal]:
        stmt = (
            select(ExtractedSignal)
            .where(ExtractedSignal.page_id == page_id)
            .order_by(ExtractedSignal.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_page_scores(db: AsyncSession, page_id: uuid.UUID) -> list[PageScore]:
        stmt = (
            select(PageScore)
            .where(PageScore.page_id == page_id)
            .options(selectinload(PageScore.reasons))
            .order_by(PageScore.calculated_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_review_queue(
        db: AsyncSession,
        min_priority: float | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReviewQueueItemResponse]:
        threshold = min_priority if min_priority is not None else settings.REVIEW_THRESHOLD

        # Query latest score per page where review_priority_score >= threshold
        stmt = (
            select(PageScore)
            .where(PageScore.review_priority_score >= threshold)
            .options(selectinload(PageScore.page), selectinload(PageScore.reasons))
            .order_by(PageScore.review_priority_score.desc())
            .limit(limit)
            .offset(offset)
        )
        scores = (await db.execute(stmt)).scalars().all()

        items: list[ReviewQueueItemResponse] = []
        for s in scores:
            if not s.page:
                continue

            # Check registry verification status for this page
            reg_stmt = select(RegistryVerification).where(RegistryVerification.page_id == s.page_id)
            reg_ver = (await db.execute(reg_stmt)).scalar_one_or_none()
            reg_status = reg_ver.status.value if reg_ver else RegistryStatus.NOT_CHECKED.value

            # Check latest AI analysis for this page
            ai_stmt = (
                select(AIAnalysis)
                .where(AIAnalysis.page_id == s.page_id, AIAnalysis.status == "SUCCESS")
                .order_by(AIAnalysis.created_at.desc())
                .limit(1)
            )
            ai_rec = (await db.execute(ai_stmt)).scalar_one_or_none()
            ai_sum = None
            if ai_rec and isinstance(ai_rec.output_json, dict):
                ai_sum = {
                    "provider": ai_rec.provider,
                    "commercial_confidence": ai_rec.confidence,
                    "business_type": ai_rec.output_json.get("business_type"),
                    "recurring_activity": ai_rec.output_json.get("recurring_activity", False),
                }

            structured_reasons = [
                ReviewReasonItem(
                    reason=r.reason,
                    source=getattr(r, "source", "DETERMINISTIC") or "DETERMINISTIC",
                    evidence_post_ids=getattr(r, "evidence_post_ids", []) or [],
                )
                for r in s.reasons
            ]

            items.append(
                ReviewQueueItemResponse(
                    page_id=s.page_id,
                    page_name=s.page.name,
                    canonical_url=s.page.canonical_url,
                    review_priority=s.review_priority_score,
                    commercial_activity=s.commercial_activity_score,
                    transaction_evidence=s.transaction_evidence_score,
                    economic_activity=s.economic_activity_score,
                    registry_status=reg_status,
                    ai_summary=ai_sum,
                    reasons=[r.reason for r in s.reasons],
                    structured_reasons=structured_reasons,
                    calculated_at=s.calculated_at,
                )
            )

        return items

    @staticmethod
    async def update_page_registry_verification(
        db: AsyncSession,
        page_id: uuid.UUID,
        payload: RegistryVerificationUpdate,
    ) -> RegistryVerification:
        stmt = select(RegistryVerification).where(RegistryVerification.page_id == page_id)
        reg_ver = (await db.execute(stmt)).scalar_one_or_none()

        now = datetime.now(UTC)
        if not reg_ver:
            reg_ver = RegistryVerification(
                page_id=page_id,
                status=payload.status,
                source=payload.source,
                external_reference=payload.external_reference,
                verified_by=payload.verified_by,
                verified_at=now,
                notes=payload.notes,
            )
            db.add(reg_ver)
        else:
            reg_ver.status = payload.status
            reg_ver.source = payload.source
            reg_ver.external_reference = payload.external_reference
            reg_ver.verified_by = payload.verified_by
            reg_ver.verified_at = now
            reg_ver.notes = payload.notes
            reg_ver.updated_at = now

        await db.commit()
        await db.refresh(reg_ver)
        return reg_ver

    @staticmethod
    async def get_metrics_summary(db: AsyncSession) -> dict[str, Any]:
        # Target counts by status
        target_counts = dict(
            (
                await db.execute(
                    select(CrawlTarget.status, func.count(CrawlTarget.id)).group_by(
                        CrawlTarget.status
                    )
                )
            ).all()
        )

        total_targets = sum(target_counts.values())

        # Quick vs Deep crawls
        mode_counts = dict(
            (
                await db.execute(
                    select(CrawlJob.crawl_mode, func.count(CrawlJob.id)).group_by(
                        CrawlJob.crawl_mode
                    )
                )
            ).all()
        )

        promoted_count = (
            await db.execute(
                select(func.count(CrawlTarget.id)).where(
                    CrawlTarget.crawl_mode == CrawlMode.DEEP,
                    CrawlTarget.quick_score.is_not(None),
                )
            )
        ).scalar() or 0

        # Totals
        total_pages = (await db.execute(select(func.count(Page.id)))).scalar() or 0
        total_posts = (await db.execute(select(func.count(Post.id)))).scalar() or 0
        total_signals = (await db.execute(select(func.count(ExtractedSignal.id)))).scalar() or 0
        total_evidence = (await db.execute(select(func.count(Evidence.id)))).scalar() or 0

        # Review queue stats
        review_pages = (
            await db.execute(
                select(func.count(PageScore.id)).where(
                    PageScore.review_priority_score >= settings.REVIEW_THRESHOLD
                )
            )
        ).scalar() or 0

        avg_priority = (
            await db.execute(select(func.avg(PageScore.review_priority_score)))
        ).scalar() or 0.0

        # AI & Gemini Metrics
        gemini_calls = (await db.execute(select(func.count(AIAnalysis.id)))).scalar() or 0
        successful_calls = (
            await db.execute(
                select(func.count(AIAnalysis.id)).where(AIAnalysis.status == "SUCCESS")
            )
        ).scalar() or 0
        failed_calls = (
            await db.execute(select(func.count(AIAnalysis.id)).where(AIAnalysis.status == "FAILED"))
        ).scalar() or 0
        cached_responses = ai_service.metrics.get("cached_responses", 0)
        avg_latency = (
            await db.execute(
                select(func.avg(AIAnalysis.latency_ms)).where(AIAnalysis.status == "SUCCESS")
            )
        ).scalar() or 0.0
        pages_analyzed = (
            await db.execute(
                select(func.count(func.distinct(AIAnalysis.page_id))).where(
                    AIAnalysis.status == "SUCCESS"
                )
            )
        ).scalar() or 0
        ambiguity_cases = (
            await db.execute(
                select(func.count(AIAnalysis.id)).where(
                    AIAnalysis.analysis_type == "AMBIGUITY_RESOLUTION"
                )
            )
        ).scalar() or 0

        return {
            "targets_pending": target_counts.get(TargetStatus.PENDING, 0),
            "targets_claimed": target_counts.get(TargetStatus.CLAIMED, 0),
            "targets_crawling": target_counts.get(TargetStatus.CRAWLING, 0),
            "targets_completed": target_counts.get(TargetStatus.COMPLETED, 0),
            "targets_blocked": target_counts.get(TargetStatus.BLOCKED, 0),
            "targets_failed": target_counts.get(TargetStatus.FAILED, 0),
            "targets_retry": target_counts.get(TargetStatus.RETRY, 0),
            "targets_manual_review": target_counts.get(TargetStatus.MANUAL_REVIEW, 0),
            "total_targets": total_targets,
            "quick_crawls": mode_counts.get(CrawlMode.QUICK.value, 0)
            + mode_counts.get(CrawlMode.QUICK, 0),
            "deep_crawls": mode_counts.get(CrawlMode.DEEP.value, 0)
            + mode_counts.get(CrawlMode.DEEP, 0),
            "pages_promoted_quick_to_deep": promoted_count,
            "total_pages_stored": total_pages,
            "total_posts_collected": total_posts,
            "total_signals_extracted": total_signals,
            "total_evidence_stored": total_evidence,
            "pages_in_review_queue": review_pages,
            "average_review_priority": round(float(avg_priority), 1),
            "gemini_calls": gemini_calls,
            "successful_calls": successful_calls,
            "failed_calls": failed_calls,
            "cached_responses": cached_responses,
            "average_latency_ms": round(float(avg_latency), 1),
            "posts_analyzed": ai_service.metrics.get("posts_analyzed", 0),
            "pages_analyzed": pages_analyzed,
            "ambiguity_cases_resolved": ambiguity_cases,
        }

    @staticmethod
    async def get_page_ai_analyses(db: AsyncSession, page_id: uuid.UUID) -> list[AIAnalysis]:
        stmt = (
            select(AIAnalysis)
            .where(AIAnalysis.page_id == page_id)
            .order_by(AIAnalysis.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_post_ai_analyses(db: AsyncSession, post_id: uuid.UUID) -> list[AIAnalysis]:
        stmt = (
            select(AIAnalysis)
            .where(AIAnalysis.post_id == post_id)
            .order_by(AIAnalysis.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_post(db: AsyncSession, post_id: uuid.UUID) -> Post | None:
        stmt = select(Post).where(Post.id == post_id).options(selectinload(Post.signals))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_post_signals(db: AsyncSession, post_id: uuid.UUID) -> list[ExtractedSignal]:
        stmt = (
            select(ExtractedSignal)
            .where(ExtractedSignal.post_id == post_id)
            .order_by(ExtractedSignal.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_job_evidence(db: AsyncSession, job_id: uuid.UUID) -> list[Evidence]:
        stmt = (
            select(Evidence)
            .where(Evidence.crawl_job_id == job_id)
            .order_by(Evidence.captured_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


query_service = QueryService()
