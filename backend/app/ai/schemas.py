from typing import Literal

from pydantic import BaseModel, Field

ActivityType = Literal[
    "PRODUCT_SALE",
    "SERVICE",
    "WHOLESALE",
    "RENTAL",
    "FOOD_BUSINESS",
    "PERSONAL_RESALE",
    "ADVERTISEMENT",
    "NON_COMMERCIAL",
    "UNKNOWN",
]

PostCategory = Literal[
    "PRODUCT_OFFER",
    "SERVICE_OFFER",
    "PRICE_INFORMATION",
    "PROMOTION",
    "ORDER_REQUEST",
    "DELIVERY_INFORMATION",
    "PAYMENT_INFORMATION",
    "CUSTOMER_TESTIMONIAL",
    "PERSONAL_RESALE",
    "GENERAL_CONTENT",
    "NON_COMMERCIAL",
    "UNKNOWN",
]

BusinessPattern = Literal[
    "RECURRING_COMMERCIAL_ACTIVITY",
    "OCCASIONAL_COMMERCIAL_ACTIVITY",
    "PERSONAL_ACCOUNT",
    "COMMUNITY_OR_CONTENT",
    "UNKNOWN",
]

DeliveryPattern = Literal[
    "NATIONWIDE",
    "LOCAL_REGIONAL",
    "NONE_OR_PICKUP",
    "INTERNATIONAL",
    "UNKNOWN",
]


class GeminiCommercialAnalysis(BaseModel):
    """Structured response for ambiguity resolution."""

    is_commercial: bool
    confidence: float = Field(ge=0.0, le=1.0)
    activity_type: ActivityType = "UNKNOWN"
    recurring_business_pattern: bool = False
    ordering_detected: bool = False
    delivery_detected: bool = False
    payment_detected: bool = False
    promotion_detected: bool = False
    business_type: str | None = None
    products_or_services: list[str] = Field(default_factory=list)
    evidence_post_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class PostSemanticClassification(BaseModel):
    """Post-level semantic classification."""

    post_id: str
    categories: list[PostCategory] = Field(default_factory=list)
    commercial: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    indicators: list[str] = Field(default_factory=list)


class BatchPostClassificationResponse(BaseModel):
    """Batch container for multi-post semantic analysis."""

    posts: list[PostSemanticClassification] = Field(default_factory=list)


class PageSemanticAnalysis(BaseModel):
    """Page-level semantic synthesis after deep crawl."""

    business_pattern: BusinessPattern = "UNKNOWN"
    commercial_confidence: float = Field(ge=0.0, le=1.0)
    business_type: str | None = None
    products_or_services: list[str] = Field(default_factory=list)
    sales_channels: list[str] = Field(default_factory=list)
    delivery_pattern: DeliveryPattern = "UNKNOWN"
    recurring_activity: bool = False
    evidence_post_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
