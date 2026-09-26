import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.normalizer import normalize_facebook_url
from app.ingestion.service import target_ingestion_service
from app.ingestion.sources import CsvTargetSource
from app.models.crawl_target import CrawlTarget
from app.models.enums import CrawlMode, RegistryStatus, TargetStatus
from app.models.page import Page
from app.models.page_score import PageScore, ScoreReason
from app.queue.target_queue import target_queue


def test_url_normalization_and_deduplication():
    url1 = "https://m.facebook.com/tunis.shop/?ref=bookmarks&mibextid=ZbWKwL"
    url2 = "https://www.facebook.com/tunis.shop"
    url3 = "http://facebook.com/tunis.shop/"

    norm1 = normalize_facebook_url(url1)
    norm2 = normalize_facebook_url(url2)
    norm3 = normalize_facebook_url(url3)

    assert norm1 == "https://www.facebook.com/tunis.shop"
    assert norm2 == "https://www.facebook.com/tunis.shop"
    assert norm3 == "https://www.facebook.com/tunis.shop"


async def test_csv_target_source_ingestion(db_session: AsyncSession):
    csv_text = """url,priority
https://facebook.com/page1?ref=test,10
https://m.facebook.com/page2,5
https://facebook.com/page1,20
https://facebook.com/page3,0
"""
    source = CsvTargetSource(csv_text)
    result = await target_ingestion_service.ingest_from_source(db_session, source)

    assert result["total_submitted"] == 4
    assert result["created_count"] == 3  # page1 duplicate in batch skipped
    assert result["duplicates_skipped"] == 1


async def test_target_queue_claiming_and_skip_locked(db_session: AsyncSession):
    # Enqueue 2 targets
    t1 = CrawlTarget(
        url="https://facebook.com/first-target",
        canonical_url="https://www.facebook.com/first-target",
        priority=10,
        status=TargetStatus.PENDING,
        crawl_mode=CrawlMode.QUICK,
    )
    t2 = CrawlTarget(
        url="https://facebook.com/second-target",
        canonical_url="https://www.facebook.com/second-target",
        priority=20,
        status=TargetStatus.PENDING,
        crawl_mode=CrawlMode.QUICK,
    )
    db_session.add_all([t1, t2])
    await db_session.commit()

    # Claim 1: Should claim t2 because priority=20 > priority=10
    claimed1 = await target_queue.claim_next_target(db_session)
    assert claimed1 is not None
    assert claimed1.canonical_url == "https://www.facebook.com/second-target"
    assert claimed1.status == TargetStatus.CLAIMED
    assert claimed1.attempt_count == 1

    # Claim 2: Should claim t1
    claimed2 = await target_queue.claim_next_target(db_session)
    assert claimed2 is not None
    assert claimed2.canonical_url == "https://www.facebook.com/first-target"
    assert claimed2.status == TargetStatus.CLAIMED

    # Claim 3: None available
    claimed3 = await target_queue.claim_next_target(db_session)
    assert claimed3 is None


async def test_target_queue_retry_and_blocked(db_session: AsyncSession):
    target = CrawlTarget(
        url="https://facebook.com/retry-test",
        canonical_url="https://www.facebook.com/retry-test",
        status=TargetStatus.CLAIMED,
        attempt_count=1,
        max_attempts=3,
        crawl_mode=CrawlMode.QUICK,
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)

    # Schedule transient retry
    await target_queue.schedule_retry(db_session, target.id, error_code="TIMEOUT")
    await db_session.refresh(target)
    assert target.status == TargetStatus.RETRY
    assert target.next_attempt_at is not None

    # Test BLOCKED status (e.g. CAPTCHA)
    await target_queue.mark_blocked(db_session, target.id, reason="CAPTCHA encountered")
    await db_session.refresh(target)
    assert target.status == TargetStatus.BLOCKED

    # Blocked target must NOT be claimed
    claimed = await target_queue.claim_next_target(db_session)
    assert claimed is None


async def test_target_promotion_to_deep(db_session: AsyncSession):
    target = CrawlTarget(
        url="https://facebook.com/promote-test",
        canonical_url="https://www.facebook.com/promote-test",
        status=TargetStatus.CLAIMED,
        crawl_mode=CrawlMode.QUICK,
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)

    # Promote
    await target_queue.promote_to_deep(db_session, target.id, quick_score=75.0)
    await db_session.refresh(target)
    assert target.crawl_mode == CrawlMode.DEEP
    assert target.status == TargetStatus.PENDING
    assert target.quick_score == 75.0


async def test_review_queue_and_metrics_endpoints(
    async_client: AsyncClient, db_session: AsyncSession
):
    # Setup Page and Score above review threshold (85.0 >= 75.0)
    page_id = uuid.uuid4()
    page = Page(
        id=page_id,
        name="Review Target Store",
        canonical_url="https://www.facebook.com/review-target-store",
    )
    db_session.add(page)
    await db_session.flush()

    score = PageScore(
        page_id=page_id,
        commercial_activity_score=90.0,
        transaction_evidence_score=85.0,
        economic_activity_score=80.0,
        review_priority_score=86.0,
    )
    db_session.add(score)
    await db_session.flush()

    reason = ScoreReason(
        page_score_id=score.id,
        component="COMMERCIAL_ACTIVITY",
        reason="15 posts contain explicit prices",
        weight_or_value=35.0,
    )
    db_session.add(reason)
    await db_session.commit()

    # Query GET /review-queue
    resp = await async_client.get("/review-queue")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    found = next((i for i in items if i["page_id"] == str(page_id)), None)
    assert found is not None
    assert found["review_priority"] == 86.0
    assert found["registry_status"] == RegistryStatus.NOT_CHECKED.value
    assert len(found["reasons"]) >= 1

    # Query GET /metrics/summary
    metrics_resp = await async_client.get("/metrics/summary")
    assert metrics_resp.status_code == 200
    metrics_data = metrics_resp.json()
    assert "total_targets" in metrics_data
    assert "pages_in_review_queue" in metrics_data
    assert metrics_data["pages_in_review_queue"] >= 1
