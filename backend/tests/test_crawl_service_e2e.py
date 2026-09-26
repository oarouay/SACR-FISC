import hashlib
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import CrawlResult, EvidenceArtifact, RawPageMetadata, RawPostData
from app.models.crawl_job import CrawlJob, CrawlStatus
from app.models.evidence import Evidence
from app.models.page import Page
from app.models.post import Post
from app.models.signal import ExtractedSignal
from app.services.crawl_service import crawl_service


@pytest.mark.asyncio
async def test_crawl_service_end_to_end_mocked(db_session: AsyncSession):
    # 1. Create crawl job
    job = await crawl_service.create_job(
        db=db_session,
        target_url="https://www.facebook.com/tunis-fashion-test",
        max_posts=5,
        max_scroll_cycles=2,
    )
    assert job.status == CrawlStatus.PENDING

    # 2. Prepare mock collector output
    mock_page = RawPageMetadata(
        name="Tunis Fashion Test",
        canonical_url="https://www.facebook.com/tunis-fashion-test",
        platform_page_id="tunis.fashion",
        description="Boutique de mode. WhatsApp: 98 123 456",
        public_phone="+21698123456",
        public_email="contact@tunisfashion.tn",
    )
    mock_post_text = (
        "Promotion 89 DT. Livraison toute la Tunisie. Commande WhatsApp +216 98 123 456"
    )
    mock_post = RawPostData(
        platform_post_id="post_1001",
        permalink="https://www.facebook.com/tunis-fashion-test/posts/1001",
        text=mock_post_text,
        published_at=None,
        raw_data={"adapter": "test"},
        content_hash=hashlib.sha256(mock_post_text.encode()).hexdigest(),
    )
    mock_evidence = EvidenceArtifact(
        evidence_type="SCREENSHOT_PAGE",
        data=b"FakePNGDataForScreenshot",
        filename_prefix="test_e2e",
        metadata={"step": "overview"},
    )
    mock_result = CrawlResult(
        status=CrawlStatus.SUCCESS,
        posts_collected=1,
        page_metadata=mock_page,
        posts=[mock_post],
        evidence_items=[mock_evidence],
    )

    # 3. Patch FacebookPageCollector.run and AsyncSessionLocal
    with (
        patch(
            "app.collectors.facebook.collector.FacebookPageCollector.run", new_callable=AsyncMock
        ) as mock_run,
        patch("app.services.crawl_service.AsyncSessionLocal") as mock_session_factory,
    ):
        mock_run.return_value = mock_result
        # Direct session context to use db_session
        mock_session_factory.return_value.__aenter__.return_value = db_session
        mock_session_factory.return_value.__aexit__.return_value = None

        await crawl_service.run_crawl_task(job.id)

    # 4. Verify outcomes in Database
    updated_job = (
        await db_session.execute(select(CrawlJob).where(CrawlJob.id == job.id))
    ).scalar_one()
    assert updated_job.status == CrawlStatus.SUCCESS
    assert updated_job.posts_collected == 1
    assert updated_job.finished_at is not None

    # Verify Page record
    page = (
        await db_session.execute(select(Page).where(Page.canonical_url == mock_page.canonical_url))
    ).scalar_one()
    assert page.name == "Tunis Fashion Test"
    assert page.public_phone == "+21698123456"

    # Verify Post record
    post = (await db_session.execute(select(Post).where(Post.page_id == page.id))).scalar_one()
    assert post.platform_post_id == "post_1001"
    assert post.text == mock_post_text

    # Verify ExtractedSignals attached to post
    signals = (
        (
            await db_session.execute(
                select(ExtractedSignal).where(ExtractedSignal.post_id == post.id)
            )
        )
        .scalars()
        .all()
    )
    sig_types = [s.signal_type for s in signals]
    assert "PRICE" in sig_types
    assert "DELIVERY" in sig_types
    assert "ORDER_INSTRUCTION" in sig_types
    assert "PHONE" in sig_types

    # Verify Evidence record
    evidence_list = (
        (await db_session.execute(select(Evidence).where(Evidence.crawl_job_id == job.id)))
        .scalars()
        .all()
    )
    assert len(evidence_list) == 1
    assert evidence_list[0].evidence_type == "SCREENSHOT_PAGE"
