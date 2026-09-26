from abc import ABC, abstractmethod
from typing import Any

from app.ai.schemas import (
    BatchPostClassificationResponse,
    GeminiCommercialAnalysis,
    PageSemanticAnalysis,
)


class AIProvider(ABC):
    """
    Abstract AI Provider Interface.
    Decouples application orchestration from model-specific APIs.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g., 'gemini', 'mock')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the active model."""
        pass

    @abstractmethod
    async def resolve_ambiguity(
        self,
        page_name: str,
        page_description: str | None,
        page_category: str | None,
        posts: list[dict[str, Any]],
    ) -> GeminiCommercialAnalysis:
        """
        Ambiguity resolution for pages in the borderline quick score zone [25, 65).
        """
        pass

    @abstractmethod
    async def classify_posts(
        self,
        posts: list[dict[str, Any]],
    ) -> BatchPostClassificationResponse:
        """
        Batch-level semantic post classification.
        """
        pass

    @abstractmethod
    async def analyze_page(
        self,
        page_name: str,
        page_description: str | None,
        page_category: str | None,
        deterministic_summary: dict[str, Any],
        representative_posts: list[dict[str, Any]],
        activity_period: str | None = None,
    ) -> PageSemanticAnalysis:
        """
        Page-level commercial activity synthesis after deep crawl.
        """
        pass
