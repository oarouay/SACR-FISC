import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.crawl_target import CrawlTarget
from app.models.enums import CrawlMode, TargetStatus


class TargetQueue:
    """
    PostgreSQL-backed Job Queue using row-level locking (FOR UPDATE SKIP LOCKED).
    Guarantees that multiple concurrent workers never process the same target concurrently.
    """

    @staticmethod
    async def claim_next_target(db: AsyncSession) -> CrawlTarget | None:
        now = datetime.now(UTC)
        stmt = (
            select(CrawlTarget)
            .where(
                CrawlTarget.status.in_([TargetStatus.PENDING, TargetStatus.RETRY]),
                or_(
                    CrawlTarget.next_attempt_at.is_(None),
                    CrawlTarget.next_attempt_at <= now,
                ),
            )
            .order_by(CrawlTarget.priority.desc(), CrawlTarget.created_at.asc())
            .limit(1)
        )

        try:
            bind = db.bind or (getattr(db, "sync_session", None) and db.sync_session.bind)
            if not bind or bind.dialect.name != "sqlite":
                stmt = stmt.with_for_update(skip_locked=True)
        except Exception:
            stmt = stmt.with_for_update(skip_locked=True)

        result = await db.execute(stmt)
        target = result.scalar_one_or_none()
        if not target:
            return None

        target.status = TargetStatus.CLAIMED
        target.attempt_count += 1
        target.updated_at = now
        await db.commit()
        await db.refresh(target)

        logger.info(
            f"Worker claimed target {target.id} [{target.canonical_url}] "
            f"(mode={target.crawl_mode}, attempt={target.attempt_count}/{target.max_attempts})"
        )
        return target

    @staticmethod
    async def schedule_retry(
        db: AsyncSession,
        target_id: uuid.UUID,
        error_code: str,
        error_message: str | None = None,
    ) -> None:
        target = (
            await db.execute(select(CrawlTarget).where(CrawlTarget.id == target_id))
        ).scalar_one_or_none()
        if not target:
            return

        now = datetime.now(UTC)
        if target.attempt_count >= target.max_attempts:
            target.status = TargetStatus.FAILED
            logger.warning(
                f"Target {target_id} exceeded max attempts ({target.max_attempts}). Marked FAILED."
            )
        else:
            # Exponential backoff: 30s, 60s, 120s, etc.
            backoff_secs = 30 * (2 ** max(0, target.attempt_count - 1))
            target.next_attempt_at = now + timedelta(seconds=backoff_secs)
            target.status = TargetStatus.RETRY
            logger.info(
                f"Scheduled retry for target {target_id} in {backoff_secs}s (error={error_code})"
            )

        target.updated_at = now
        await db.commit()

    @staticmethod
    async def mark_blocked(
        db: AsyncSession,
        target_id: uuid.UUID,
        reason: str,
    ) -> None:
        target = (
            await db.execute(select(CrawlTarget).where(CrawlTarget.id == target_id))
        ).scalar_one_or_none()
        if not target:
            return

        target.status = TargetStatus.BLOCKED
        target.updated_at = datetime.now(UTC)
        await db.commit()
        logger.warning(f"Target {target_id} marked BLOCKED: {reason}")

    @staticmethod
    async def mark_manual_review(
        db: AsyncSession,
        target_id: uuid.UUID,
        reason: str,
    ) -> None:
        target = (
            await db.execute(select(CrawlTarget).where(CrawlTarget.id == target_id))
        ).scalar_one_or_none()
        if not target:
            return

        target.status = TargetStatus.MANUAL_REVIEW
        target.updated_at = datetime.now(UTC)
        await db.commit()
        logger.info(f"Target {target_id} marked MANUAL_REVIEW: {reason}")

    @staticmethod
    async def mark_failed(
        db: AsyncSession,
        target_id: uuid.UUID,
        reason: str,
    ) -> None:
        target = (
            await db.execute(select(CrawlTarget).where(CrawlTarget.id == target_id))
        ).scalar_one_or_none()
        if not target:
            return

        target.status = TargetStatus.FAILED
        target.updated_at = datetime.now(UTC)
        await db.commit()
        logger.error(f"Target {target_id} marked FAILED: {reason}")

    @staticmethod
    async def mark_completed(
        db: AsyncSession,
        target_id: uuid.UUID,
        quick_score: float | None = None,
        final_score: float | None = None,
    ) -> None:
        target = (
            await db.execute(select(CrawlTarget).where(CrawlTarget.id == target_id))
        ).scalar_one_or_none()
        if not target:
            return

        now = datetime.now(UTC)
        target.status = TargetStatus.COMPLETED
        target.last_crawled_at = now
        target.updated_at = now
        if quick_score is not None:
            target.quick_score = quick_score
        if final_score is not None:
            target.final_score = final_score

        await db.commit()
        logger.info(f"Target {target_id} marked COMPLETED (final_score={target.final_score})")

    @staticmethod
    async def promote_to_deep(
        db: AsyncSession,
        target_id: uuid.UUID,
        quick_score: float,
    ) -> None:
        target = (
            await db.execute(select(CrawlTarget).where(CrawlTarget.id == target_id))
        ).scalar_one_or_none()
        if not target:
            return

        now = datetime.now(UTC)
        target.crawl_mode = CrawlMode.DEEP
        target.status = TargetStatus.PENDING
        target.quick_score = quick_score
        target.priority += 10  # prioritize deep crawl of qualified candidates
        target.next_attempt_at = now
        target.updated_at = now

        await db.commit()
        logger.info(
            f"Target {target_id} promoted to DEEP crawl (quick_score={quick_score} >= {settings.DEEP_CRAWL_THRESHOLD})"
        )


target_queue = TargetQueue()
