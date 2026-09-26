import re
from typing import Any


class PhoneExtractor:
    # Matches Tunisian numbers:
    # Optional country code: +216, 00216, 216
    # 8 digits typically starting with 2, 3, 4, 5, 7, 9
    # Allows spaces, dots, dashes between digit groups
    TUNISIA_PHONE_REGEX = re.compile(
        r"(?:(?:\+|00|\(?\+?)216[\s.-]?)?\(?([234579]\d{1})\)?[\s.-]?(\d{3})[\s.-]?(\d{3})\b",
        re.IGNORECASE,
    )

    @classmethod
    def normalize_phone(cls, raw: str) -> str | None:
        """
        Normalizes various Tunisian phone formats into standard +216XXXXXXXX format.
        Examples:
            '98 123 456' -> '+21698123456'
            '98123456' -> '+21698123456'
            '+216 98 123 456' -> '+21698123456'
            '00216 98123456' -> '+21698123456'
        """
        match = cls.TUNISIA_PHONE_REGEX.search(raw)
        if not match:
            return None
        part1, part2, part3 = match.groups()
        return f"+216{part1}{part2}{part3}"

    @classmethod
    def extract(cls, text: str) -> list[dict[str, Any]]:
        """
        Extracts all Tunisian phone signals from text.
        """
        if not text:
            return []

        results: list[dict[str, Any]] = []
        seen_normalized = set()

        for match in cls.TUNISIA_PHONE_REGEX.finditer(text):
            raw_val = match.group(0).strip()
            part1, part2, part3 = match.groups()
            normalized = f"+216{part1}{part2}{part3}"

            if normalized in seen_normalized:
                continue
            seen_normalized.add(normalized)

            results.append(
                {
                    "signal_type": "PHONE",
                    "raw_value": raw_val,
                    "normalized_value": normalized,
                    "confidence": 1.0,
                    "evidence_text": raw_val,
                    "extraction_method": "tunisia_phone_regex_v1",
                }
            )

        return results
