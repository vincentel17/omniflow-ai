from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from packages.policy import PolicyEngine
from packages.schemas import (
    PresenceActionJSON,
    PresenceAuditInputJSON,
    SEOClusterJSON,
    SEOClusterPostJSON,
    SEOFaqJSON,
    PresenceFindingJSON,
    PresenceHealthReportJSON,
    ReviewResponseDraftJSON,
    ReviewSentimentJSON,
    SEOContentJSON,
    SEOPlanJSON,
    SEOServicePageJSON,
)

from ..models import (    LeadAssignment,
    Membership,
    PresenceFinding,    PresenceTask,
    PresenceTaskStatus,
    PresenceTaskType,
    ReputationReview,
    RiskTier,
    Role,
)
from .verticals import load_pack_file


def _now() -> datetime:
    return datetime.now(UTC)


def mask_reviewer_name(name: str | None) -> str:
    if not name:
        return "Anonymous"
    compact = name.strip()
    if len(compact) <= 2:
        return f"{compact[0]}*" if compact else "Anonymous"
    return f"{compact[0]}{'*' * max(1, len(compact) - 2)}{compact[-1]}"


def hash_review_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _robots_allows_homepage(url: str, timeout_seconds: float = 2.5) -> bool:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.get(robots_url)
            if response.status_code >= 400:
                return True
            lines = [line.strip().lower() for line in response.text.splitlines()]
    except Exception:
        return False

    applies_to_all = False
    for line in lines:
        if line.startswith("user-agent:"):
            applies_to_all = line.split(":", 1)[1].strip() == "*"
            continue
        if applies_to_all and line.startswith("disallow:"):
            value = line.split(":", 1)[1].strip()
            if value == "/":
                return False
    return True


def fetch_website_snapshot(
    website_url: str,
    timeout_seconds: float = 4.0,
) -> dict[str, Any]:
    allowed = _robots_allows_homepage(website_url)
    if not allowed:
        return {"allowed": False, "reason": "robots_disallow"}

    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.get(website_url)
        if response.status_code >= 400:
            return {"allowed": True, "error": f"status_{response.status_code}"}
        body = response.text[:200_000]
    except Exception:
        return {"allowed": True, "error": "fetch_failed"}

    title_match = re.search(r"<title[^>]*>(.*?)</title>", body, flags=re.IGNORECASE | re.DOTALL)
    description_match = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
        body,
        flags=re.IGNORECASE,
    )
    canonical_match = re.search(
        r'<link\s+rel=["\']canonical["\']\s+href=["\'](.*?)["\']',
        body,
        flags=re.IGNORECASE,
    )
    h1_count = len(re.findall(r"<h1[^>]*>", body, flags=re.IGNORECASE))
    has_schema = "application/ld+json" in body.lower()
    return {
        "allowed": True,
        "title": (title_match.group(1).strip() if title_match else ""),
        "meta_description": (description_match.group(1).strip() if description_match else ""),
        "canonical": (canonical_match.group(1).strip() if canonical_match else ""),
        "h1_count": h1_count,
        "has_schema": has_schema,
    }


def mock_profile_snapshot(provider: str, account_ref: str) -> dict[str, Any]:
    base = {
        "provider": provider,
        "account_ref": account_ref,
        "bio": "Helping local customers with trusted service.",
        "cta_link_present": True,
        "branding_consistency": "partial",
    }
    if provider == "gbp":
        base.update(
            {
                "categories_present": False,
                "services_count": 3,
                "hours_present": True,
                "photos_last_30_days": 1,
                "posts_last_30_days": 0,
                "qa_enabled": False,
            }
        )
    return base


