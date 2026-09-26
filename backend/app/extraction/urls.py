import re
from typing import Any


class URLExtractor:
    URL_REGEX = re.compile(
        r"(?:https?://|www\.)[^\s<>{}\"\'\[\]`]+",
        re.IGNORECASE,
    )
    # Also match wa.me without scheme
    WA_SHORT_REGEX = re.compile(
        r"\b(?:wa\.me|api\.whatsapp\.com/send)[^\s<>{}\"\'\[\]`]+",
        re.IGNORECASE,
    )

    @classmethod
    def classify_url(cls, url: str) -> str:
        lowered = url.lower()
        if "wa.me" in lowered or "whatsapp.com" in lowered:
            return "WHATSAPP_LINK"
        if (
            "forms.gle" in lowered
            or "docs.google.com/forms" in lowered
            or "typeform.com" in lowered
        ):
            return "ORDER_FORM"
        if "t.me" in lowered or "telegram.me" in lowered:
            return "TELEGRAM_LINK"
        if "instagram.com" in lowered or "tiktok.com" in lowered:
            return "SOCIAL_PROFILE"
        return "WEBSITE"

    @classmethod
    def extract(cls, text: str) -> list[dict[str, Any]]:
        if not text:
            return []

        results: list[dict[str, Any]] = []
        seen = set()

        # Combine regular URLs and wa.me shorthands
        matches = [m.group(0) for m in cls.URL_REGEX.finditer(text)]
        matches.extend([m.group(0) for m in cls.WA_SHORT_REGEX.finditer(text)])

        for raw_url in matches:
            cleaned = raw_url.rstrip(".,;!?:")
            if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
                normalized_url = f"https://{cleaned}"
            else:
                normalized_url = cleaned

            if normalized_url in seen:
                continue
            seen.add(normalized_url)

            url_type = cls.classify_url(normalized_url)

            results.append(
                {
                    "signal_type": "URL",
                    "raw_value": cleaned,
                    "normalized_value": {
                        "url": normalized_url,
                        "category": url_type,
                    },
                    "confidence": 1.0,
                    "evidence_text": cleaned,
                    "extraction_method": "url_regex_v1",
                }
            )

        return results
