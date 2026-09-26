from pydantic import BaseModel


class MetricsSummaryResponse(BaseModel):
    targets_pending: int
    targets_claimed: int
    targets_crawling: int
    targets_completed: int
    targets_blocked: int
    targets_failed: int
    targets_retry: int
    targets_manual_review: int
    total_targets: int

    quick_crawls: int
    deep_crawls: int
    pages_promoted_quick_to_deep: int

    total_pages_stored: int
    total_posts_collected: int
    total_signals_extracted: int
    total_evidence_stored: int

    pages_in_review_queue: int
    average_review_priority: float

    # Gemini & AI Intelligence Metrics
    gemini_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    cached_responses: int = 0
    average_latency_ms: float = 0.0
    posts_analyzed: int = 0
    pages_analyzed: int = 0
    ambiguity_cases_resolved: int = 0
