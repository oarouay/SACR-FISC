from app.extraction.phones import PhoneExtractor


def test_normalize_tunisian_phones():
    test_cases = [
        ("98 123 456", "+21698123456"),
        ("98123456", "+21698123456"),
        ("+216 98 123 456", "+21698123456"),
        ("00216 98123456", "+21698123456"),
        ("(+216) 98 123 456", "+21698123456"),
        ("+216-98-123-456", "+21698123456"),
        ("22 334 455", "+21622334455"),
        ("50.998.877", "+21650998877"),
        ("71 112 233", "+21671112233"),
    ]

    for raw, expected in test_cases:
        normalized = PhoneExtractor.normalize_phone(raw)
        assert normalized == expected, f"Failed for {raw}: got {normalized}, expected {expected}"


def test_extract_phones_from_post_text():
    text = (
        "Nouvelle collection disponible! Contactez-nous sur WhatsApp au 98 123 456 "
        "ou par téléphone fixe 71 112 233. Bureau: +216 98 123 456 (doublon)."
    )
    signals = PhoneExtractor.extract(text)
    assert len(signals) == 2  # Deduplicates same normalized phone

    phones = [s["normalized_value"] for s in signals]
    assert "+21698123456" in phones
    assert "+21671112233" in phones

    first_sig = signals[0]
    assert first_sig["signal_type"] == "PHONE"
    assert first_sig["confidence"] == 1.0


def test_extract_phones_empty_or_no_match():
    assert PhoneExtractor.extract("") == []
    assert PhoneExtractor.extract("Aucun numéro ici.") == []
