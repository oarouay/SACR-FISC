import uuid

from app.extraction.pipeline import signal_pipeline


def test_section_14_specification_example():
    """
    Direct test for the canonical example in Section 14 of the MVP requirements:
    "Promotion 89 DT. Livraison toute la Tunisie. Commande WhatsApp +216 98 123 456"
    """
    text = "Promotion 89 DT. Livraison toute la Tunisie. Commande WhatsApp +216 98 123 456"
    page_id = uuid.uuid4()
    post_id = uuid.uuid4()

    signals = signal_pipeline.extract_signals(text=text, page_id=page_id, post_id=post_id)

    signals_by_type = {s["signal_type"]: s for s in signals}

    # 1. Price
    assert "PRICE" in signals_by_type
    price_sig = signals_by_type["PRICE"]
    assert price_sig["raw_value"] == "89 DT"
    assert price_sig["normalized_value"] == {"amount": 89, "currency": "TND"}
    assert price_sig["confidence"] == 1.0

    # 2. Delivery
    assert "DELIVERY" in signals_by_type
    deliv_sig = signals_by_type["DELIVERY"]
    assert deliv_sig["normalized_value"] == "TUNISIA_NATIONWIDE"
    assert deliv_sig["raw_value"].lower() == "livraison toute la tunisie"

    # 3. Order Instruction
    assert "ORDER_INSTRUCTION" in signals_by_type
    order_sig = signals_by_type["ORDER_INSTRUCTION"]
    assert order_sig["normalized_value"] == "WHATSAPP"
    assert "whatsapp" in order_sig["raw_value"].lower()

    # 4. Phone
    assert "PHONE" in signals_by_type
    phone_sig = signals_by_type["PHONE"]
    assert phone_sig["raw_value"] == "+216 98 123 456"
    assert phone_sig["normalized_value"] == "+21698123456"
    assert phone_sig["confidence"] == 1.0

    # Verify ID attachment
    for sig in signals:
        assert sig["page_id"] == page_id
        assert sig["post_id"] == post_id
        assert sig["extraction_version"] == "1.0.0"
