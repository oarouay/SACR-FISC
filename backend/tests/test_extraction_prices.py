from app.extraction.prices import PriceExtractor


def test_extract_tunisian_prices():
    test_cases = [
        ("Promotion exceptionnelle: 89 DT seulement!", 89, "TND"),
        ("Prix du pack: 89 TND avec livraison", 89, "TND"),
        ("Article de luxe: 89,500 DT stock limité", 89.5, "TND"),
        ("Article promo: 89.500 DT disponible", 89.5, "TND"),
        ("عرض خاص 89 دينار توصيل سريع", 89, "TND"),
        ("السعر: 89 د.ت والدفع عند الاستلام", 89, "TND"),
        ("Prix: 120 DT en boutique", 120, "TND"),
    ]

    for text, expected_amount, expected_curr in test_cases:
        signals = PriceExtractor.extract(text)
        assert len(signals) >= 1, f"No price detected in: '{text}'"
        sig = signals[0]
        assert sig["signal_type"] == "PRICE"
        assert sig["normalized_value"]["amount"] == expected_amount, f"Amount mismatch in '{text}'"
        assert sig["normalized_value"]["currency"] == expected_curr
        assert sig["confidence"] == 1.0


def test_extract_multiple_prices():
    text = "Veste à 120 DT et pantalon à 65 DT. Ne ratez pas l'offre!"
    signals = PriceExtractor.extract(text)
    assert len(signals) == 2
    amounts = [s["normalized_value"]["amount"] for s in signals]
    assert 120 in amounts
    assert 65 in amounts


def test_empty_or_no_price():
    assert PriceExtractor.extract("") == []
    assert PriceExtractor.extract("Pas de prix mentionné dans ce post") == []
