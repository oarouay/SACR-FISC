import asyncio
import json
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.base import AIProvider
from app.ai.prompts import (
    AMBIGUITY_RESOLUTION_PROMPT,
    BATCH_POST_CLASSIFICATION_PROMPT,
    PAGE_LEVEL_ANALYSIS_PROMPT,
    SYSTEM_INSTRUCTION,
)
from app.ai.schemas import (
    BatchPostClassificationResponse,
    GeminiCommercialAnalysis,
    PageSemanticAnalysis,
)
from app.core.config import settings
from app.core.logging import logger

T = TypeVar("T", bound=BaseModel)


class AIProviderError(Exception):
    """Base exception for AI provider operations."""

    pass


class GeminiProvider(AIProvider):
    """
    Production-ready Google Gemini API provider.
    Implements concurrency limiting, bounded retries, structured JSON validation,
    and post-processing evidence validation.
    """

    def __init__(
        self,
        api_key: str | None = None,
        fast_model: str | None = None,
        analysis_model: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        concurrency: int | None = None,
    ) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.fast_model = fast_model or settings.GEMINI_FAST_MODEL
        self.analysis_model = analysis_model or settings.GEMINI_ANALYSIS_MODEL
        self.timeout = timeout if timeout is not None else settings.GEMINI_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.GEMINI_MAX_RETRIES
        limit = concurrency if concurrency is not None else settings.GEMINI_CONCURRENCY
        self._semaphore = asyncio.Semaphore(limit)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self.fast_model

    async def _execute_generate_content(
        self,
        model: str,
        user_prompt: str,
        schema_cls: type[T],
        allowed_post_ids: set[str],
    ) -> tuple[T, int, dict[str, Any]]:
        """
        Executes an HTTP call to Gemini generateContent with concurrency limit and retries.
        Returns (parsed_pydantic_instance, latency_ms, usage_metadata).
        """
        if not self.api_key:
            raise AIProviderError("GEMINI_API_KEY is not configured.")

        url = f"{self.base_url}/{model}:generateContent"
        params = {"key": self.api_key}

        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        }

        async with self._semaphore:
            backoff = 1.0
            last_err: Exception | None = None

            for attempt in range(1, self.max_retries + 2):
                start_time = time.perf_counter()
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(url, params=params, json=payload)

                    latency_ms = int((time.perf_counter() - start_time) * 1000)

                    if response.status_code == 429:
                        logger.warning(
                            f"Gemini API 429 Rate Limited (attempt {attempt}). Backing off {backoff}s..."
                        )
                        if attempt <= self.max_retries:
                            await asyncio.sleep(backoff)
                            backoff *= 2.0
                            continue
                        raise AIProviderError("Gemini API rate limit exceeded (429).")

                    if response.status_code >= 500:
                        logger.warning(
                            f"Gemini API 5xx Server Error {response.status_code} (attempt {attempt})."
                        )
                        if attempt <= self.max_retries:
                            await asyncio.sleep(backoff)
                            backoff *= 2.0
                            continue
                        raise AIProviderError(f"Gemini server error: {response.status_code}")

                    if response.status_code != 200:
                        raise AIProviderError(
                            f"Gemini API error ({response.status_code}): {response.text[:200]}"
                        )

                    resp_data = response.json()
                    candidates = resp_data.get("candidates", [])
                    if not candidates:
                        raise AIProviderError("Gemini returned empty candidates.")

                    raw_text = (
                        candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    )
                    if not raw_text:
                        raise AIProviderError("Gemini candidate has no text part.")

                    usage = resp_data.get("usageMetadata", {})

                    # Parse JSON
                    parsed_dict = json.loads(raw_text)

                    # Evidence provenance check: filter/validate post IDs
                    if "evidence_post_ids" in parsed_dict and isinstance(
                        parsed_dict["evidence_post_ids"], list
                    ):
                        valid_ids = [
                            pid
                            for pid in parsed_dict["evidence_post_ids"]
                            if str(pid) in allowed_post_ids
                        ]
                        parsed_dict["evidence_post_ids"] = valid_ids

                    # Pydantic validation
                    validated_obj = schema_cls.model_validate(parsed_dict)
                    return validated_obj, latency_ms, usage

                except (httpx.TimeoutException, httpx.NetworkError) as e:
                    last_err = e
                    logger.warning(
                        f"Gemini network error (attempt {attempt}/{self.max_retries + 1}): {e}"
                    )
                    if attempt <= self.max_retries:
                        await asyncio.sleep(backoff)
                        backoff *= 2.0
                        continue
                except (json.JSONDecodeError, ValidationError) as e:
                    last_err = e
                    logger.warning(f"Gemini response validation error (attempt {attempt}): {e}")
                    if attempt <= self.max_retries:
                        await asyncio.sleep(backoff)
                        backoff *= 1.5
                        continue
                except Exception as e:
                    last_err = e
                    break

            raise AIProviderError(f"Gemini operation failed after retries: {last_err}")

    async def resolve_ambiguity(
        self,
        page_name: str,
        page_description: str | None,
        page_category: str | None,
        posts: list[dict[str, Any]],
    ) -> GeminiCommercialAnalysis:
        allowed_ids = {str(p.get("post_id")) for p in posts if p.get("post_id")}
        posts_payload = [
            {"post_id": str(p.get("post_id", "")), "text": p.get("text", "")}
            for p in posts[: settings.GEMINI_MAX_POSTS_PER_REQUEST]
        ]
        prompt = AMBIGUITY_RESOLUTION_PROMPT.format(
            page_name=page_name or "Unknown",
            page_category=page_category or "Unspecified",
            page_description=page_description or "None provided",
            posts_json=json.dumps(posts_payload, ensure_ascii=False, indent=2),
        )

        result, _, _ = await self._execute_generate_content(
            model=self.fast_model,
            user_prompt=prompt,
            schema_cls=GeminiCommercialAnalysis,
            allowed_post_ids=allowed_ids,
        )
        return result

    async def classify_posts(
        self,
        posts: list[dict[str, Any]],
    ) -> BatchPostClassificationResponse:
        allowed_ids = {str(p.get("post_id")) for p in posts if p.get("post_id")}
        posts_payload = [
            {"post_id": str(p.get("post_id", "")), "text": p.get("text", "")}
            for p in posts[: settings.GEMINI_MAX_POSTS_PER_REQUEST]
        ]
        prompt = BATCH_POST_CLASSIFICATION_PROMPT.format(
            posts_json=json.dumps(posts_payload, ensure_ascii=False, indent=2),
        )

        result, _, _ = await self._execute_generate_content(
            model=self.fast_model,
            user_prompt=prompt,
            schema_cls=BatchPostClassificationResponse,
            allowed_post_ids=allowed_ids,
        )

        # Enforce that only supplied post IDs are included
        filtered_posts = [p for p in result.posts if p.post_id in allowed_ids]
        result.posts = filtered_posts
        return result

    async def analyze_page(
        self,
        page_name: str,
        page_description: str | None,
        page_category: str | None,
        deterministic_summary: dict[str, Any],
        representative_posts: list[dict[str, Any]],
        activity_period: str | None = None,
    ) -> PageSemanticAnalysis:
        allowed_ids = {str(p.get("post_id")) for p in representative_posts if p.get("post_id")}
        posts_payload = [
            {"post_id": str(p.get("post_id", "")), "text": p.get("text", "")}
            for p in representative_posts[:10]
        ]
        prompt = PAGE_LEVEL_ANALYSIS_PROMPT.format(
            page_name=page_name or "Unknown",
            page_category=page_category or "Unspecified",
            page_description=page_description or "None provided",
            total_posts=deterministic_summary.get("total_posts", 0),
            price_count=deterministic_summary.get("price_count", 0),
            order_count=deterministic_summary.get("order_count", 0),
            delivery_count=deterministic_summary.get("delivery_count", 0),
            payment_count=deterministic_summary.get("payment_count", 0),
            promo_count=deterministic_summary.get("promo_count", 0),
            activity_period=activity_period or "Recent collection window",
            representative_posts_json=json.dumps(posts_payload, ensure_ascii=False, indent=2),
        )

        result, _, _ = await self._execute_generate_content(
            model=self.analysis_model,
            user_prompt=prompt,
            schema_cls=PageSemanticAnalysis,
            allowed_post_ids=allowed_ids,
        )
        return result
