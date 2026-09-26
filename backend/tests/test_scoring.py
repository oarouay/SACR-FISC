import uuid

from app.models.enums import RegistryStatus
from app.models.page import Page
from app.models.post import Post
from app.models.registry_verification import RegistryVerification
from app.models.signal import ExtractedSignal
from app.scoring.priority import priority_scorer
from app.scoring.quick import quick_scorer


def test_quick_scorer_low_commercial():
    page = Page(
        id=uuid.uuid4(),
        canonical_url="https://www.facebook.com/personal-blog",
        name="Personal Life",
        description="Just sharing my personal thoughts and family photos.",
    )
    posts = [
        Post(
            id=uuid.uuid4(),
            page_id=page.id,
            text="Had a great walk in the park today with friends!",
        )
    ]
    signals = []

    res = quick_scorer.calculate(page, posts, signals)
    assert res.score == 0.0
    assert len(res.reasons) == 0


def test_quick_scorer_high_commercial():
    page_id = uuid.uuid4()
    p1_id = uuid.uuid4()
    p2_id = uuid.uuid4()

    page = Page(
        id=page_id,
        canonical_url="https://www.facebook.com/tunis-boutique",
        name="Tunis Boutique",
        public_phone="+21698123456",
        description="Boutique en ligne Tunisie. Vente de vêtements et accessoires.",
    )
    posts = [
        Post(
            id=p1_id,
            page_id=page_id,
            text="Robe d'été magnifique Prix 89 DT. Livraison 58 wilayas!",
        ),
        Post(
            id=p2_id, page_id=page_id, text="Arrivage stock limité! 120 DT. Commande par WhatsApp."
        ),
    ]
    signals = [
        ExtractedSignal(
            page_id=page_id,
            post_id=p1_id,
            signal_type="PRICE",
            raw_value="89 DT",
            normalized_value={"amount": 89.0, "currency": "TND"},
            evidence_text="89 DT",
        ),
        ExtractedSignal(
            page_id=page_id,
            post_id=p2_id,
            signal_type="PRICE",
            raw_value="120 DT",
            normalized_value={"amount": 120.0, "currency": "TND"},
            evidence_text="120 DT",
        ),
        ExtractedSignal(
            page_id=page_id,
            post_id=p1_id,
            signal_type="DELIVERY",
            raw_value="Livraison",
            normalized_value="Livraison",
            evidence_text="Livraison",
        ),
        ExtractedSignal(
            page_id=page_id,
            post_id=p2_id,
            signal_type="ORDER_METHOD",
            raw_value="Commande par WhatsApp",
            normalized_value="Commande par WhatsApp",
            evidence_text="Commande par WhatsApp",
        ),
        ExtractedSignal(
            page_id=page_id,
            post_id=p2_id,
            signal_type="COMMERCIAL_KEYWORD",
            raw_value="stock",
            normalized_value="stock",
            evidence_text="stock",
        ),
        ExtractedSignal(
            page_id=page_id,
            post_id=p2_id,
            signal_type="COMMERCIAL_KEYWORD",
            raw_value="Boutique",
            normalized_value="Boutique",
            evidence_text="Boutique",
        ),
        ExtractedSignal(
            page_id=page_id,
            post_id=p2_id,
            signal_type="COMMERCIAL_KEYWORD",
            raw_value="vente",
            normalized_value="vente",
            evidence_text="vente",
        ),
        ExtractedSignal(
            page_id=page_id,
            post_id=None,
            signal_type="PHONE",
            raw_value="+21698123456",
            normalized_value="+21698123456",
            evidence_text="+21698123456",
        ),
    ]

    res = quick_scorer.calculate(page, posts, signals)
    assert res.score >= 60.0  # Qualifies for DEEP crawl threshold
    assert any("prix" in r for r in res.reason_strings)
    assert any("commande" in r.lower() for r in res.reason_strings)
    assert any("livraison" in r.lower() for r in res.reason_strings)


