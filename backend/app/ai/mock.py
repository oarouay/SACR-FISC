import re
from typing import Any

from app.ai.base import AIProvider
from app.ai.schemas import (
    ActivityType,
    BatchPostClassificationResponse,
    BusinessPattern,
    DeliveryPattern,
    GeminiCommercialAnalysis,
    PageSemanticAnalysis,
    PostCategory,
    PostSemanticClassification,
)


class MockGeminiProvider(AIProvider):
    """
    Simulated Gemini 2.5 Intelligence Provider for offline testing, local demos,
    and mock page evaluation without requiring live Google API credentials.
    Accurately handles Tunisian Arabic (Derja / Arabizi), French, and local commercial idioms.
    """

    @property
    def provider_name(self) -> str:
        return "gemini-mock"

    @property
    def model_name(self) -> str:
        return "gemini-2.5-flash-mock"

    def _analyze_text(self, text: str) -> dict[str, Any]:
        lower = text.lower()

        # Tunisian Derja / Arabizi & French indicators
        price_patterns = [
            r"\b\d+[\s]*(?:dt|tnd|dinars?|millimes?)\b",
            r"\bprix\b",
            r"\bb9adech\b",
            r"\bkaddech\b",
            r"\bsoum\b",
            r"\bpromo\b",
            r"\bsolde\b",
        ]
        has_price = any(re.search(p, lower) for p in price_patterns)

        delivery_patterns = [
            r"\blivraison\b",
            r"\btawsil\b",
            r"\b24\s*wilay(?:as?|et)\b",
            r"\baramex\b",
            r"\bdomicile\b",
            r"\bdispo\b",
            r"\bdisponible\b",
        ]
        has_delivery = any(re.search(p, lower) for p in delivery_patterns)

        payment_patterns = [
            r"\bd17\b",
            r"\bflouci\b",
            r"\bsob\s*flous\b",
            r"\bpaiement\s+(?:à|a)\s+la\s+livraison\b",
            r"\besp[èe]ces?\b",
            r"\bvirement\b",
            r"\bacompte\b",
        ]
        has_payment = any(re.search(p, lower) for p in payment_patterns)

        order_patterns = [
            r"\bcommander\b",
            r"\bcommande\b",
            r"\bmessage\s+priv[ée]\b",
            r"\bmp\b",
            r"\binbox\b",
            r"\bwhatsapp\b",
            r"\bcontactez\b",
            r"\bappel\b",
            r"\bt[ée]l\b",
        ]
        has_ordering = any(re.search(p, lower) for p in order_patterns)

        wholesale_patterns = [
            r"\bgros\b",
            r"\bgrossiste\b",
            r"\bquantit[ée]\b",
            r"\bcarton\b",
            r"\bsemi[\s-]gros\b",
        ]
        has_wholesale = any(re.search(p, lower) for p in wholesale_patterns)

        informal_patterns = [
            r"\bsans\s+facture\b",
            r"\bpas\s+de\s+facture\b",
            r"\bchouf\s+f\s+story\b",
            r"\bint[ée]ress[ée]\s+mp\b",
        ]
        has_informal = any(re.search(p, lower) for p in informal_patterns)

        is_commercial = (
            has_price
            or has_delivery
            or has_payment
            or (has_ordering and (has_delivery or has_price or "dispo" in lower))
        )

        return {
            "has_price": has_price,
            "has_delivery": has_delivery,
            "has_payment": has_payment,
            "has_ordering": has_ordering,
            "has_wholesale": has_wholesale,
            "has_informal": has_informal,
            "is_commercial": is_commercial,
        }

    async def resolve_ambiguity(
        self,
        page_name: str,
        page_description: str | None,
        page_category: str | None,
        posts: list[dict[str, Any]],
    ) -> GeminiCommercialAnalysis:
        allowed_ids = [p.get("post_id", "") for p in posts if p.get("post_id")]
        evidence_ids: list[str] = []
        reasons: list[str] = []

        commercial_posts_count = 0
        has_delivery = False
        has_payment = False
        has_ordering = False
        has_wholesale = False

        for post in posts:
            p_id = post.get("post_id", "")
            text = post.get("text", "")
            analysis = self._analyze_text(text)

            if analysis["is_commercial"]:
                commercial_posts_count += 1
                if p_id and p_id in allowed_ids and p_id not in evidence_ids:
                    evidence_ids.append(p_id)
            if analysis["has_delivery"]:
                has_delivery = True
            if analysis["has_payment"]:
                has_payment = True
            if analysis["has_ordering"]:
                has_ordering = True
            if analysis["has_wholesale"]:
                has_wholesale = True

        total_posts = max(len(posts), 1)
        ratio = commercial_posts_count / total_posts
        is_commercial = ratio >= 0.3 or commercial_posts_count >= 2

        activity_type: ActivityType = "PRODUCT_SALE"
        if has_wholesale:
            activity_type = "WHOLESALE"
        elif "service" in (page_category or "").lower():
            activity_type = "SERVICE"
        elif not is_commercial:
            activity_type = "NON_COMMERCIAL"

        confidence = min(0.95, max(0.60, ratio * 0.9 + 0.1)) if is_commercial else 0.85

        if is_commercial:
            reasons.append(
                f"Des offres commerciales récurrentes sont observées dans {commercial_posts_count}/{len(posts)} publications analysées."
            )
            if has_delivery:
                reasons.append("Des éléments attestent une activité de livraison et de logistique sur le territoire tunisien.")
            if has_payment:
                reasons.append(
                    "Des modalités de paiement sont mentionnées, notamment le paiement à la livraison ou D17."
                )
            if has_ordering:
                reasons.append(
                    "Des canaux directs de prise de commande sont observés par message privé ou WhatsApp."
                )
        else:
            reasons.append(
                "Les publications analysées présentent principalement un contenu informatif, personnel ou non commercial."
            )

        return GeminiCommercialAnalysis(
            is_commercial=is_commercial,
            confidence=confidence,
            activity_type=activity_type,
            recurring_business_pattern=commercial_posts_count >= 2,
            ordering_detected=has_ordering,
            delivery_detected=has_delivery,
            payment_detected=has_payment,
            promotion_detected=ratio > 0.4,
            business_type=page_category or "Commerce électronique / page commerciale",
            products_or_services=[page_name] if is_commercial else [],
            evidence_post_ids=evidence_ids[:5],
            reasons=reasons,
        )

    async def classify_posts(
        self,
        posts: list[dict[str, Any]],
    ) -> BatchPostClassificationResponse:
        results: list[PostSemanticClassification] = []

        for p in posts:
            p_id = p.get("post_id", "")
            text = p.get("text", "")
            analysis = self._analyze_text(text)

            categories: list[PostCategory] = []
            indicators: list[str] = []

            if analysis["has_price"]:
                categories.append("PRICE_INFORMATION")
                indicators.append("Prix ou devise mentionné")
            if analysis["has_delivery"]:
                categories.append("DELIVERY_INFORMATION")
                indicators.append("Mots-clés relatifs à la livraison ou à l’expédition détectés")
            if analysis["has_payment"]:
                categories.append("PAYMENT_INFORMATION")
                indicators.append("Modalités de paiement détectées (D17, paiement à la livraison)")
            if analysis["has_ordering"]:
                categories.append("ORDER_REQUEST")
                indicators.append("Appel à la commande détecté (Inbox, message privé, WhatsApp)")
            if analysis["is_commercial"]:
                categories.append("PRODUCT_OFFER")
                indicators.append("Offre de produits commerciaux identifiée")
            else:
                categories.append("GENERAL_CONTENT")
                indicators.append("Contenu textuel non transactionnel")

            conf = 0.90 if analysis["is_commercial"] else 0.80

            results.append(
                PostSemanticClassification(
                    post_id=p_id,
                    categories=categories,
                    commercial=analysis["is_commercial"],
                    confidence=conf,
                    indicators=indicators,
                )
            )

        return BatchPostClassificationResponse(posts=results)

    async def analyze_page(
        self,
        page_name: str,
        page_description: str | None,
        page_category: str | None,
        deterministic_summary: dict[str, Any],
        representative_posts: list[dict[str, Any]],
        activity_period: str | None = None,
    ) -> PageSemanticAnalysis:
        allowed_ids = [p.get("post_id", "") for p in representative_posts if p.get("post_id")]
        evidence_ids: list[str] = []
        reasons: list[str] = []
        sales_channels: list[str] = ["Facebook Page"]

        commercial_count = 0
        has_delivery = False
        has_wholesale = False
        has_informal = False

        for post in representative_posts:
            p_id = post.get("post_id", "")
            text = post.get("text", "")
            analysis = self._analyze_text(text)
            if analysis["is_commercial"]:
                commercial_count += 1
                if p_id and p_id in allowed_ids and p_id not in evidence_ids:
                    evidence_ids.append(p_id)
            if analysis["has_delivery"]:
                has_delivery = True
            if analysis["has_wholesale"]:
                has_wholesale = True
            if analysis["has_informal"]:
                has_informal = True
            if analysis["has_ordering"]:
                if "WhatsApp" not in sales_channels and (
                    "whatsapp" in text.lower() or "+216" in text
                ):
                    sales_channels.append("WhatsApp")
                if "Messenger" not in sales_channels and (
                    "mp" in text.lower() or "inbox" in text.lower()
                ):
                    sales_channels.append("Facebook Messenger")

        is_recurrent = (
            commercial_count >= 2 or deterministic_summary.get("total_posts_with_prices", 0) >= 2
        )

        pattern: BusinessPattern = (
            "RECURRING_COMMERCIAL_ACTIVITY" if is_recurrent else "OCCASIONAL_COMMERCIAL_ACTIVITY"
        )
        if commercial_count == 0 and deterministic_summary.get("total_posts", 0) > 3:
            pattern = "COMMUNITY_OR_CONTENT"

        delivery_pattern: DeliveryPattern = "NATIONWIDE" if has_delivery else "LOCAL_REGIONAL"
        if not has_delivery:
            delivery_pattern = "NONE_OR_PICKUP"

        confidence = 0.92 if is_recurrent else 0.75

        reasons.append(
            f"La page présente un profil d’activité commerciale observé à partir de {commercial_count} échantillon(s) de publication(s)."
        )
        if has_delivery:
            reasons.append(
                "Des opérations de livraison nationale ou régionale sont étayées par les éléments logistiques des publications."
            )
        if has_wholesale:
            reasons.append("Des éléments indiquent une activité de vente en gros ou de distribution en volume.")
        if has_informal:
            reasons.append(
                "Des indices de transactions informelles ou non facturées sont observés dans les échanges publiés."
            )

        return PageSemanticAnalysis(
            business_pattern=pattern,
            commercial_confidence=confidence,
            business_type=page_category or "Commerce électronique / activité de vente au détail",
            products_or_services=[page_name],
            sales_channels=sales_channels,
            delivery_pattern=delivery_pattern,
            recurring_activity=is_recurrent,
            evidence_post_ids=evidence_ids[:5],
            reasons=reasons,
        )
