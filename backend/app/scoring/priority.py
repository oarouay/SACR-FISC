from app.ai.schemas import PageSemanticAnalysis
from app.core.config import settings
from app.models.page import Page
from app.models.post import Post
from app.models.signal import ExtractedSignal
from app.scoring.models import ComponentScore, ReviewScoreResult, ScoreExplanation


class ReviewPriorityScorer:
    """
    Computes explainable Review Priority Score:
    ReviewPriority = 0.45 * CommercialActivity + 0.30 * TransactionEvidence + 0.25 * EconomicActivity
    Explicitly independent of registry verification status.
    """

    def calculate(
        self,
        page: Page | None,
        posts: list[Post],
        signals: list[ExtractedSignal],
        ai_analysis: PageSemanticAnalysis | None = None,
    ) -> ReviewScoreResult:
        comm_score, comm_reasons = self._calc_commercial_activity(posts, signals, ai_analysis)
        tx_score, tx_reasons = self._calc_transaction_evidence(page, posts, signals, ai_analysis)
        econ_score, econ_reasons = self._calc_economic_activity(page, posts, signals, ai_analysis)

        weighted = 0.45 * comm_score.score + 0.30 * tx_score.score + 0.25 * econ_score.score
        review_priority = min(max(round(weighted, 1), 0.0), 100.0)

        return ReviewScoreResult(
            commercial_activity=comm_score,
            transaction_evidence=tx_score,
            economic_activity=econ_score,
            review_priority=review_priority,
            scoring_version=settings.SCORING_VERSION,
        )

    def _calc_commercial_activity(
        self,
        posts: list[Post],
        signals: list[ExtractedSignal],
        ai_analysis: PageSemanticAnalysis | None = None,
    ) -> tuple[ComponentScore, list[ScoreExplanation]]:
        score = 0.0
        reasons: list[ScoreExplanation] = []
        total_posts = len(posts)

        # 1. Price density & repetition
        price_signals = [s for s in signals if s.signal_type == "PRICE"]
        posts_with_prices = {s.post_id for s in price_signals if s.post_id}
        price_post_cnt = len(posts_with_prices)

        if price_post_cnt >= 15:
            score += 35.0
            reasons.append(
                ScoreExplanation(
                    component="COMMERCIAL_ACTIVITY",
                    reason=f"Forte densité de publications avec prix ({price_post_cnt}/{total_posts})",
                    weight=35.0,
                )
            )
        elif price_post_cnt >= 5:
            score += 25.0
            reasons.append(
                ScoreExplanation(
                    component="COMMERCIAL_ACTIVITY",
                    reason=f"Répétition d’annonces tarifées observée ({price_post_cnt}/{total_posts} publications)",
                    weight=25.0,
                )
            )
        elif price_post_cnt >= 1:
            score += 15.0
            reasons.append(
                ScoreExplanation(
                    component="COMMERCIAL_ACTIVITY",
                    reason=f"Des indices tarifaires observables sont détectés ({price_post_cnt} publication(s))",
                    weight=15.0,
                )
            )

        # 2. Commercial catalog terms
        commercial_terms = [s for s in signals if s.signal_type == "COMMERCIAL_KEYWORD"]
        term_count = len(commercial_terms)
        if term_count >= 10:
            score += 25.0
            reasons.append(
                ScoreExplanation(
                    component="COMMERCIAL_ACTIVITY",
                    reason=f"Terminologie commerciale et de catalogue abondante ({term_count} occurrence(s))",
                    weight=25.0,
                )
            )
        elif term_count >= 3:
            score += 15.0
            reasons.append(
                ScoreExplanation(
                    component="COMMERCIAL_ACTIVITY",
                    reason=f"Terminologie commerciale fréquente détectée ({term_count} occurrence(s))",
                    weight=15.0,
                )
            )
        elif term_count >= 1:
            score += 8.0
            reasons.append(
                ScoreExplanation(
                    component="COMMERCIAL_ACTIVITY",
                    reason="Des indices fondés sur des mots-clés commerciaux sont présents",
                    weight=8.0,
                )
            )

        # 3. Promotions & Stock announcements
        stock_signals = [
            s
            for s in commercial_terms
            if any(k in s.raw_value.lower() for k in ["stock", "disponible", "arrivage", "nouveau"])
        ]
        if stock_signals:
            score += 15.0
            reasons.append(
                ScoreExplanation(
                    component="COMMERCIAL_ACTIVITY",
                    reason=f"Annonces de stock et de réassort actives ({len(stock_signals)} mention(s))",
                    weight=15.0,
                )
            )

        promo_signals = [
            s
            for s in commercial_terms
            if any(
                k in s.raw_value.lower() for k in ["promo", "solde", "remise", "reduction", "تخفيض"]
            )
        ]
        if promo_signals:
            score += 15.0
            reasons.append(
                ScoreExplanation(
                    component="COMMERCIAL_ACTIVITY",
                    reason=f"Formulations relatives aux promotions et remises ({len(promo_signals)} mention(s))",
                    weight=15.0,
                )
            )

        # 4. Catalog-like post consistency
        if total_posts >= 5 and (price_post_cnt / total_posts) >= 0.5:
            score += 10.0
            reasons.append(
                ScoreExplanation(
                    component="COMMERCIAL_ACTIVITY",
                    reason=f"La majorité du contenu présente une structure de catalogue de vente ({round((price_post_cnt / total_posts) * 100)} %) ",
                    weight=10.0,
                )
            )

        # 5. Gemini Semantic Enrichment
        if (
            ai_analysis
            and ai_analysis.commercial_confidence >= 0.85
            and ai_analysis.recurring_activity
        ):
            boost = 15.0
            score += boost
            reasons.append(
                ScoreExplanation(
                    component="COMMERCIAL_ACTIVITY",
                    reason=f"Le profil sémantique est cohérent avec {ai_analysis.business_type or 'une activité de vente en ligne'}",
                    weight=boost,
                    source="GEMINI",
                    evidence_post_ids=ai_analysis.evidence_post_ids,
                )
            )

        clamped = min(max(round(score, 1), 0.0), 100.0)
        return ComponentScore(score=clamped, reasons=reasons), reasons

    def _calc_transaction_evidence(
        self,
        page: Page | None,
        posts: list[Post],
        signals: list[ExtractedSignal],
        ai_analysis: PageSemanticAnalysis | None = None,
    ) -> tuple[ComponentScore, list[ScoreExplanation]]:

        score = 0.0
        reasons: list[ScoreExplanation] = []

        # 1. Order instructions & CTAs
        order_signals = [s for s in signals if s.signal_type == "ORDER_METHOD"]
        order_post_cnt = len({s.post_id for s in order_signals if s.post_id})
        if order_post_cnt >= 10:
            score += 30.0
            reasons.append(
                ScoreExplanation(
                    component="TRANSACTION_EVIDENCE",
                    reason=f"Instructions de prise de commande récurrentes ({order_post_cnt} publication(s))",
                    weight=30.0,
                )
            )
        elif order_post_cnt >= 3:
            score += 20.0
            reasons.append(
                ScoreExplanation(
                    component="TRANSACTION_EVIDENCE",
                    reason=f"Appels fréquents à la prise de commande ({order_post_cnt} publication(s))",
                    weight=20.0,
                )
            )
        elif order_post_cnt >= 1:
            score += 10.0
            reasons.append(
                ScoreExplanation(
                    component="TRANSACTION_EVIDENCE",
                    reason="Des instructions de commande ou de réservation directe sont détectées",
                    weight=10.0,
                )
            )

        # 2. Delivery channels
        delivery_signals = [s for s in signals if s.signal_type == "DELIVERY"]
        delivery_post_cnt = len({s.post_id for s in delivery_signals if s.post_id})
        if delivery_post_cnt >= 5:
            score += 25.0
            reasons.append(
                ScoreExplanation(
                    component="TRANSACTION_EVIDENCE",
                    reason=f"Mentions d’un service de livraison actif dans les publications ({delivery_post_cnt})",
                    weight=25.0,
                )
            )
        elif delivery_post_cnt >= 1:
            score += 15.0
            reasons.append(
                ScoreExplanation(
                    component="TRANSACTION_EVIDENCE",
                    reason="Des modalités de livraison et d’expédition sont détectées",
                    weight=15.0,
                )
            )

        # 3. Cash on Delivery (COD) / Payment instructions
        cod_signals = [
            s
            for s in signals
            if "livraison" in s.raw_value.lower()
            or "cod" in s.raw_value.lower()
            or "espece" in s.raw_value.lower()
            or "paiement" in s.raw_value.lower()
        ]
        if cod_signals:
            score += 20.0
            reasons.append(
                ScoreExplanation(
                    component="TRANSACTION_EVIDENCE",
                    reason="Des instructions directes de paiement ou de paiement à la livraison sont établies",
                    weight=20.0,
                )
            )

        # 4. WhatsApp / phone business contact channel
        has_phone = bool(page and page.public_phone) or any(
            s.signal_type == "PHONE" for s in signals
        )
        if has_phone:
            score += 15.0
            phone_val = page.public_phone if page and page.public_phone else "in posts"
            reasons.append(
                ScoreExplanation(
                    component="TRANSACTION_EVIDENCE",
                    reason=f"Un contact direct du vendeur par téléphone ou WhatsApp est actif ({phone_val})",
                    weight=15.0,
                )
            )

        # 5. External checkout / store URLs
        url_signals = [s for s in signals if s.signal_type == "URL"]
        store_urls = [
            u
            for u in url_signals
            if not any(
                dom in u.raw_value.lower() for dom in ["facebook.com", "instagram.com", "fb.me"]
            )
        ]
        if store_urls or (page and page.website):
            score += 10.0
            site_val = page.website if (page and page.website) else store_urls[0].raw_value
            reasons.append(
                ScoreExplanation(
                    component="TRANSACTION_EVIDENCE",
                    reason=f"Un site marchand ou une page de destination externe est associé ({site_val})",
                    weight=10.0,
                )
            )

        # 6. Gemini Semantic Confirmation
        if ai_analysis and ai_analysis.delivery_pattern == "NATIONWIDE":
            boost = 10.0
            score += boost
            reasons.append(
                ScoreExplanation(
                    component="TRANSACTION_EVIDENCE",
                    reason="L’analyse sémantique confirme un profil de couverture de livraison nationale",
                    weight=boost,
                    source="GEMINI",
                    evidence_post_ids=ai_analysis.evidence_post_ids,
                )
            )

        clamped = min(max(round(score, 1), 0.0), 100.0)
        return ComponentScore(score=clamped, reasons=reasons), reasons

    def _calc_economic_activity(
        self,
        page: Page | None,
        posts: list[Post],
        signals: list[ExtractedSignal],
        ai_analysis: PageSemanticAnalysis | None = None,
    ) -> tuple[ComponentScore, list[ScoreExplanation]]:

        score = 0.0
        reasons: list[ScoreExplanation] = []
        total_posts = len(posts)

        # 1. Commercial post volume (Scale indicator)
        price_signals = [s for s in signals if s.signal_type == "PRICE"]
        numeric_prices: list[float] = []
        for s in price_signals:
            if isinstance(s.normalized_value, dict) and "amount" in s.normalized_value:
                try:
                    numeric_prices.append(float(s.normalized_value["amount"]))
                except (ValueError, TypeError):
                    pass
            elif isinstance(s.normalized_value, (int, float)):
                numeric_prices.append(float(s.normalized_value))

        if total_posts >= 40:
            score += 25.0
            reasons.append(
                ScoreExplanation(
                    component="ECONOMIC_ACTIVITY",
                    reason=f"Échelle importante du catalogue ({total_posts} publications distinctes conservées)",
                    weight=25.0,
                )
            )
        elif total_posts >= 15:
            score += 15.0
            reasons.append(
                ScoreExplanation(
                    component="ECONOMIC_ACTIVITY",
                    reason=f"Volume modéré du catalogue ({total_posts} publications distinctes conservées)",
                    weight=15.0,
                )
            )
        elif total_posts >= 5:
            score += 10.0
            reasons.append(
                ScoreExplanation(
                    component="ECONOMIC_ACTIVITY",
                    reason=f"Historique actif de publications ({total_posts})",
                    weight=10.0,
                )
            )

        # 2. Observed Price Range and Distribution
        if numeric_prices:
            min_p = min(numeric_prices)
            max_p = max(numeric_prices)
            score += 25.0
            reasons.append(
                ScoreExplanation(
                    component="ECONOMIC_ACTIVITY",
                    reason=f"La fourchette de prix extraite s’étend de {min_p:.1f} TND à {max_p:.1f} TND",
                    weight=25.0,
                )
            )

        # 3. Geographic Delivery Coverage (National / Multi-region)
        delivery_signals = [s for s in signals if s.signal_type == "DELIVERY"]
        nationwide = any(
            any(
                k in s.raw_value.lower()
                for k in ["toute la tunisie", "24", "gouvernorat", "domicile"]
            )
            for s in delivery_signals
        )
        if nationwide:
            score += 25.0
            reasons.append(
                ScoreExplanation(
                    component="ECONOMIC_ACTIVITY",
                    reason="Une couverture de livraison nationale ou multirégionale est explicitement indiquée",
                    weight=25.0,
                )
            )
        elif delivery_signals:
            score += 15.0
            reasons.append(
                ScoreExplanation(
                    component="ECONOMIC_ACTIVITY",
                    reason="Des opérations de livraison régionale sont indiquées",
                    weight=15.0,
                )
            )

        # 4. Wholesale or multiple locations
        wholesale_signals = [
            s
            for s in signals
            if any(
                k in s.raw_value.lower()
                for k in ["gros", "revendeur", "distributeur", "semi-gros", "بالجملة"]
            )
        ]
        if wholesale_signals:
            score += 15.0
            reasons.append(
                ScoreExplanation(
                    component="ECONOMIC_ACTIVITY",
                    reason=f"Vocabulaire de vente en gros ou de distribution détecté ({len(wholesale_signals)} mention(s))",
                    weight=15.0,
                )
            )

        # 5. Listed physical address or multiple branches
        if page and page.public_address:
            score += 10.0
            reasons.append(
                ScoreExplanation(
                    component="ECONOMIC_ACTIVITY",
                    reason=f"Présence physique déclarée ({page.public_address})",
                    weight=10.0,
                )
            )

        # 6. Gemini Geographic / Scale Confirmation
        if (
            ai_analysis
            and ai_analysis.recurring_activity
            and ai_analysis.delivery_pattern in ("NATIONWIDE", "LOCAL_REGIONAL")
        ):
            boost = 10.0
            score += boost
            reasons.append(
                ScoreExplanation(
                    component="ECONOMIC_ACTIVITY",
                    reason=f"Échelle sémantique confirmée : opérations récurrentes sur des canaux {ai_analysis.delivery_pattern.lower()}",
                    weight=boost,
                    source="GEMINI",
                    evidence_post_ids=ai_analysis.evidence_post_ids,
                )
            )

        clamped = min(max(round(score, 1), 0.0), 100.0)
        return ComponentScore(score=clamped, reasons=reasons), reasons


priority_scorer = ReviewPriorityScorer()
