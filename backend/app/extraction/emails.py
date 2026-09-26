import re
from typing import Any


class EmailExtractor:
    EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

    @classmethod
    def extract(cls, text: str) -> list[dict[str, Any]]:
        if not text:
            return []

        results: list[dict[str, Any]] = []
        seen = set()

        for match in cls.EMAIL_REGEX.finditer(text):
            raw_email = match.group(0).strip()
            normalized = raw_email.lower()

            if normalized in seen:
                continue
            seen.add(normalized)

            results.append(
                {
                    "signal_type": "EMAIL",
                    "raw_value": raw_email,
                    "normalized_value": normalized,
                    "confidence": 1.0,
                    "evidence_text": raw_email,
                    "extraction_method": "rfc_email_regex_v1",
                }
            )

        return results
