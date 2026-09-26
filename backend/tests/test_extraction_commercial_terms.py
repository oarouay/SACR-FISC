from app.extraction.commercial_terms import commercial_terms_extractor


def test_french_commercial_terms():
    text = "Grande promotion sur nos articles en stock. Paiement sécurisé et contactez-nous pour commander."
    signals = commercial_terms_extractor.extract(text)
    types = [s["signal_type"] for s in signals]
    assert "PROMOTION" in types
    assert "AVAILABILITY" in types
    assert "PAYMENT" in types
    assert "ORDER_INSTRUCTION" in types


def test_arabic_commercial_terms():
    text = "عرض خاص وتخفيض ممتاز، للبيع هاتف ذكي متوفر الآن. اطلب عبر الخاص مع الدفع عند الاستلام."
    signals = commercial_terms_extractor.extract(text)
    types = [s["signal_type"] for s in signals]
    assert "PROMOTION" in types
    assert "AVAILABILITY" in types
    assert "ORDER_INSTRUCTION" in types
    assert "PAYMENT" in types


def test_tunisian_social_commerce_expressions():
    text = "Nouveautés dispo! Commande inbox ou commande privé. Livraison toute la Tunisie et paiement à la livraison."
    signals = commercial_terms_extractor.extract(text)

    norms = [s["normalized_value"] for s in signals]
    assert "TUNISIA_NATIONWIDE" in norms
    assert "CASH_ON_DELIVERY" in norms
    assert "DIRECT_MESSAGE_INBOX" in norms
    assert "IN_STOCK" in norms


def test_delivery_24_gouvernorats():
    text = "Livraison 24 gouvernorats dispo de suite."
    signals = commercial_terms_extractor.extract(text)
    norms = [s["normalized_value"] for s in signals]
    assert "TUNISIA_24_GOVERNORATES" in norms


def test_multi_word_precedence():
    # 'livraison toute la tunisie' should match as a single span, not separately trigger generic 'livraison'
    text = "Livraison toute la Tunisie rapide."
    signals = commercial_terms_extractor.extract(text)
    delivery_signals = [s for s in signals if s["signal_type"] == "DELIVERY"]
    # Only one dominant delivery signal
    assert len(delivery_signals) == 1
    assert delivery_signals[0]["normalized_value"] == "TUNISIA_NATIONWIDE"