def test_review_priority_score_formula_and_reasons():
    page_id = uuid.uuid4()
    p1 = uuid.uuid4()
    p2 = uuid.uuid4()

    page = Page(
        id=page_id,
        canonical_url="https://www.facebook.com/tunis-commerce",
        name="Tunis Commerce Express",
        public_phone="+21671123456",
        website="https://tunis-store.tn",
        public_address="Avenue Habib Bourguiba, Tunis",
    )
    posts = [
        Post(id=p1, page_id=page_id, text="Article A 55 DT livraison toute la tunisie"),
        Post(
            id=p2,
            page_id=page_id,
            text="Article B 95 DT paiement a la livraison commande en message prive",
        ),
    ]
    signals = [
        ExtractedSignal(
            page_id=page_id,
            post_id=p1,
            signal_type="PRICE",
            raw_value="55 DT",
            normalized_value={"amount": 55.0, "currency": "TND"},
            evidence_text="55 DT",
        ),
        ExtractedSignal(
            page_id=page_id,
            post_id=p2,
            signal_type="PRICE",
            raw_value="95 DT",
            normalized_value={"amount": 95.0, "currency": "TND"},
            evidence_text="95 DT",
        ),
        ExtractedSignal(
            page_id=page_id,
            post_id=p1,
            signal_type="DELIVERY",
            raw_value="toute la tunisie",
            normalized_value="toute la tunisie",
            evidence_text="toute la tunisie",
        ),
        ExtractedSignal(
            page_id=page_id,
            post_id=p2,
            signal_type="DELIVERY",
            raw_value="paiement a la livraison",
            normalized_value="paiement a la livraison",
            evidence_text="paiement a la livraison",
        ),
        ExtractedSignal(
            page_id=page_id,
            post_id=p2,
            signal_type="ORDER_METHOD",
            raw_value="commande en message prive",
            normalized_value="commande en message prive",
            evidence_text="commande en message prive",
        ),
        ExtractedSignal(
            page_id=page_id,
            post_id=p1,
            signal_type="COMMERCIAL_KEYWORD",
            raw_value="stock",
            normalized_value="stock",
            evidence_text="stock",
        ),
        ExtractedSignal(
            page_id=page_id,
            post_id=p2,
            signal_type="COMMERCIAL_KEYWORD",
            raw_value="promo",
            normalized_value="promo",
            evidence_text="promo",
        ),
        ExtractedSignal(
            page_id=page_id,
            post_id=None,
            signal_type="PHONE",
            raw_value="+21671123456",
            normalized_value="+21671123456",
            evidence_text="+21671123456",
        ),
    ]

    res = priority_scorer.calculate(page, posts, signals)

    # Verify mathematical formula: 0.45 * Comm + 0.30 * Tx + 0.25 * Econ
    expected = round(
        0.45 * res.commercial_activity.score
        + 0.30 * res.transaction_evidence.score
        + 0.25 * res.economic_activity.score,
        1,
    )
    assert res.review_priority == expected
    assert 0.0 <= res.review_priority <= 100.0

    # Verify explainability
    all_reasons = res.all_explanations
    assert len(all_reasons) > 0
    components = {r.component for r in all_reasons}
    assert "COMMERCIAL_ACTIVITY" in components
    assert "TRANSACTION_EVIDENCE" in components
    assert "ECONOMIC_ACTIVITY" in components


def test_registry_status_not_checked_by_default_and_not_negative():
    page_id = uuid.uuid4()
    reg = RegistryVerification(
        page_id=page_id,
        status=RegistryStatus.NOT_CHECKED,
    )
    assert reg.status == RegistryStatus.NOT_CHECKED
    assert reg.status != RegistryStatus.NO_MATCH_CONFIRMED

    # Priority scorer does not accept or factor in registry status
    page = Page(id=page_id, canonical_url="https://facebook.com/shop", name="Shop")
    posts = []
    signals = []
    res = priority_scorer.calculate(page, posts, signals)
    # The score must be 0 for an empty page, regardless of registry status
    assert res.review_priority == 0.0
