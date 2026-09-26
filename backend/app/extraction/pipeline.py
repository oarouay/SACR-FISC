import uuid
from typing import Any

from app.core.config import settings
from app.extraction.commercial_terms import commercial_terms_extractor
from app.extraction.emails import EmailExtractor
from app.extraction.phones import PhoneExtractor
from app.extraction.prices import PriceExtractor
from app.extraction.urls import URLExtractor
from app.models.signal import ExtractedSignal


class SignalExtractionPipeline:
    def __init__(self, version: str = settings.EXTRACTOR_VERSION) -> None:
        self.version = version

    def extract_signals(
        self,
        text: str,
        page_id: uuid.UUID,
        post_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """
        Runs deterministic extraction on text and produces signal dicts.
        """
        if not text or not text.strip():
            return []

        raw_signals: list[dict[str, Any]] = []

        # 1. Prices
        raw_signals.extend(PriceExtractor.extract(text))

        # 2. Phones
        raw_signals.extend(PhoneExtractor.extract(text))

        # 3. Commercial terms (Delivery, Orders, Promotions, Stock, Payment)
        raw_signals.extend(commercial_terms_extractor.extract(text))

        # 4. Emails
        raw_signals.extend(EmailExtractor.extract(text))

        # 5. URLs
        raw_signals.extend(URLExtractor.extract(text))

        # Standardize metadata and link to entity IDs
        standardized: list[dict[str, Any]] = []
        for sig in raw_signals:
            standardized.append(
                {
                    "page_id": page_id,
                    "post_id": post_id,
                    "signal_type": sig["signal_type"],
                    "raw_value": sig["raw_value"],
                    "normalized_value": sig["normalized_value"],
                    "confidence": sig.get("confidence", 1.0),
                    "evidence_text": sig.get("evidence_text", sig["raw_value"]),
                    "extraction_method": sig.get("extraction_method", "deterministic_v1"),
                    "extraction_version": self.version,
                }
            )

        return standardized

    def create_signal_models(
        self,
        text: str,
        page_id: uuid.UUID,
        post_id: uuid.UUID | None = None,
    ) -> list[ExtractedSignal]:
        """
        Extracts signals and converts them to SQLAlchemy ExtractedSignal models.
        """
        dicts = self.extract_signals(text=text, page_id=page_id, post_id=post_id)
        return [ExtractedSignal(**d) for d in dicts]


signal_pipeline = SignalExtractionPipeline()
