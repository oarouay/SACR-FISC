import hashlib
import json
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import AIProvider
from app.ai.gemini import AIProviderError, GeminiProvider
from app.ai.schemas import (
    GeminiCommercialAnalysis,
    PageSemanticAnalysis,
)
from app.core.config import settings
from app.core.logging import logger
from app.models.ai_analysis import AIAnalysis


class AIService:
    """
    Orchestrates AI analysis with input hashing, caching, graceful degradation,
    and provenance persistence in the PostgreSQL database.
    """

    def __init__(self, provider: AIProvider | None = None) -> None:
        if provider is not None:
            self.provider = provider
        elif (
            settings.GEMINI_API_KEY
            and settings.GEMINI_API_KEY.strip()
            and settings.GEMINI_API_KEY != "mock"
        ):
            self.provider = GeminiProvider()
        elif settings.AI_FALLBACK_TO_MOCK:
            from app.ai.mock import MockGeminiProvider

            self.provider = MockGeminiProvider()
        else:
            self.provider = GeminiProvider()
        # Internal operational metrics
        self.metrics = {
            "gemini_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "cached_responses": 0,
            "total_latency_ms": 0,
            "posts_analyzed": 0,
            "pages_analyzed": 0,
            "ambiguity_cases_resolved": 0,
        }

    @staticmethod
    def compute_input_hash(
        provider: str,
        model: str,
        analysis_type: str,
        prompt_version: str,
        schema_version: str,
        payload: dict[str, Any],
    ) -> str:
        """Computes deterministic SHA256 hash over normalized input parameters."""
        serialized = json.dumps(
            {
                "provider": provider,
                "model": model,
                "type": analysis_type,
                "prompt_v": prompt_version,
                "schema_v": schema_version,
                "payload": payload,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def resolve_ambiguity(
        self,
        db: AsyncSession,
        page_id: uuid.UUID,
        page_name: str,
        page_description: str | None,
        page_category: str | None,
        posts: list[dict[str, Any]],
    ) -> tuple[GeminiCommercialAnalysis | None, bool]:
        """
        Runs or retrieves cached ambiguity analysis.
        Returns (result, was_cached).
        """
        if not settings.GEMINI_ENABLED:
            logger.info("Gemini analysis is disabled via settings. Skipping ambiguity resolution.")
            return None, False

        analysis_type = "AMBIGUITY_RESOLUTION"
        post_ids = [str(p.get("post_id", "")) for p in posts if p.get("post_id")]
        payload = {
            "page_name": page_name,
            "page_description": page_description,
            "page_category": page_category,
            "posts": [
                {"post_id": str(p.get("post_id", "")), "text": p.get("text", "")}
                for p in posts[: settings.GEMINI_MAX_POSTS_PER_REQUEST]
            ],
        }

        input_hash = self.compute_input_hash(
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            analysis_type=analysis_type,
            prompt_version=settings.AI_PROMPT_VERSION,
            schema_version=settings.AI_SCHEMA_VERSION,
            payload=payload,
        )

        # 1. Check cache in database
        stmt = (
            select(AIAnalysis)
            .where(AIAnalysis.input_hash == input_hash, AIAnalysis.status == "SUCCESS")
            .order_by(AIAnalysis.created_at.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        cached = res.scalar_one_or_none()
        if cached:
            self.metrics["cached_responses"] += 1
            logger.info(f"AI Cache Hit for Page {page_id} (hash={input_hash[:12]})")
            return GeminiCommercialAnalysis.model_validate(cached.output_json), True

        # 2. Call Provider
        self.metrics["gemini_calls"] += 1
        start_time = time.perf_counter()
        try:
            analysis = await self.provider.resolve_ambiguity(
                page_name=page_name,
                page_description=page_description,
                page_category=page_category,
                posts=posts,
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Record success in DB
            db_record = AIAnalysis(
                page_id=page_id,
                provider=self.provider.provider_name,
                model=self.provider.model_name,
                analysis_type=analysis_type,
                prompt_version=settings.AI_PROMPT_VERSION,
                schema_version=settings.AI_SCHEMA_VERSION,
                input_hash=input_hash,
                input_post_ids=post_ids,
                output_json=analysis.model_dump(),
                confidence=analysis.confidence,
                status="SUCCESS",
                latency_ms=latency_ms,
            )
            db.add(db_record)
            await db.commit()

            self.metrics["successful_calls"] += 1
            self.metrics["total_latency_ms"] += latency_ms
            self.metrics["ambiguity_cases_resolved"] += 1
            self.metrics["posts_analyzed"] += len(post_ids)
            return analysis, False

        except AIProviderError as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            self.metrics["failed_calls"] += 1
            logger.error(f"Gemini ambiguity resolution failed: {e}")

            # Record failure in DB for observability
            db_record = AIAnalysis(
                page_id=page_id,
                provider=self.provider.provider_name,
                model=self.provider.model_name,
                analysis_type=analysis_type,
                prompt_version=settings.AI_PROMPT_VERSION,
                schema_version=settings.AI_SCHEMA_VERSION,
                input_hash=input_hash,
                input_post_ids=post_ids,
                output_json={},
                confidence=None,
                status="FAILED",
                latency_ms=latency_ms,
                error_message=str(e),
            )
            db.add(db_record)
            await db.commit()
            return None, False

    async def analyze_page(
        self,
        db: AsyncSession,
        page_id: uuid.UUID,
        page_name: str,
        page_description: str | None,
        page_category: str | None,
        deterministic_summary: dict[str, Any],
        representative_posts: list[dict[str, Any]],
        activity_period: str | None = None,
    ) -> tuple[PageSemanticAnalysis | None, bool]:
        """
        Runs or retrieves page-level synthesis after deep crawl.
        Returns (result, was_cached).
        """
        if not settings.GEMINI_ENABLED:
            logger.info("Gemini analysis is disabled via settings. Skipping page analysis.")
            return None, False

        analysis_type = "PAGE_ANALYSIS"
        post_ids = [str(p.get("post_id", "")) for p in representative_posts if p.get("post_id")]
        payload = {
            "page_name": page_name,
            "page_description": page_description,
            "page_category": page_category,
            "deterministic_summary": deterministic_summary,
            "activity_period": activity_period,
            "representative_posts": [
                {"post_id": str(p.get("post_id", "")), "text": p.get("text", "")}
                for p in representative_posts[:10]
            ],
        }

        input_hash = self.compute_input_hash(
            provider=self.provider.provider_name,
            model=settings.GEMINI_ANALYSIS_MODEL,
            analysis_type=analysis_type,
            prompt_version=settings.AI_PROMPT_VERSION,
            schema_version=settings.AI_SCHEMA_VERSION,
            payload=payload,
        )

        # 1. Check cache
        stmt = (
            select(AIAnalysis)
            .where(AIAnalysis.input_hash == input_hash, AIAnalysis.status == "SUCCESS")
            .order_by(AIAnalysis.created_at.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        cached = res.scalar_one_or_none()
        if cached:
            self.metrics["cached_responses"] += 1
            logger.info(f"AI Cache Hit for Page Level Analysis {page_id}")
            return PageSemanticAnalysis.model_validate(cached.output_json), True

        # 2. Call Provider
        self.metrics["gemini_calls"] += 1
        start_time = time.perf_counter()
        try:
            analysis = await self.provider.analyze_page(
                page_name=page_name,
                page_description=page_description,
                page_category=page_category,
                deterministic_summary=deterministic_summary,
                representative_posts=representative_posts,
                activity_period=activity_period,
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            db_record = AIAnalysis(
                page_id=page_id,
                provider=self.provider.provider_name,
                model=settings.GEMINI_ANALYSIS_MODEL,
                analysis_type=analysis_type,
                prompt_version=settings.AI_PROMPT_VERSION,
                schema_version=settings.AI_SCHEMA_VERSION,
                input_hash=input_hash,
                input_post_ids=post_ids,
                output_json=analysis.model_dump(),
                confidence=analysis.commercial_confidence,
                status="SUCCESS",
                latency_ms=latency_ms,
            )
            db.add(db_record)
            await db.commit()

            self.metrics["successful_calls"] += 1
            self.metrics["total_latency_ms"] += latency_ms
            self.metrics["pages_analyzed"] += 1
            self.metrics["posts_analyzed"] += len(post_ids)
            return analysis, False

        except AIProviderError as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            self.metrics["failed_calls"] += 1
            logger.error(f"Gemini page analysis failed: {e}")

            db_record = AIAnalysis(
                page_id=page_id,
                provider=self.provider.provider_name,
                model=settings.GEMINI_ANALYSIS_MODEL,
                analysis_type=analysis_type,
                prompt_version=settings.AI_PROMPT_VERSION,
                schema_version=settings.AI_SCHEMA_VERSION,
                input_hash=input_hash,
                input_post_ids=post_ids,
                output_json={},
                confidence=None,
                status="FAILED",
                latency_ms=latency_ms,
                error_message=str(e),
            )
            db.add(db_record)
            await db.commit()
            return None, False


ai_service = AIService()
