import re
from typing import Any


class PriceExtractor:
    # Pattern matching Tunisian Dinars:
    # Numeric part: e.g. 89, 89.5, 89,500, 89.500, 1500
    # Currency markers: DT, D.T, dt, d.t, TND, tnd, dinar, dinars, دينار, د.ت, د ت
    PRICE_REGEX = re.compile(
        r"(?:(?:prix|السعر|tarif)[\s:]*)?"
        r"(?P<amount>\d{1,4}(?:[\s.,]\d{3})*(?:[.,]\d{1,3})?|\d+(?:[.,]\d+)?)"
        r"[\s]*"
        r"(?P<currency>DT|D\.T|dt|d\.t|TND|tnd|dinars?|دينار(?:ا|اً)?|د\.ت|د\s*ت)\b",
        re.IGNORECASE,
    )

    # Reverse pattern where currency comes first, e.g. "DT 89", "دينار 89"
    REVERSE_PRICE_REGEX = re.compile(
        r"(?P<currency>DT|D\.T|dt|d\.t|TND|tnd|دينار|د\.ت)[\s:]+"
        r"(?P<amount>\d{1,4}(?:[\s.,]\d{3})*(?:[.,]\d{1,3})?|\d+(?:[.,]\d+)?)",
        re.IGNORECASE,
    )

    @staticmethod
    def parse_amount(raw_num: str) -> float | int:
        """
        Parses amount string into float or int.
        Handles Tunisian millimes (e.g. 89,500 DT -> 89.5 TND, 89.500 DT -> 89.5 TND).
        """
        cleaned = raw_num.replace(" ", "").strip()

        # Check for 3-decimal millimes notation, e.g., "89,500" or "89.500"
        if re.search(r"^\d+[.,]\d{3}$", cleaned):
            parts = re.split(r"[.,]", cleaned)
            whole = int(parts[0])
            millimes = int(parts[1])
            val = whole + (millimes / 1000.0)
            return round(val, 3) if millimes % 100 != 0 else round(val, 1)

        # Standard decimal point with comma or period
        if "," in cleaned and "." not in cleaned:
            cleaned = cleaned.replace(",", ".")

        val = float(cleaned)
        return int(val) if val.is_integer() else val

    @classmethod
    def extract(cls, text: str) -> list[dict[str, Any]]:
        """
        Extracts all price signals from text.
        """
        if not text:
            return []

        results: list[dict[str, Any]] = []
        seen_matches = set()

        for pattern in (cls.PRICE_REGEX, cls.REVERSE_PRICE_REGEX):
            for match in pattern.finditer(text):
                raw_match = match.group(0).strip()
                if raw_match in seen_matches:
                    continue
                seen_matches.add(raw_match)

                raw_amount = match.group("amount")
                try:
                    parsed_amount = cls.parse_amount(raw_amount)
                except ValueError:
                    continue

                results.append(
                    {
                        "signal_type": "PRICE",
                        "raw_value": raw_match,
                        "normalized_value": {
                            "amount": parsed_amount,
                            "currency": "TND",
                        },
                        "confidence": 1.0,
                        "evidence_text": raw_match,
                        "extraction_method": "tunisia_price_regex_v1",
                    }
                )

        return results