def build_presence_report(
    audit_input: PresenceAuditInputJSON,
    snapshots: list[dict[str, Any]],
) -> PresenceHealthReportJSON:
    findings: list[PresenceFindingJSON] = []

    for snapshot in snapshots:
        provider = str(snapshot.get("provider", "unknown"))
        if provider == "gbp":
            if not snapshot.get("categories_present", False):
                findings.append(
                    PresenceFindingJSON(
                        source="gbp",
                        category="profile",
                        severity="high",
                        title="Primary categories missing",
                        description="Google Business Profile categories are incomplete.",
                        evidence_json={"categories_present": False},
                        recommendation_json=PresenceActionJSON(
                            action_type="fix_profile",
                            steps=["Set primary category", "Add secondary categories"],
                            estimated_impact="high",
                            estimated_effort="low",
                            requires_human_review=False,
                            risk_tier="TIER_1",
                        ),
                    )
                )
            if int(snapshot.get("posts_last_30_days", 0)) == 0:
                findings.append(
                    PresenceFindingJSON(
                        source="gbp",
                        category="content",
                        severity="medium",
                        title="No recent GBP posts",
                        description="No posts in the last 30 days were detected.",
                        evidence_json={"posts_last_30_days": 0},
                        recommendation_json=PresenceActionJSON(
                            action_type="post_gbp",
                            steps=["Create weekly local update posts"],
                            estimated_impact="med",
                            estimated_effort="low",
                            requires_human_review=False,
                            risk_tier="TIER_1",
                        ),
                    )
                )
        else:
            if not snapshot.get("cta_link_present", False):
                findings.append(
                    PresenceFindingJSON(
                        source=provider,
                        category="profile",
                        severity="low",
                        title="CTA link missing",
                        description="Profile bio is missing a trackable CTA link.",
                        evidence_json={"cta_link_present": False},
                        recommendation_json=PresenceActionJSON(
                            action_type="fix_profile",
                            steps=["Add a primary CTA URL with tracking UTM"],
                            estimated_impact="med",
                            estimated_effort="low",
                            requires_human_review=False,
                            risk_tier="TIER_1",
                        ),
                    )
                )

    website_url = audit_input.website_url
    if website_url:
        site = snapshots[-1] if snapshots and snapshots[-1].get("source") == "website" else {}
        if not site.get("allowed", True):
            findings.append(
                PresenceFindingJSON(
                    source="website",
                    category="technical",
                    severity="info",
                    title="Website audit skipped by robots.txt",
                    description="Robots.txt disallowed homepage fetch.",
                    evidence_json={"reason": site.get("reason", "robots_disallow")},
                    recommendation_json=PresenceActionJSON(
                        action_type="create_page",
                        steps=["Review robots.txt policy for homepage access"],
                        estimated_impact="low",
                        estimated_effort="low",
                        requires_human_review=True,
                        risk_tier="TIER_1",
                    ),
                )
            )
        else:
            if not site.get("meta_description"):
                findings.append(
                    PresenceFindingJSON(
                        source="website",
                        category="seo",
                        severity="medium",
                        title="Meta description missing",
                        description="Homepage meta description was not detected.",
                        evidence_json={"url": str(website_url)},
                        recommendation_json=PresenceActionJSON(
                            action_type="create_page",
                            steps=["Add concise meta description with target intent"],
                            estimated_impact="med",
                            estimated_effort="low",
                            requires_human_review=False,
                            risk_tier="TIER_1",
                        ),
                    )
                )
            if int(site.get("h1_count", 0)) != 1:
                findings.append(
                    PresenceFindingJSON(
                        source="website",
                        category="technical",
                        severity="low",
                        title="H1 structure needs improvement",
                        description="Homepage should have exactly one primary H1.",
                        evidence_json={"h1_count": site.get("h1_count", 0)},
                        recommendation_json=PresenceActionJSON(
                            action_type="create_page",
                            steps=["Normalize heading hierarchy to one H1"],
                            estimated_impact="low",
                            estimated_effort="low",
                            requires_human_review=False,
                            risk_tier="TIER_1",
                        ),
                    )
                )

    penalty = sum({"info": 2, "low": 5, "medium": 10, "high": 20}[f.severity] for f in findings)
    overall_score = max(0, 100 - penalty)
    category_scores = {
        "profile": max(0, 100 - 15 * sum(1 for f in findings if f.category == "profile")),
        "seo": max(0, 100 - 15 * sum(1 for f in findings if f.category == "seo")),
        "content": max(0, 100 - 15 * sum(1 for f in findings if f.category == "content")),
        "authority": 75,
        "reviews": 70,
        "consistency": 80,
        "technical": max(0, 100 - 10 * sum(1 for f in findings if f.category == "technical")),
    }
    prioritized_actions = [finding.recommendation_json for finding in findings[:10]]
    return PresenceHealthReportJSON(
        overall_score=overall_score,
        category_scores=category_scores,
        findings=findings,
        prioritized_actions=prioritized_actions,
    )


def load_seo_archetypes(pack_slug: str) -> dict[str, Any]:
    return load_pack_file(pack_slug, "seo_archetypes.json")


def build_seo_plan(
    pack_slug: str,
    locations: list[str],
    latest_findings: list[PresenceFinding] | None = None,
) -> SEOPlanJSON:
    archetypes = load_seo_archetypes(pack_slug)
    primary_location = locations[0] if locations else "local-area"
    has_technical_gap = any(f.category == "technical" for f in latest_findings or [])
    service_pages = [
        SEOServicePageJSON(
            title=f"{primary_location.title()} Service Experts",
            keyword=f"{primary_location} service",
            location=primary_location,
            slug=f"{primary_location.replace(' ', '-').lower()}-service",
            outline=["Overview", "Process", "Proof", "FAQ", "Call to action"],
        )
    ]
    cluster_name = archetypes.get("blog_cluster", "local-growth")
    blog_clusters = [
        SEOClusterJSON(
            pillar_topic=str(cluster_name),
            cluster_posts=[
                SEOClusterPostJSON(
                    title=f"Top {primary_location.title()} Buyer Questions",
                    keyword=f"{primary_location} guide",
                    slug=f"{primary_location.replace(' ', '-').lower()}-guide",
                ),
                SEOClusterPostJSON(
                    title="How to Evaluate Providers",
                    keyword="provider evaluation checklist",
                    slug="provider-evaluation-checklist",
                ),
            ],
        )
    ]
    return SEOPlanJSON(
        service_pages=service_pages,
        blog_clusters=blog_clusters,
        internal_linking_suggestions=[
            "Link each cluster post back to the primary service page",
            "Cross-link FAQ answers to relevant service sections",
        ],
        schema_suggestions=["LocalBusiness", "FAQPage"] + (["BreadcrumbList"] if has_technical_gap else []),
    )


