from app.models.page import Page
from app.models.post import Post
from app.models.signal import ExtractedSignal
from app.scoring.models import QuickScoreResult, ScoreExplanation


class QuickCommercialScorer:
    """
    Lightweight, deterministic, explainable commercial scorer for the QUICK phase.
    Does NOT use an LLM. Clamped to [0, 100].
    """

    def calculate(
        self,
        page: Page | None,
        posts: list[Post],
        signals: list[ExtractedSignal],
    ) -> QuickScoreResult:
        score = 0.0
        explanations: list[ScoreExplanation] = []
        total_posts = len(posts)

        # 1. Price analysis
        posts_with_prices = {
            sig.post_id for sig in signals if sig.signal_type == "PRICE" and sig.post_id
        }
        price_post_count = len(posts_with_prices)
        if price_post_count >= 2 or (total_posts > 0 and price_post_count / total_posts >= 0.3):
            score += 20.0
            ratio_str = (
                f"{price_post_count}/{total_posts}" if total_posts > 0 else str(price_post_count)
            )
            explanations.append(
                ScoreExplanation(
                    component="PRICE",
                    reason=f"{ratio_str} publication(s) contiennent des prix explicites",
                    weight=20.0,
                )
            )
        elif price_post_count == 1:
            score += 10.0
            explanations.append(
                ScoreExplanation(
                    component="PRICE",
                    reason="Des prix explicites sont détectés dans le contenu des publications",
                    weight=10.0,
                )
            )

        # 2. Commercial terms & product catalog wording
        commercial_terms = [sig for sig in signals if sig.signal_type == "COMMERCIAL_KEYWORD"]
        if (
            len(commercial_terms) >= 3
            or len({s.post_id for s in commercial_terms if s.post_id}) >= 2
        ):
            score += 20.0
            explanations.append(
                ScoreExplanation(
                    component="PRODUCT",
                    reason=f"Une terminologie commerciale ou de catalogue récurrente est détectée ({len(commercial_terms)} terme(s))",
                    weight=20.0,
                )
            )
        elif len(commercial_terms) >= 1:
            score += 10.0
            explanations.append(
                ScoreExplanation(
                    component="PRODUCT",
                    reason="Des mots-clés commerciaux ou de catalogue sont détectés",
                    weight=10.0,
                )
            )

        # 3. Order instructions
        order_signals = [sig for sig in signals if sig.signal_type == "ORDER_METHOD"]
        order_posts = {sig.post_id for sig in order_signals if sig.post_id}
        if len(order_posts) >= 2 or len(order_signals) >= 3:
            score += 20.0
            explanations.append(
                ScoreExplanation(
                    component="ORDER_INSTRUCTION",
                    reason=f"{len(order_posts)} publication(s) contiennent des instructions explicites de commande",
                    weight=20.0,
                )
            )
        elif len(order_signals) >= 1:
            score += 10.0
            explanations.append(
                ScoreExplanation(
                    component="ORDER_INSTRUCTION",
                    reason="Un appel ou une instruction de prise de commande est détecté",
                    weight=10.0,
                )
            )

        # 4. Delivery terms
        delivery_signals = [sig for sig in signals if sig.signal_type == "DELIVERY"]
        if delivery_signals:
            score += 15.0
            delivery_posts = len({sig.post_id for sig in delivery_signals if sig.post_id})
            explanations.append(
                ScoreExplanation(
                    component="DELIVERY",
                    reason=f"Des mentions de livraison et d’expédition sont détectées ({delivery_posts} publication(s))",
                    weight=15.0,
                )
            )

        # 5. Payment / Cash on delivery (COD)
        cod_signals = [
            sig
            for sig in signals
            if "livraison" in sig.raw_value.lower()
            or "cod" in sig.raw_value.lower()
            or (
                isinstance(sig.normalized_value, dict)
                and "payment" in sig.normalized_value.get("category", "")
            )
        ]
        if cod_signals:
            score += 10.0
            explanations.append(
                ScoreExplanation(
                    component="PAYMENT",
                    reason="Des instructions de paiement ou de paiement à la livraison sont détectées",
                    weight=10.0,
                )
            )

        # 6. Business contact info (phone/email in profile or post signals)
        has_profile_phone = bool(page and page.public_phone)
        has_post_phone = any(sig.signal_type == "PHONE" for sig in signals)
        if has_profile_phone or has_post_phone:
            score += 5.0
            phone_ref = page.public_phone if page and page.public_phone else "in posts"
            explanations.append(
                ScoreExplanation(
                    component="BUSINESS_CONTACT",
                    reason=f"Un numéro de contact professionnel ou WhatsApp est détecté ({phone_ref})",
                    weight=5.0,
                )
            )

        # 7. Promotional language
        promo_signals = [
            sig
            for sig in signals
            if sig.signal_type == "COMMERCIAL_KEYWORD"
            and any(
                p in sig.raw_value.lower()
                for p in ["promo", "solde", "remise", "reduction", "تخفيض", "عرض"]
            )
        ]
        if promo_signals:
            score += 5.0
            explanations.append(
                ScoreExplanation(
                    component="PROMOTION",
                    reason="Des mentions promotionnelles ou de remise sont détectées",
                    weight=5.0,
                )
            )

        # 8. Persistent commercial pattern (both prices and order/delivery co-occur)
        if price_post_count >= 1 and (order_signals or delivery_signals):
            score += 5.0
            explanations.append(
                ScoreExplanation(
                    component="COMMERCIAL_PATTERN",
                    reason="La présence de prix coïncide avec des canaux actifs de commande ou de livraison",
                    weight=5.0,
                )
            )

        clamped_score = min(max(round(score, 1), 0.0), 100.0)
        return QuickScoreResult(score=clamped_score, reasons=explanations)


quick_scorer = QuickCommercialScorer()
