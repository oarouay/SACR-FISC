import hashlib

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.page import Page
from app.models.post import Post
from app.models.signal import ExtractedSignal


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert "collector_version" in data
    assert "extractor_version" in data


@pytest.mark.asyncio
async def test_create_and_get_crawl_job(async_client: AsyncClient, db_session: AsyncSession):

    payload = {
        "url": "https://www.facebook.com/controlled-page-test",
        "max_posts": 10,
        "max_scroll_cycles": 5,
    }
    response = await async_client.post("/crawl-jobs", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "PENDING"

    job_id = data["job_id"]

    # Retrieve job status
    get_res = await async_client.get(f"/crawl-jobs/{job_id}")
    assert get_res.status_code == 200
    job_detail = get_res.json()
    assert job_detail["id"] == job_id
    assert job_detail["target_url"] == payload["url"]
    assert job_detail["max_posts"] == 10


@pytest.mark.asyncio
async def test_pages_and_signals_endpoints(async_client: AsyncClient, db_session: AsyncSession):
    # Seed a test page, post, and signals
    page = Page(
        canonical_url="https://facebook.com/test-shop",
        name="Test Shop SARL",
        public_phone="+21698123456",
        public_email="test@shop.tn",
    )
    db_session.add(page)
    await db_session.flush()

    post = Post(
        page_id=page.id,
        platform_post_id="post_999",
        text="Promotion 89 DT. Livraison toute la Tunisie.",
        content_hash=hashlib.sha256(b"test").hexdigest(),
    )
    db_session.add(post)
    await db_session.flush()

    sig1 = ExtractedSignal(
        page_id=page.id,
        post_id=post.id,
        signal_type="PRICE",
        raw_value="89 DT",
        normalized_value={"amount": 89, "currency": "TND"},
        evidence_text="89 DT",
    )
    sig2 = ExtractedSignal(
        page_id=page.id,
        post_id=post.id,
        signal_type="DELIVERY",
        raw_value="Livraison toute la Tunisie",
        normalized_value="TUNISIA_NATIONWIDE",
        evidence_text="Livraison toute la Tunisie",
    )
    db_session.add_all([sig1, sig2])
    await db_session.commit()

    # 1. GET /pages
    pages_res = await async_client.get("/pages")
    assert pages_res.status_code == 200
    pages_data = pages_res.json()
    assert len(pages_data) >= 1
    assert any(p["id"] == str(page.id) for p in pages_data)

    # 2. GET /pages/{id}
    page_detail = (await async_client.get(f"/pages/{page.id}")).json()
    assert page_detail["name"] == "Test Shop SARL"
    assert page_detail["posts_count"] == 1
    assert page_detail["signals_count"] == 2

    # 3. GET /pages/{id}/posts
    posts_res = await async_client.get(f"/pages/{page.id}/posts")
    assert posts_res.status_code == 200
    assert len(posts_res.json()) == 1

    # 4. GET /pages/{id}/signals
    signals_res = await async_client.get(f"/pages/{page.id}/signals")
    assert signals_res.status_code == 200
    sig_data = signals_res.json()
    assert sig_data["total_signals"] == 2
    assert sig_data["signals_by_type"]["PRICE"] == 1
    assert sig_data["signals_by_type"]["DELIVERY"] == 1

    # 5. GET /posts/{id}
    post_res = await async_client.get(f"/posts/{post.id}")
    assert post_res.status_code == 200
    assert len(post_res.json()["signals"]) == 2


@pytest.mark.asyncio
async def test_fiscal_registry_search_endpoint(async_client: AsyncClient):
    # Query with phone
    resp = await async_client.get("/fiscal-registry/search?phone=%2B21698123456")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    assert data["results"][0]["tax_id"] == "MAT-TEST-001"

    # Query with business name
    resp_name = await async_client.get("/fiscal-registry/search?business_name=Tunis")
    assert resp_name.status_code == 200
    assert resp_name.json()["count"] >= 1


@pytest.mark.asyncio
async def test_ai_analysis_api_endpoints(async_client: AsyncClient, db_session: AsyncSession):
    from app.models.ai_analysis import AIAnalysis

    page = Page(
        canonical_url="https://facebook.com/ai-test-page",
        name="AI Boutique",
        description="Boutique en ligne",
    )
    db_session.add(page)
    await db_session.flush()

    post = Post(
        page_id=page.id,
        platform_post_id="post_ai_001",
        text="Nouvelle collection robes 65 DT livraison gratuite",
        content_hash=hashlib.sha256(b"ai_post_test").hexdigest(),
    )
    db_session.add(post)
    await db_session.flush()

    # Seed an AI analysis record
    ai_record = AIAnalysis(
        page_id=page.id,
        post_id=post.id,
        provider="gemini",
        model="gemini-2.5-flash",
        analysis_type="POST_CLASSIFICATION",
        prompt_version="1.0.0",
        schema_version="1.0.0",
        input_hash="hash_test_123",
        input_post_ids=["post_ai_001"],
        output_json={"is_commercial": True, "activity_type": "PRODUCT_SALE"},
        confidence=0.95,
        status="SUCCESS",
        latency_ms=250,
    )
    db_session.add(ai_record)
    await db_session.commit()

    # 1. Test GET /pages/{page_id}/ai-analysis
    page_ai_res = await async_client.get(f"/pages/{page.id}/ai-analysis")
    assert page_ai_res.status_code == 200
    records = page_ai_res.json()
    assert len(records) == 1
    assert records[0]["analysis_type"] == "POST_CLASSIFICATION"
    assert records[0]["confidence"] == 0.95

    # 2. Test GET /posts/{post_id}/ai-analysis
    post_ai_res = await async_client.get(f"/posts/{post.id}/ai-analysis")
    assert post_ai_res.status_code == 200
    post_records = post_ai_res.json()
    assert len(post_records) == 1
    assert post_records[0]["post_id"] == str(post.id)

    # 3. Test POST /pages/{page_id}/reanalyze with mocked provider
    from unittest.mock import AsyncMock, patch

    from app.ai.schemas import PageSemanticAnalysis

    mock_analysis = PageSemanticAnalysis(
        business_pattern="RECURRING_COMMERCIAL_ACTIVITY",
        commercial_confidence=0.94,
        business_type="ONLINE_RETAIL",
        products_or_services=["robes"],
        sales_channels=["private_message"],
        delivery_pattern="NATIONWIDE",
        recurring_activity=True,
        evidence_post_ids=["post_ai_001"],
        reasons=["Offres fréquentes"],
    )

    with patch("app.ai.service.AIService.analyze_page", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = (mock_analysis, False)
        reanalyze_res = await async_client.post(f"/pages/{page.id}/reanalyze?force=true")
        assert reanalyze_res.status_code == 200
        reanalyze_data = reanalyze_res.json()
        assert reanalyze_data["status"] == "SUCCESS"
        assert reanalyze_data["analysis_type"] == "PAGE_ANALYSIS"
