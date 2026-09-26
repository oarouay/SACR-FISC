import re
from typing import Any, NamedTuple


class TermDefinition(NamedTuple):
    pattern: str
    signal_type: str
    normalized_value: str
    confidence: float = 1.0


# Configurable dictionary of commercial signals across French, Arabic, and Tunisian dialect.
# More specific multi-word phrases MUST come first to match before single-word tokens.
COMMERCIAL_DICTIONARY: list[TermDefinition] = [
    # --- DELIVERY SIGNALS ---
    TermDefinition(r"\blivraison toute la tunisie\b", "DELIVERY", "TUNISIA_NATIONWIDE"),
    TermDefinition(r"\blivraison 24 gouvernorats\b", "DELIVERY", "TUNISIA_24_GOVERNORATES"),
    TermDefinition(r"\blivraison 24 wilayas\b", "DELIVERY", "TUNISIA_24_GOVERNORATES"),
    TermDefinition(r"توصيل كامل تراب الجمهورية", "DELIVERY", "TUNISIA_NATIONWIDE"),
    TermDefinition(r"توصيل 24 ولاية", "DELIVERY", "TUNISIA_24_GOVERNORATES"),
    TermDefinition(r"\blivraison gratuite\b", "DELIVERY", "FREE_DELIVERY"),
    TermDefinition(r"توصيل مجاني", "DELIVERY", "FREE_DELIVERY"),
    TermDefinition(r"\blivraison express\b", "DELIVERY", "EXPRESS_DELIVERY"),
    TermDefinition(r"\blivraison à domicile\b", "DELIVERY", "HOME_DELIVERY"),
    TermDefinition(r"\blivraison a domicile\b", "DELIVERY", "HOME_DELIVERY"),
    TermDefinition(r"\blivraison rapide\b", "DELIVERY", "FAST_DELIVERY"),
    TermDefinition(r"\blivraison\b", "DELIVERY", "DELIVERY_AVAILABLE"),
    TermDefinition(r"\bتوصيل\b", "DELIVERY", "DELIVERY_AVAILABLE"),
    # --- ORDER INSTRUCTION SIGNALS ---
    TermDefinition(r"\bcommande whatsapp\b", "ORDER_INSTRUCTION", "WHATSAPP"),
    TermDefinition(r"\bsur whatsapp\b", "ORDER_INSTRUCTION", "WHATSAPP"),
    TermDefinition(r"\bwhatsapp\b", "ORDER_INSTRUCTION", "WHATSAPP"),
    TermDefinition(r"واتساب", "ORDER_INSTRUCTION", "WHATSAPP"),
    TermDefinition(r"\bcommande inbox\b", "ORDER_INSTRUCTION", "DIRECT_MESSAGE_INBOX"),
    TermDefinition(r"\bcommande priv[eé]\b", "ORDER_INSTRUCTION", "DIRECT_MESSAGE_INBOX"),
    TermDefinition(r"\bprix inbox\b", "ORDER_INSTRUCTION", "DIRECT_MESSAGE_INBOX"),
    TermDefinition(r"\ben priv[eé]\b", "ORDER_INSTRUCTION", "DIRECT_MESSAGE_INBOX"),
    TermDefinition(r"\binbox\b", "ORDER_INSTRUCTION", "DIRECT_MESSAGE_INBOX"),
    TermDefinition(r"اطلب عبر الخاص", "ORDER_INSTRUCTION", "DIRECT_MESSAGE_INBOX"),
    TermDefinition(r"على الخاص", "ORDER_INSTRUCTION", "DIRECT_MESSAGE_INBOX"),
    TermDefinition(r"\bcontactez-nous\b", "ORDER_INSTRUCTION", "CONTACT_REQUIRED"),
    TermDefinition(r"\bcontactez nous\b", "ORDER_INSTRUCTION", "CONTACT_REQUIRED"),
    TermDefinition(r"اتصل بنا", "ORDER_INSTRUCTION", "CONTACT_REQUIRED"),
    TermDefinition(r"\bcommande\b", "ORDER_INSTRUCTION", "ORDER"),
    TermDefinition(r"\bcommander\b", "ORDER_INSTRUCTION", "ORDER"),
    TermDefinition(r"\bاطلب\b", "ORDER_INSTRUCTION", "ORDER"),
    TermDefinition(r"\bطلب\b", "ORDER_INSTRUCTION", "ORDER"),
    TermDefinition(r"\bللبيع\b", "ORDER_INSTRUCTION", "FOR_SALE"),
    # --- PAYMENT TERMS ---
    TermDefinition(r"\bpaiement [aà] la livraison\b", "PAYMENT", "CASH_ON_DELIVERY"),
    TermDefinition(r"الدفع عند الاستلام", "PAYMENT", "CASH_ON_DELIVERY"),
    TermDefinition(r"\bcash [aà] la livraison\b", "PAYMENT", "CASH_ON_DELIVERY"),
    TermDefinition(r"\bpaiement\b", "PAYMENT", "PAYMENT_TERMS"),
    TermDefinition(r"\bالدفع\b", "PAYMENT", "PAYMENT_TERMS"),
    # --- AVAILABILITY / STOCK SIGNALS ---
    TermDefinition(r"\ben stock\b", "AVAILABILITY", "IN_STOCK"),
    TermDefinition(r"\bstock limit[eé]\b", "AVAILABILITY", "LIMITED_STOCK"),
    TermDefinition(r"كمية محدودة", "AVAILABILITY", "LIMITED_STOCK"),
    TermDefinition(r"\bdisponible\b", "AVAILABILITY", "IN_STOCK"),
    TermDefinition(r"\bdispo\b", "AVAILABILITY", "IN_STOCK"),
    TermDefinition(r"\bمتوفر\b", "AVAILABILITY", "IN_STOCK"),
    TermDefinition(r"\bغير متوفر\b", "AVAILABILITY", "OUT_OF_STOCK"),
    TermDefinition(r"\bhors stock\b", "AVAILABILITY", "OUT_OF_STOCK"),
    TermDefinition(r"\brupture de stock\b", "AVAILABILITY", "OUT_OF_STOCK"),
    TermDefinition(r"\bstock\b", "AVAILABILITY", "IN_STOCK"),
    # --- PROMOTIONS & DISCOUNTS ---
    TermDefinition(r"\bpromo sp[eé]ciale\b", "PROMOTION", "SPECIAL_PROMO"),
    TermDefinition(r"\bpromotion\b", "PROMOTION", "PROMOTION"),
    TermDefinition(r"\bpromo\b", "PROMOTION", "PROMOTION"),
    TermDefinition(r"\br[eé]duction\b", "PROMOTION", "DISCOUNT"),
    TermDefinition(r"\bremise\b", "PROMOTION", "DISCOUNT"),
    TermDefinition(r"\bsolde\b", "PROMOTION", "SALE"),
    TermDefinition(r"\bتخفيض\b", "PROMOTION", "DISCOUNT"),
    TermDefinition(r"\bتخفيضات\b", "PROMOTION", "DISCOUNT"),
    TermDefinition(r"\bعرض\b", "PROMOTION", "SPECIAL_OFFER"),
    TermDefinition(r"\bعرض خاص\b", "PROMOTION", "SPECIAL_OFFER"),
]


