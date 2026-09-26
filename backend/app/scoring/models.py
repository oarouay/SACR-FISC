from dataclasses import dataclass, field


@dataclass
class ScoreExplanation:
    component: str
    reason: str
    weight: float = 0.0
    evidence_reference: str | None = None
    source: str = "DETERMINISTIC"
    evidence_post_ids: list[str] = field(default_factory=list)


@dataclass
class QuickScoreResult:
    score: float
    reasons: list[ScoreExplanation] = field(default_factory=list)

    @property
    def reason_strings(self) -> list[str]:
        return [r.reason for r in self.reasons]


@dataclass
class ComponentScore:
    score: float
    reasons: list[ScoreExplanation] = field(default_factory=list)


@dataclass
class ReviewScoreResult:
    commercial_activity: ComponentScore
    transaction_evidence: ComponentScore
    economic_activity: ComponentScore
    review_priority: float
    scoring_version: str = "1.0.0"

    @property
    def all_explanations(self) -> list[ScoreExplanation]:
        return (
            self.commercial_activity.reasons
            + self.transaction_evidence.reasons
            + self.economic_activity.reasons
        )
