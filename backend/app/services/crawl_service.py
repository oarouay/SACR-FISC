import uuid
from datetime import UTC, datetime

from playwright.async_api import Browser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import ai_service
from app.collectors.base import CrawlResult
from app.collectors.facebook.collector import FacebookPageCollector
from app.core.config import settings
from app.core.logging import logger
from app.db import session as db_session_module
from app.evidence.storage import evidence_storage
from app.extraction.pipeline import signal_pipeline
from app.models.crawl_job import CrawlErrorCode, CrawlJob, CrawlStatus
from app.models.crawl_target import CrawlTarget
from app.models.enums import CrawlMode, RegistryStatus, TargetStatus
from app.models.evidence import Evidence
from app.models.page import Page
from app.models.page_score import PageScore, ScoreReason
from app.models.post import Post
from app.models.registry_verification import RegistryVerification
from app.models.signal import ExtractedSignal
from app.queue.target_queue import target_queue
from app.scoring.models import ScoreExplanation
from app.scoring.priority import priority_scorer
from app.scoring.quick import quick_scorer

AsyncSessionLocal = db_session_module.AsyncSessionLocal


class CrawlService:
    @staticmethod
    async def create_job(
        db: AsyncSession,
        target_url: str,
        max_posts: int | None = None,
        max_scroll_cycles: int | None = None,
        target_id: uuid.UUID | None = None,
        crawl_mode: CrawlMode = CrawlMode.QUICK,
    ) -> CrawlJob:
        if max_posts is None:
            max_posts = (
                settings.QUICK_POST_LIMIT
                if crawl_mode == CrawlMode.QUICK
                else settings.DEEP_POST_LIMIT
            )
        if max_scroll_cycles is None:
            max_scroll_cycles = (
                settings.QUICK_MAX_SCROLL_CYCLES
                if crawl_mode == CrawlMode.QUICK
                else settings.DEEP_MAX_SCROLL_CYCLES
            )

        job = CrawlJob(
            target_id=target_id,
            target_url=target_url.strip(),
            platform="facebook",
            crawl_mode=crawl_mode,
            status=CrawlStatus.PENDING,
            max_posts=max_posts,
            max_scroll_cycles=max_scroll_cycles,
            collector_version=settings.COLLECTOR_VERSION,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        logger.info(f"Created crawl job {job.id} for {target_url} (mode={crawl_mode})")
        return job

    @classmethod
    async def process_target(
        cls,
        target: CrawlTarget,
        browser: Browser | None = None,
        job_id: uuid.UUID | None = None,
    ) -> CrawlResult:
        """
        Executes a crawl against a claimed CrawlTarget, handles Page/Post/Evidence persistence,
        runs appropriate scoring (Quick vs. Deep), and transitions the target state.
        """
        async with AsyncSessionLocal() as session:
            # 1. Fetch or create a CrawlJob tracking this execution
            job = None
            if job_id:
                job_res = await session.execute(select(CrawlJob).where(CrawlJob.id == job_id))
                job = job_res.scalar_one_or_none()

            if not job:
                job = await cls.create_job(
                    db=session,
                    target_url=target.canonical_url,
                    target_id=target.id,
                    crawl_mode=target.crawl_mode,
                )

            job.status = CrawlStatus.RUNNING
            job.started_at = datetime.now(UTC)
            await session.commit()

            # 2. Run Collector
            collector = FacebookPageCollector(
                page_timeout=settings.CRAWL_DEFAULT_PAGE_TIMEOUT,
                headless=settings.PLAYWRIGHT_HEADLESS,
                browser=browser,
            )
            crawl_result: CrawlResult = await collector.run(
                job_id=job.id,
                target_url=target.canonical_url,
                max_posts=job.max_posts,
                max_scroll_cycles=job.max_scroll_cycles,
                crawl_mode=target.crawl_mode.value,
            )

            # 3. Handle Blocking / Failure Cases
            if crawl_result.status == CrawlStatus.FAILED:
                job.status = CrawlStatus.FAILED
                job.finished_at = datetime.now(UTC)
                job.error_code = crawl_result.error_code
                job.error_message = crawl_result.error_message
                await session.commit()

                # Dispatch structured retry / blocked / failure state to TargetQueue
                code = crawl_result.error_code or ""
                msg = crawl_result.error_message or "Unknown failure"
                if code in (
                    CrawlErrorCode.CAPTCHA.value,
                    CrawlErrorCode.LOGIN_REQUIRED.value,
                    CrawlErrorCode.ACCESS_RESTRICTED.value,
                ):
                    await target_queue.mark_blocked(session, target.id, reason=f"{code}: {msg}")
                elif code == CrawlErrorCode.LAYOUT_UNKNOWN.value:
                    await target_queue.mark_manual_review(
                        session, target.id, reason=f"{code}: {msg}"
                    )
                elif code in (
                    CrawlErrorCode.PAGE_NOT_FOUND.value,
                    CrawlErrorCode.INVALID_URL.value,
                ):
                    await target_queue.mark_failed(session, target.id, reason=f"{code}: {msg}")
                else:
                    await target_queue.schedule_retry(
                        session, target.id, error_code=code, error_message=msg
                    )

                return crawl_result

            # 4. Handle Page Persistence (Upsert)
            page_record: Page | None = None
            if crawl_result.page_metadata:
                pm = crawl_result.page_metadata
                page_res = await session.execute(
                    select(Page).where(Page.canonical_url == pm.canonical_url)
                )
                page_record = page_res.scalar_one_or_none()
                now = datetime.now(UTC)

                if page_record:
                    page_record.last_seen_at = now
                    page_record.updated_at = now
                    if pm.name:
                        page_record.name = pm.name
                    if pm.description:
                        page_record.description = pm.description
                    if pm.public_phone:
                        page_record.public_phone = pm.public_phone
                    if pm.public_email:
                        page_record.public_email = pm.public_email
                    if pm.website:
                        page_record.website = pm.website
                    if pm.public_address:
                        page_record.public_address = pm.public_address
                else:
                    page_record = Page(
                        canonical_url=pm.canonical_url,
                        name=pm.name,
                        platform_page_id=pm.platform_page_id,
                        description=pm.description,
                        category=pm.category,
                        public_phone=pm.public_phone,
                        public_email=pm.public_email,
                        website=pm.website,
                        public_address=pm.public_address,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                    session.add(page_record)
                    await session.flush()

                    # Section 1 & 21: Default registry status is strictly NOT_CHECKED
                    reg_ver = RegistryVerification(
                        page_id=page_record.id,
                        status=RegistryStatus.NOT_CHECKED,
                        notes="Registry verification not performed; strictly decoupled from crawler.",
                    )
                    session.add(reg_ver)

                await session.flush()

                # Extract signals from description
                if page_record.description:
                    page_signals = signal_pipeline.create_signal_models(
                        text=page_record.description,
                        page_id=page_record.id,
                        post_id=None,
                    )
                    for sig in page_signals:
                        session.add(sig)

            # 5. Handle Post Persistence & Signal Extraction
            created_posts_map: dict[int, uuid.UUID] = {}
            for idx, raw_post in enumerate(crawl_result.posts):
                if not page_record:
                    break

                post_query = select(Post).where(
                    Post.page_id == page_record.id,
                    (Post.platform_post_id == raw_post.platform_post_id)
                    | (Post.content_hash == raw_post.content_hash),
                )
                existing_post = (await session.execute(post_query)).scalar_one_or_none()
                now = datetime.now(UTC)

                if existing_post:
                    existing_post.last_seen_at = now
                    post_id = existing_post.id
                else:
                    new_post = Post(
                        page_id=page_record.id,
                        platform_post_id=raw_post.platform_post_id,
                        permalink=raw_post.permalink,
                        text=raw_post.text,
                        published_at=raw_post.published_at,
                        first_seen_at=now,
                        last_seen_at=now,
                        raw_data=raw_post.raw_data,
                        content_hash=raw_post.content_hash,
                    )
                    session.add(new_post)
                    await session.flush()
                    post_id = new_post.id

                    if raw_post.text:
                        signals = signal_pipeline.create_signal_models(
                            text=raw_post.text,
                            page_id=page_record.id,
                            post_id=post_id,
                        )
                        for sig in signals:
                            session.add(sig)

                created_posts_map[idx] = post_id

            # 6. Store Evidence Artifacts
            for item in crawl_result.evidence_items:
                storage_ref, content_hash = evidence_storage.store_file(
                    data=item.data,
                    filename_prefix=item.filename_prefix,
                    extension=item.extension,
                )
                linked_post_id = (
                    created_posts_map.get(item.post_index) if item.post_index is not None else None
                )
                evidence_entry = Evidence(
                    crawl_job_id=job.id,
                    page_id=page_record.id if page_record else None,
                    post_id=linked_post_id,
                    evidence_type=item.evidence_type,
                    storage_reference=storage_ref,
                    content_hash=content_hash,
                    evidence_metadata=item.metadata,
                )
                session.add(evidence_entry)

            # 7. Finalize CrawlJob record
            job.status = crawl_result.status
            job.posts_collected = crawl_result.posts_collected
            job.finished_at = datetime.now(UTC)
            job.error_code = crawl_result.error_code
            job.error_message = crawl_result.error_message
            await session.commit()

            # 8. Scoring & Autonomous Pipeline Decisions
            if page_record:
                # Load all posts and signals for this page
                all_posts_res = await session.execute(
                    select(Post).where(Post.page_id == page_record.id)
                )
                all_posts = list(all_posts_res.scalars().all())

                all_sigs_res = await session.execute(
                    select(ExtractedSignal).where(ExtractedSignal.page_id == page_record.id)
                )
                all_signals = list(all_sigs_res.scalars().all())

                if target.crawl_mode == CrawlMode.QUICK:
                    # Calculate Quick Commercial Score deterministically
                    quick_result = quick_scorer.calculate(page_record, all_posts, all_signals)
                    q_score = quick_result.score
                    ai_ambiguity_reasons: list[ScoreExplanation] = []

                    # Ambiguity Resolution Gating (Section 2 & 5)
                    # If quick_score < QUICK_LOW_THRESHOLD: low relevance, no Gemini call
                    # If QUICK_LOW_THRESHOLD <= quick_score < QUICK_DEEP_THRESHOLD: send sample to Gemini
                    # If quick_score >= QUICK_DEEP_THRESHOLD: strong commercial candidate, promote directly
                    if settings.QUICK_LOW_THRESHOLD <= q_score < settings.QUICK_DEEP_THRESHOLD:
                        posts_payload = [
                            {"post_id": str(p.platform_post_id or p.id), "text": p.text or ""}
                            for p in all_posts
                        ]
                        ambiguity_analysis, was_cached = await ai_service.resolve_ambiguity(
                            db=session,
                            page_id=page_record.id,
                            page_name=page_record.name or "",
                            page_description=page_record.description,
                            page_category=page_record.category,
                            posts=posts_payload,
                        )
                        if (
                            ambiguity_analysis
                            and ambiguity_analysis.is_commercial
                            and ambiguity_analysis.confidence >= 0.85
                            and len(ambiguity_analysis.evidence_post_ids) >= 1
                        ):
                            boost = 25.0
                            q_score = min(q_score + boost, 85.0)
                            ai_ambiguity_reasons.append(
                                ScoreExplanation(
                                    component="AI_AMBIGUITY_RESOLUTION",
                                    reason=(
                                        f"L’analyse automatisée a résolu un profil commercial ambigu ({ambiguity_analysis.activity_type}) "
                                        f"avec un niveau de confiance de {ambiguity_analysis.confidence:.2f}"
                                    ),
                                    weight=boost,
                                    source="GEMINI",
                                    evidence_post_ids=ambiguity_analysis.evidence_post_ids,
                                )
                            )
                        elif ambiguity_analysis:
                            ai_ambiguity_reasons.append(
                                ScoreExplanation(
                                    component="AI_AMBIGUITY_RESOLUTION",
                                    reason="La résolution automatisée a évalué le contenu comme non commercial ou insuffisamment fiable",
                                    weight=0.0,
                                    source="GEMINI",
                                )
                            )

                    # Save quick score record
                    score_rec = PageScore(
                        page_id=page_record.id,
                        target_id=target.id,
                        quick_score=q_score,
                        commercial_activity_score=q_score,
                        transaction_evidence_score=0.0,
                        economic_activity_score=0.0,
                        review_priority_score=q_score,
                        scoring_version=settings.SCORING_VERSION,
                    )
                    session.add(score_rec)
                    await session.flush()

                    for expl in quick_result.reasons + ai_ambiguity_reasons:
                        session.add(
                            ScoreReason(
                                page_score_id=score_rec.id,
                                component=expl.component,
                                reason=expl.reason,
                                weight_or_value=expl.weight,
                                source=expl.source,
                                evidence_post_ids=expl.evidence_post_ids,
                            )
                        )
                    await session.commit()

                    # Decide promotion to DEEP or mark COMPLETED
                    if q_score >= settings.QUICK_DEEP_THRESHOLD:
                        await target_queue.promote_to_deep(session, target.id, quick_score=q_score)
                    else:
                        await target_queue.mark_completed(
                            session, target.id, quick_score=q_score, final_score=q_score
                        )

                elif target.crawl_mode == CrawlMode.DEEP:
                    # 1. Deterministic signals summary
                    price_count = len([s for s in all_signals if s.signal_type == "PRICE"])
                    order_count = len([s for s in all_signals if s.signal_type == "ORDER_METHOD"])
                    delivery_count = len([s for s in all_signals if s.signal_type == "DELIVERY"])
                    payment_count = len([s for s in all_signals if s.signal_type == "PAYMENT"])
                    promo_count = len(
                        [s for s in all_signals if s.signal_type == "COMMERCIAL_KEYWORD"]
                    )

                    summary = {
                        "total_posts": len(all_posts),
                        "price_count": price_count,
                        "order_count": order_count,
                        "delivery_count": delivery_count,
                        "payment_count": payment_count,
                        "promo_count": promo_count,
                    }

                    # Representative posts (posts with signals or text)
                    rep_posts = [
                        {"post_id": str(p.platform_post_id or p.id), "text": p.text or ""}
                        for p in all_posts
                        if p.text and len(p.text.strip()) > 15
                    ][:10]

                    # Run Page-Level Gemini Synthesis
                    ai_page_analysis, _ = await ai_service.analyze_page(
                        db=session,
                        page_id=page_record.id,
                        page_name=page_record.name or "",
                        page_description=page_record.description,
                        page_category=page_record.category,
                        deterministic_summary=summary,
                        representative_posts=rep_posts,
                    )

                    # Calculate Deep Review Priority Score (enriched by Gemini if available)
                    deep_result = priority_scorer.calculate(
                        page=page_record,
                        posts=all_posts,
                        signals=all_signals,
                        ai_analysis=ai_page_analysis,
                    )

                    score_rec = PageScore(
                        page_id=page_record.id,
                        target_id=target.id,
                        quick_score=target.quick_score,
                        commercial_activity_score=deep_result.commercial_activity.score,
                        transaction_evidence_score=deep_result.transaction_evidence.score,
                        economic_activity_score=deep_result.economic_activity.score,
                        review_priority_score=deep_result.review_priority,
                        scoring_version=settings.SCORING_VERSION,
                    )
                    session.add(score_rec)
                    await session.flush()

                    for expl in deep_result.all_explanations:
                        session.add(
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
                    await session.commit()

                    await target_queue.mark_completed(
                        session, target.id, final_score=deep_result.review_priority
                    )
            else:
                await target_queue.mark_completed(session, target.id)

            return crawl_result

    @classmethod
    async def run_crawl_task(cls, job_id: uuid.UUID) -> None:
        """Legacy direct invocation compatibility."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(CrawlJob).where(CrawlJob.id == job_id))
            job = result.scalar_one_or_none()
            if not job:
                logger.error(f"Crawl job {job_id} not found in database.")
                return

            # Check if target exists or create a temporary one
            target_res = await session.execute(
                select(CrawlTarget).where(CrawlTarget.canonical_url == job.target_url)
            )
            target = target_res.scalar_one_or_none()
            if not target:
                target = CrawlTarget(
                    url=job.target_url,
                    canonical_url=job.target_url,
                    platform="facebook",
                    status=TargetStatus.CLAIMED,
                    crawl_mode=job.crawl_mode,
                )
                session.add(target)
                await session.commit()
                await session.refresh(target)

            await cls.process_target(target, job_id=job.id)


crawl_service = CrawlService()