class CommercialTermsExtractor:
    def __init__(self, terms: list[TermDefinition] | None = None) -> None:
        self.terms = terms or COMMERCIAL_DICTIONARY
        # Compile each pattern with case insensitivity
        self._compiled = [
            (re.compile(t.pattern, re.IGNORECASE), t.signal_type, t.normalized_value, t.confidence)
            for t in self.terms
        ]

    def extract(self, text: str) -> list[dict[str, Any]]:
        if not text:
            return []

        results: list[dict[str, Any]] = []
        # Track covered character spans to avoid overlapping sub-matches
        matched_spans: list[tuple[int, int]] = []
        seen_signals = set()

        for pattern, sig_type, norm_val, confidence in self._compiled:
            for match in pattern.finditer(text):
                start, end = match.span()
                # Check if this match overlaps an already matched longer span
                if any(start >= s and end <= e for s, e in matched_spans):
                    continue

                raw_match = match.group(0).strip()
                signal_key = (sig_type, norm_val, raw_match.lower())
                if signal_key in seen_signals:
                    continue

                seen_signals.add(signal_key)
                matched_spans.append((start, end))

                results.append(
                    {
                        "signal_type": sig_type,
                        "raw_value": raw_match,
                        "normalized_value": norm_val,
                        "confidence": confidence,
                        "evidence_text": raw_match,
                        "extraction_method": "dictionary_v1",
                    }
                )

        return results


commercial_terms_extractor = CommercialTermsExtractor()
