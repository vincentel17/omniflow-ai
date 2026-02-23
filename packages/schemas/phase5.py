from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class PresenceAuditInputJSON(BaseModel):
    website_url: HttpUrl | None = None
    providers_to_audit: list[str] = Field(default_factory=list, max_length=8)
    account_refs: dict[str, list[str]] = Field(default_factory=dict)
    run_mode: str = Field(pattern="^(manual|scheduled)$")


class PresenceActionJSON(BaseModel):
    action_type: str = Field(min_length=1, max_length=100)
    steps: list[str] = Field(default_factory=list, max_length=20)
    estimated_impact: str = Field(pattern="^(low|med|high)$")
    estimated_effort: str = Field(pattern="^(low|med|high)$")
    requires_human_review: bool = True
    risk_tier: str = Field(pattern="^TIER_[0-4]$")


class PresenceFindingJSON(BaseModel):
    source: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=100)
    severity: str = Field(pattern="^(info|low|medium|high)$")
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=2000)
    evidence_json: dict[str, object] = Field(default_factory=dict)
    recommendation_json: PresenceActionJSON


class PresenceHealthReportJSON(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    category_scores: dict[str, int] = Field(default_factory=dict)
    findings: list[PresenceFindingJSON] = Field(default_factory=list, max_length=200)
    prioritized_actions: list[PresenceActionJSON] = Field(default_factory=list, max_length=10)


class SEOServicePageJSON(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    keyword: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    outline: list[str] = Field(default_factory=list, max_length=20)


class SEOClusterPostJSON(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    keyword: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)


class SEOClusterJSON(BaseModel):
    pillar_topic: str = Field(min_length=1, max_length=255)
    cluster_posts: list[SEOClusterPostJSON] = Field(default_factory=list, max_length=20)


class SEOPlanJSON(BaseModel):
    service_pages: list[SEOServicePageJSON] = Field(default_factory=list, max_length=50)
    blog_clusters: list[SEOClusterJSON] = Field(default_factory=list, max_length=20)
    internal_linking_suggestions: list[str] = Field(default_factory=list, max_length=50)
    schema_suggestions: list[str] = Field(default_factory=list, max_length=20)


class SEOFaqJSON(BaseModel):
    question: str = Field(min_length=1, max_length=255)
    answer: str = Field(min_length=1, max_length=2000)


class SEOContentJSON(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    meta_title: str = Field(min_length=1, max_length=255)
    meta_description: str = Field(min_length=1, max_length=500)
    outline: list[str] = Field(default_factory=list, max_length=20)
    body_markdown: str = Field(min_length=1, max_length=50000)
    faq: list[SEOFaqJSON] = Field(default_factory=list, max_length=20)
    schema_data: dict[str, object] | None = Field(
        default=None,
        validation_alias="schema_json",
        serialization_alias="schema_json",
    )
    disclaimers: list[str] = Field(default_factory=list, max_length=10)


class ReviewSentimentJSON(BaseModel):
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    labels: list[str] = Field(default_factory=list, max_length=12)
    urgency: str = Field(pattern="^(low|med|high)$")


class ReviewResponseDraftJSON(BaseModel):
    response_text: str = Field(min_length=1, max_length=4000)
    tone: str = Field(min_length=1, max_length=100)
    disclaimers: list[str] = Field(default_factory=list, max_length=8)
    risk_tier: str = Field(pattern="^TIER_[0-4]$")
    policy_warnings: list[str] = Field(default_factory=list, max_length=12)