def build_seo_content(
    title: str,
    slug: str,
    keyword: str,
    location: str | None,
    policy: PolicyEngine,
) -> tuple[SEOContentJSON, list[str], RiskTier]:
    locality = location or "local area"
    body = (
        f"# {title}\n\n"
        f"Looking for {keyword} in {locality}? This page explains outcomes, process, and next steps.\n\n"
        "## Why clients choose us\n- Proven execution\n- Transparent communication\n- Fast response\n\n"
        "## Next steps\nBook a consultation to review your specific goals."
    )
    content = SEOContentJSON(
        title=title,
        slug=slug,
        meta_title=f"{title} | OmniFlow",
        meta_description=f"Learn how we deliver {keyword} outcomes in {locality}.",
        outline=["Intro", "Why us", "Process", "FAQ", "CTA"],
        body_markdown=body,
        faq=[
            SEOFaqJSON(question="How quickly can we start?", answer="Most projects begin within one week."),
            SEOFaqJSON(
                question="Do you provide transparent pricing?",
                answer="Yes, pricing ranges are shared up front.",
            ),
        ],
        schema_data={"@type": "FAQPage"},
        disclaimers=[],
    )
    validation = policy.validate_content(content.body_markdown, context={"surface": "seo"})
    warnings = validation.reasons
    risk_tier = RiskTier(policy.risk_tier("seo_generate", context={"surface": "seo"}).value)
    return content, warnings, risk_tier


def score_review_sentiment(review_text: str, rating: int) -> ReviewSentimentJSON:
    lower = review_text.lower()
    labels: list[str] = []
    if "staff" in lower:
        labels.append("staff")
    if "price" in lower or "pricing" in lower:
        labels.append("pricing")
    if "fast" in lower or "slow" in lower:
        labels.append("timeliness")
    if not labels:
        labels.append("general")

    if rating <= 2 or any(token in lower for token in ("refund", "complaint", "never")):
        return ReviewSentimentJSON(sentiment_score=-0.7, labels=labels, urgency="high")
    if rating == 3:
        return ReviewSentimentJSON(sentiment_score=0.0, labels=labels, urgency="med")
    return ReviewSentimentJSON(sentiment_score=0.7, labels=labels, urgency="low")


def build_review_response_draft(
    review: ReputationReview,
    policy: PolicyEngine,
) -> ReviewResponseDraftJSON:
    base_text = (
        "Thank you for sharing this feedback. We take your experience seriously and would like to make this right."
        if review.rating <= 3
        else "Thank you for the kind review. We appreciate your trust and look forward to serving you again."
    )
    validation = policy.validate_content(base_text, context={"surface": "review_response"})
    warnings = validation.reasons
    risk_tier = RiskTier(policy.risk_tier("review_response_draft", context={"surface": "review_response"}).value)
    return ReviewResponseDraftJSON(
        response_text=base_text,
        tone="professional",
        disclaimers=[],
        risk_tier=risk_tier.value,
        policy_warnings=warnings,
    )


def next_round_robin_member(db: Session, org_id: Any) -> Any | None:
    agent_members = db.scalars(
        select(Membership)
        .where(
            Membership.org_id == org_id,
            Membership.role.in_([Role.AGENT, Role.ADMIN, Role.OWNER]),
            Membership.deleted_at.is_(None),
        )
        .order_by(Membership.created_at)
    ).all()
    if not agent_members:
        return None
    latest_assignment = db.scalar(
        select(LeadAssignment)
        .where(LeadAssignment.org_id == org_id, LeadAssignment.deleted_at.is_(None))
        .order_by(desc(LeadAssignment.created_at))
        .limit(1)
    )
    if latest_assignment is None:
        return agent_members[0].user_id
    user_ids = [m.user_id for m in agent_members]
    if latest_assignment.assigned_to_user_id not in user_ids:
        return user_ids[0]
    idx = user_ids.index(latest_assignment.assigned_to_user_id)
    return user_ids[(idx + 1) % len(user_ids)]


def create_reputation_campaign_tasks(
    db: Session,
    org_id: Any,
    template_key: str,
    audience: str,
) -> int:
    assignee = next_round_robin_member(db, org_id)
    if assignee is None:
        return 0
    count = 10 if audience == "recent_customers" else 5
    due = _now() + timedelta(hours=24)
    for index in range(count):
        db.add(
            PresenceTask(
                org_id=org_id,
                finding_id=None,
                type=PresenceTaskType.RESPOND_REVIEW,
                assigned_to_user_id=assignee,
                due_at=due,
                status=PresenceTaskStatus.OPEN,
                payload_json={
                    "campaign_task_number": index + 1,
                    "template_key": template_key,
                    "audience": audience,
                    "channel": "reputation_request",
                },
            )
        )
    db.flush()
    return count

