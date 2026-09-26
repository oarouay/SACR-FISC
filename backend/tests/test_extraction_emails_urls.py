from app.extraction.emails import EmailExtractor
from app.extraction.urls import URLExtractor


def test_extract_emails():
    text = "Pour commander écrivez à Contact@TunisShop.TN ou Support@STORE.COM. Merci!"
    signals = EmailExtractor.extract(text)
    assert len(signals) == 2

    emails = [s["normalized_value"] for s in signals]
    assert "contact@tunisshop.tn" in emails
    assert "support@store.com" in emails
    assert signals[0]["signal_type"] == "EMAIL"


def test_extract_urls():
    text = (
        "Visitez notre site https://tunis-fashion.tn/shop ou commandez sur "
        "wa.me/21698123456 ou remplissez https://forms.gle/xyz123"
    )
    signals = URLExtractor.extract(text)
    assert len(signals) == 3

    categories = {s["normalized_value"]["category"] for s in signals}
    assert "WEBSITE" in categories
    assert "WHATSAPP_LINK" in categories
    assert "ORDER_FORM" in categories
