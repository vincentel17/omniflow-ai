from __future__ import annotations

import hashlib
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.db import SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    AgentDefinition,
    AgentRun,
    AgentRunStatus,
    Approval,
    ApprovalEntityType,
    ApprovalStatus,
    BillingSubscriptionStatus,
    CampaignPlan,
    CampaignPlanStatus,
    ContentItem,
    ContentItemStatus,
    DataRetentionPolicy,
    Event,
    InboxMessage,
    InboxMessageDirection,
    InboxThread,
    InboxThreadStatus,
    InboxThreadType,
    Lead,
    LeadStatus,
    Membership,
    ModelMetadata,
    ModelStatus,
    Org,
    GlobalAdmin,
    OrgOptimizationSettings,
    OrgSettings,
    OrgSubscription,
    PresenceAuditRun,
    PresenceAuditRunStatus,
    PublishJob,
    PublishJobStatus,
    ReputationReview,
    ReputationSource,
    RiskTier,
    Role,
    SEOWorkItem,
    SEOWorkItemStatus,
    SEOWorkItemType,
    SubscriptionPlan,
    UsageMetric,
    UsageMetricType,
    User,
    VerticalPack,
    Workflow,
    WorkflowActionRun,
    WorkflowActionRunStatus,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowTriggerType,
)


SEED_VERSION = "qa-standard-v1"
ANCHOR = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
NS = uuid.UUID("7f2f16c1-8664-48ee-a5ef-7dd2d5ac7b26")


@dataclass(frozen=True)
class OrgSpec:
    key: str
    name: str
    pack_slug: str
    compliance_mode: str
    agent_autonomy_max_tier: int
    include_full_dataset: bool


ORGS = [
    OrgSpec("alpha", "OmniFlow Home Care Demo", "home-care", "home_care", 1, True),
    OrgSpec("beta", "OmniFlow Real Estate Demo", "real-estate", "none", 2, True),
    OrgSpec("gamma", "OmniFlow Generic Demo", "generic", "none", 0, True),
]

AGENT_DEFS = [
    ("SupervisorAgent", "1.0.0", ["generic", "real-estate", "home-care"]),
    ("InboxAgent", "1.0.0", ["generic", "real-estate", "home-care"]),
    ("GrowthAgent", "1.0.0", ["generic", "real-estate", "home-care"]),
    ("PresenceAgent", "1.0.0", ["generic", "real-estate", "home-care"]),
    ("SEOAgent", "1.0.0", ["generic", "real-estate", "home-care"]),
    ("ReputationAgent", "1.0.0", ["generic", "real-estate", "home-care"]),
    ("RealEstateOpsAgent", "1.0.0", ["real-estate"]),
]


def _uid(*parts: object) -> uuid.UUID:
    return uuid.uuid5(NS, ":".join(str(p) for p in parts))


def _upsert(
    db: Session,
    model: Any,
    *,
    lookup: dict[str, Any],
    defaults: dict[str, Any],
) -> Any:
    row = db.scalar(select(model).filter_by(**lookup))
    if row is None:
        row = model(**lookup, **defaults)
        db.add(row)
        db.flush()
    else:
        for key, value in defaults.items():
            setattr(row, key, value)
    return row


def _user_and_memberships(db: Session, org_id: uuid.UUID, org_key: str) -> tuple[uuid.UUID, uuid.UUID]:
    admin_id = _uid("user", org_key, "admin")
    member_id = _uid("user", org_key, "member")
    for user_id, suffix in ((admin_id, "admin"), (member_id, "member")):
        _upsert(
            db,
            User,
            lookup={"id": user_id},
            defaults={
                "email": f"{org_key}.{suffix}@qa.omniflow.local",
                "full_name": f"{org_key.title()} {suffix.title()}",
                "external_auth_id": f"auth0|qa-{org_key}-{suffix}",
            },
        )
    _upsert(
        db,
        Membership,
        lookup={"org_id": org_id, "user_id": admin_id},
        defaults={"id": _uid("membership", org_key, "admin"), "role": Role.ADMIN},
    )
    _upsert(
        db,
        Membership,
        lookup={"org_id": org_id, "user_id": member_id},
        defaults={"id": _uid("membership", org_key, "member"), "role": Role.MEMBER},
    )
    return admin_id, member_id


def _seed_preview_users(db: Session, org_id: uuid.UUID) -> None:
    preview_users = (
        ("owner", Role.OWNER),
        ("admin", Role.ADMIN),
        ("member", Role.MEMBER),
        ("agent", Role.AGENT),
    )
    for role_key, role in preview_users:
        user_id = _uid("preview-user", role_key)
        _upsert(
            db,
            User,
            lookup={"id": user_id},
            defaults={
                "email": f"preview.{role_key}@qa.omniflow.local",
                "full_name": f"Preview {role_key.title()}",
                "external_auth_id": f"auth0|preview-{role_key}",
            },
        )
        _upsert(
            db,
            Membership,
            lookup={"org_id": org_id, "user_id": user_id},
            defaults={"id": _uid("preview-membership", org_id, role_key), "role": role},
        )
        if role_key == "owner":
            _upsert(
                db,
                GlobalAdmin,
                lookup={"user_id": user_id},
                defaults={
                    "id": _uid("preview-global-admin", role_key),
                    "email": f"preview.{role_key}@qa.omniflow.local",
                    "active": True,
                },
            )


def _seed_org_basics(db: Session, spec: OrgSpec) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    org_id = _uid("org", spec.key)
    org = _upsert(
        db,
        Org,
        lookup={"id": org_id},
        defaults={"name": spec.name},
    )
    org.name = spec.name

    admin_id, member_id = _user_and_memberships(db, org_id, spec.key)
    _seed_preview_users(db, org_id)

    _upsert(
        db,
        VerticalPack,
        lookup={"org_id": org_id},
        defaults={"id": _uid("vertical-pack", spec.key), "pack_slug": spec.pack_slug},
    )

    settings_payload = {
        "qa_seed_version": SEED_VERSION,
        "enable_agents": True,
        "ai_mode": "mock",
        "connector_mode": "mock",
        "compliance_mode": spec.compliance_mode,
        "agent_autonomy_max_tier": spec.agent_autonomy_max_tier,
        "agent_max_plans_per_day": 10,
        "agent_max_steps_per_plan": 10,
        "agent_cooldown_minutes": 0,
        "agent_schedule_enabled": True,
        "agent_schedule_hour_local": 8,
        "enable_auto_nurture_apply": True,
        "agent_allowed_action_types_json": [],
        "agent_disallowed_targets_json": [],
    }
    _upsert(
        db,
        OrgSettings,
        lookup={"org_id": org_id},
        defaults={"id": _uid("org-settings", spec.key), "settings_json": settings_payload},
    )

    _upsert(
        db,
        OrgOptimizationSettings,
        lookup={"org_id": org_id},
        defaults={
            "id": _uid("org-optimization", spec.key),
            "enable_predictive_scoring": True,
            "enable_post_timing_optimization": True,
            "enable_nurture_optimization": True,
            "enable_ad_budget_recommendations": True,
            "auto_apply_low_risk_optimizations": False,
        },
    )
    return org_id, admin_id, member_id


def _seed_plan_and_subscription(db: Session, org_id: uuid.UUID, org_key: str) -> None:
    plan_id = _uid("subscription-plan", "qa-standard")
    _upsert(
        db,
        SubscriptionPlan,
        lookup={"id": plan_id},
        defaults={
            "name": "qa-standard-plan",
            "price_monthly_usd": 99.0,
            "price_yearly_usd": 999.0,
            "entitlements_json": {"agents": True, "workflows": True},
            "allowed_verticals_json": ["generic", "real-estate", "home-care"],
            "custom_pack_pricing_json": {},
        },
    )
    _upsert(
        db,
        OrgSubscription,
        lookup={"org_id": org_id},
        defaults={
            "id": _uid("org-subscription", org_key),
            "stripe_customer_id": f"cus_qa_{org_key}",
            "stripe_subscription_id": f"sub_qa_{org_key}",
            "plan_id": plan_id,
            "status": BillingSubscriptionStatus.ACTIVE,
            "current_period_start": ANCHOR - timedelta(days=10),
            "current_period_end": ANCHOR + timedelta(days=20),
            "trial_end": None,
        },
    )


def _seed_leads(db: Session, org_id: uuid.UUID, org_key: str) -> list[uuid.UUID]:
    lead_ids: list[uuid.UUID] = []
    status_schedule = (
        [LeadStatus.NEW] * 20
        + [LeadStatus.QUALIFIED] * 10
        + [LeadStatus.UNQUALIFIED] * 10
        + [LeadStatus.ARCHIVED] * 10
    )
    for idx, status in enumerate(status_schedule):
        lead_id = _uid("lead", org_key, idx)
        lead_ids.append(lead_id)
        row = _upsert(
            db,
            Lead,
            lookup={"id": lead_id},
            defaults={
                "org_id": org_id,
                "source": "qa_standard",
                "status": status,
                "name": f"{org_key.title()} Lead {idx:02d}",
                "email": f"{org_key}.lead{idx:02d}@example.test",
                "phone": f"+1-555-01{idx:03d}",
                "location_json": {"city": "Testville", "state": "NY"},
                "tags_json": ["qa-standard", status.value],
                "pii_flags_json": {},
                "sensitive_level": "medium",
            },
        )
        if idx < 5:
            row.updated_at = ANCHOR - timedelta(days=20)
    return lead_ids


def _seed_inbox(db: Session, org_id: uuid.UUID, org_key: str, lead_ids: list[uuid.UUID], admin_id: uuid.UUID) -> None:
    thread_ids: list[uuid.UUID] = []
    for idx in range(25):
        status = InboxThreadStatus.OPEN if idx < 15 else InboxThreadStatus.CLOSED
        thread_id = _uid("thread", org_key, idx)
        thread_ids.append(thread_id)
        _upsert(
            db,
            InboxThread,
            lookup={"org_id": org_id, "provider": "meta", "account_ref": "acct-main", "external_thread_id": f"{org_key}-t-{idx}"},
            defaults={
                "id": thread_id,
                "thread_type": InboxThreadType.DM,
                "subject": f"QA Thread {idx}",
                "participants_json": [{"ref": f"user-{idx}", "display": f"Participant {idx}"}],
                "last_message_at": ANCHOR - timedelta(hours=idx),
                "status": status,
                "lead_id": lead_ids[idx % len(lead_ids)],
                "assigned_to_user_id": admin_id,
            },
        )

    for idx in range(60):
        thread_id = thread_ids[idx % len(thread_ids)]
        direction = InboxMessageDirection.INBOUND if idx % 2 == 0 else InboxMessageDirection.OUTBOUND
        _upsert(
            db,
            InboxMessage,
            lookup={"org_id": org_id, "thread_id": thread_id, "external_message_id": f"{org_key}-m-{idx}"},
            defaults={
                "id": _uid("message", org_key, idx),
                "direction": direction,
                "sender_ref": f"sender-{idx % 10}",
                "sender_display": f"Sender {idx % 10}",
                "body_text": f"QA message {idx} for {org_key}",
                "body_raw_json": {"text": f"QA message {idx}"},
                "flags_json": {},
                "pii_flags_json": {},
                "sensitive_level": "medium",
            },
        )


def _seed_events(db: Session, org_id: uuid.UUID, org_key: str, sla_breaches: int) -> None:
    for idx in range(sla_breaches):
        _upsert(
            db,
            Event,
            lookup={"id": _uid("event", org_key, "sla", idx)},
            defaults={
                "org_id": org_id,
                "source": "qa-seed",
                "channel": "inbox",
                "campaign_id": None,
                "content_id": None,
                "lead_id": None,
                "actor_id": None,
                "type": "SLA_BREACH",
                "payload_json": {"minutes_over": 15 + idx},
            },
        )


def _seed_content_and_publish(
    db: Session, org_id: uuid.UUID, org_key: str, admin_id: uuid.UUID, pack_slug: str
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    campaign_id = _uid("campaign-plan", org_key, "week")
    _upsert(
        db,
        CampaignPlan,
        lookup={"org_id": org_id, "week_start_date": date(2026, 3, 2)},
        defaults={
            "id": campaign_id,
            "vertical_pack_slug": pack_slug,
            "status": CampaignPlanStatus.APPROVED,
            "created_by": admin_id,
            "approved_by": admin_id,
            "approved_at": ANCHOR - timedelta(days=1),
            "plan_json": {"name": "qa-standard"},
            "metadata_json": {"seed_version": SEED_VERSION},
        },
    )
    content_ids: list[uuid.UUID] = []
    publish_ids: list[uuid.UUID] = []
    channels = ["meta", "linkedin", "gbp"]
    for idx in range(12):
        content_id = _uid("content", org_key, idx)
        content_ids.append(content_id)
        status = ContentItemStatus.DRAFT if idx < 4 else ContentItemStatus.SCHEDULED
        _upsert(
            db,
            ContentItem,
            lookup={"id": content_id},
            defaults={
                "org_id": org_id,
                "campaign_plan_id": campaign_id,
                "channel": channels[idx % len(channels)],
                "account_ref": "acct-main",
                "status": status,
                "content_json": {"title": f"QA Content {idx}"},
                "text_rendered": f"QA content rendered text {idx}",
                "media_refs_json": [],
                "link_url": f"https://example.test/{org_key}/content/{idx}",
                "tags_json": ["qa-standard"],
                "risk_tier": RiskTier.TIER_1,
                "policy_warnings_json": [],
            },
        )
    for idx in range(8):
        publish_id = _uid("publish-job", org_key, idx)
        publish_ids.append(publish_id)
        status = PublishJobStatus.FAILED if idx < 2 else PublishJobStatus.QUEUED
        _upsert(
            db,
            PublishJob,
            lookup={"org_id": org_id, "content_item_id": content_ids[idx]},
            defaults={
                "id": publish_id,
                "provider": channels[idx % len(channels)],
                "account_ref": "acct-main",
                "schedule_at": ANCHOR + timedelta(hours=idx),
                "status": status,
                "idempotency_key": f"qa-standard:{org_key}:publish:{idx}",
                "attempts": 1 if status == PublishJobStatus.FAILED else 0,
                "last_error": "LIVE_DISABLED" if status == PublishJobStatus.FAILED else None,
                "external_id": None,
                "published_at": None,
            },
        )
    return content_ids, publish_ids


def _seed_presence_seo_reputation(db: Session, org_id: uuid.UUID, org_key: str) -> None:
    latest_score = 65.0 if org_key == "alpha" else 82.0
    for idx in range(3):
        _upsert(
            db,
            PresenceAuditRun,
            lookup={"id": _uid("presence-audit", org_key, idx)},
            defaults={
                "org_id": org_id,
                "started_at": ANCHOR - timedelta(days=idx + 1),
                "completed_at": ANCHOR - timedelta(days=idx + 1, minutes=-15),
                "status": PresenceAuditRunStatus.SUCCEEDED,
                "inputs_json": {"source": "qa-seed"},
                "summary_scores_json": {"overall_score": latest_score - (idx * 2)},
                "notes_json": {},
                "error_json": {},
            },
        )

    seo_types = [SEOWorkItemType.SERVICE_PAGE, SEOWorkItemType.BLOG_POST, SEOWorkItemType.FAQ]
    for idx in range(10):
        status = SEOWorkItemStatus.DRAFT if idx < 3 else SEOWorkItemStatus.APPROVED
        _upsert(
            db,
            SEOWorkItem,
            lookup={"org_id": org_id, "type": seo_types[idx % len(seo_types)], "url_slug": f"{org_key}-seo-{idx}"},
            defaults={
                "id": _uid("seo-work", org_key, idx),
                "status": status,
                "target_keyword": f"{org_key} service {idx}",
                "target_location": "Testville",
                "content_json": {"seed": SEED_VERSION},
                "rendered_markdown": f"# {org_key} SEO {idx}",
                "risk_tier": RiskTier.TIER_1,
                "policy_warnings_json": [],
            },
        )

    unresponded_negative = 4 if org_key == "alpha" else 2
    for idx in range(20):
        rating = 1 if idx < unresponded_negative else (5 if idx % 3 else 3)
        review_text = f"QA review {idx} for {org_key}"
        review_hash = hashlib.sha256(review_text.encode("utf-8")).hexdigest()
        responded_at = None if idx < unresponded_negative else ANCHOR - timedelta(days=1)
        _upsert(
            db,
            ReputationReview,
            lookup={"id": _uid("review", org_key, idx)},
            defaults={
                "org_id": org_id,
                "source": ReputationSource.MANUAL_IMPORT,
                "external_id": f"{org_key}-review-{idx}",
                "reviewer_name_masked": f"{org_key[0].upper()}***",
                "rating": rating,
                "review_text": review_text,
                "review_text_hash": review_hash,
                "sentiment_json": {"label": "negative" if rating <= 2 else "positive"},
                "responded_at": responded_at,
                "pii_flags_json": {},
                "sensitive_level": "medium",
            },
        )


def _seed_workflows_agents_and_approvals(db: Session, org_id: uuid.UUID, org_key: str, admin_id: uuid.UUID, member_id: uuid.UUID) -> None:
    workflow_ids: list[uuid.UUID] = []
    for idx in range(5):
        workflow_id = _uid("workflow", org_key, idx)
        workflow_ids.append(workflow_id)
        trigger = WorkflowTriggerType.EVENT if idx % 2 == 0 else WorkflowTriggerType.SCHEDULE
        _upsert(
            db,
            Workflow,
            lookup={"org_id": org_id, "key": f"qa-{org_key}-wf-{idx}"},
            defaults={
                "id": workflow_id,
                "name": f"QA Workflow {idx}",
                "enabled": True,
                "trigger_type": trigger,
                "managed_by_pack": False,
                "definition_json": {"steps": []},
            },
        )

    workflow_run_ids: list[uuid.UUID] = []
    run_statuses = [
        WorkflowRunStatus.QUEUED,
        WorkflowRunStatus.RUNNING,
        WorkflowRunStatus.SUCCEEDED,
        WorkflowRunStatus.FAILED,
        WorkflowRunStatus.BLOCKED,
    ]
    for idx in range(10):
        workflow_run_id = _uid("workflow-run", org_key, idx)
        workflow_run_ids.append(workflow_run_id)
        status = run_statuses[idx % len(run_statuses)]
        finished_at = ANCHOR - timedelta(hours=idx) if status in {WorkflowRunStatus.SUCCEEDED, WorkflowRunStatus.FAILED} else None
        _upsert(
            db,
            WorkflowRun,
            lookup={"id": workflow_run_id},
            defaults={
                "org_id": org_id,
                "workflow_id": workflow_ids[idx % len(workflow_ids)],
                "trigger_event_id": None,
                "status": status,
                "started_at": ANCHOR - timedelta(hours=idx + 2),
                "finished_at": finished_at,
                "summary_json": {"seed": SEED_VERSION},
                "error_json": {} if status != WorkflowRunStatus.FAILED else {"error": "qa-seed"},
                "loop_guard_hits": 0,
            },
        )

    action_ids: list[uuid.UUID] = []
    action_statuses = [
        WorkflowActionRunStatus.QUEUED,
        WorkflowActionRunStatus.SUCCEEDED,
        WorkflowActionRunStatus.FAILED,
        WorkflowActionRunStatus.BLOCKED,
    ]
    for idx in range(8):
        action_id = _uid("workflow-action", org_key, idx)
        action_ids.append(action_id)
        _upsert(
            db,
            WorkflowActionRun,
            lookup={"org_id": org_id, "idempotency_key": f"qa-standard:{org_key}:action:{idx}"},
            defaults={
                "id": action_id,
                "workflow_run_id": workflow_run_ids[idx % len(workflow_run_ids)],
                "action_type": "CREATE_TASK",
                "status": action_statuses[idx % len(action_statuses)],
                "input_json": {"params_json": {"seed_index": idx}},
                "output_json": {},
                "error_json": {},
            },
        )

    for idx, (name, version, packs) in enumerate(AGENT_DEFS):
        agent_def_id = _uid("agent-def", idx, name, version)
        _upsert(
            db,
            AgentDefinition,
            lookup={"id": agent_def_id},
            defaults={
                "name": name,
                "version": version,
                "enabled": True,
                "supported_packs_json": packs,
                "config_json": {"seed": SEED_VERSION},
            },
        )

    agent_run_ids: list[uuid.UUID] = []
    agent_statuses = [
        AgentRunStatus.PROPOSED,
        AgentRunStatus.APPROVED,
        AgentRunStatus.BLOCKED,
        AgentRunStatus.SUCCEEDED,
        AgentRunStatus.EXECUTING,
        AgentRunStatus.PLANNED,
    ]
    agent_names = ["InboxAgent", "GrowthAgent", "PresenceAgent", "SEOAgent", "ReputationAgent", "SupervisorAgent"]
    for idx in range(6):
        run_id = _uid("agent-run", org_key, idx)
        agent_run_ids.append(run_id)
        status = agent_statuses[idx]
        _upsert(
            db,
            AgentRun,
            lookup={"id": run_id},
            defaults={
                "org_id": org_id,
                "agent_name": agent_names[idx],
                "agent_version": "1.0.0",
                "trigger_type": "manual",
                "status": status,
                "context_snapshot_json": {"seed": SEED_VERSION, "org_key": org_key},
                "perception_json": {"observations": [], "opportunities": [], "risks": []},
                "plan_json": {
                    "plan_id": str(_uid("plan", org_key, idx)),
                    "agent_name": agent_names[idx],
                    "agent_version": "1.0.0",
                    "objective": "qa validation",
                    "steps": [
                        {
                            "step_id": f"step-{idx}",
                            "action_type": "DRAFT_REPLY" if idx % 2 == 0 else "SCHEDULE_PUBLISH",
                            "target_ref": f"lead:{idx}",
                            "inputs_json": {"channel": "meta", "schedule_at": "2026-03-04T12:00:00Z"},
                            "expected_outcome": "qa",
                            "risk_tier": 2 if idx == 2 else 1,
                            "requires_approval": idx in (2, 4),
                        }
                    ],
                    "overall_risk_tier": 2 if idx == 2 else 1,
                    "rationale": "qa seed",
                    "rollback_strategy": "none",
                    "limits": {"max_exec_time_seconds": 120, "max_steps": 10},
                },
                "started_at": ANCHOR - timedelta(hours=idx + 1),
                "finished_at": ANCHOR - timedelta(hours=idx) if status in {AgentRunStatus.SUCCEEDED, AgentRunStatus.BLOCKED} else None,
                "error_json": {} if status != AgentRunStatus.BLOCKED else {"approval_required": True},
            },
        )

    approval_statuses = [
        ApprovalStatus.PENDING,
        ApprovalStatus.PENDING,
        ApprovalStatus.PENDING,
        ApprovalStatus.PENDING,
        ApprovalStatus.APPROVED,
        ApprovalStatus.APPROVED,
        ApprovalStatus.REJECTED,
        ApprovalStatus.REJECTED,
    ]
    for idx, status in enumerate(approval_statuses):
        is_agent = idx < 4
        entity_id = agent_run_ids[idx % len(agent_run_ids)] if is_agent else action_ids[idx % len(action_ids)]
        decided_by = None if status == ApprovalStatus.PENDING else member_id
        decided_at = None if status == ApprovalStatus.PENDING else ANCHOR - timedelta(hours=idx)
        _upsert(
            db,
            Approval,
            lookup={"id": _uid("approval", org_key, idx)},
            defaults={
                "org_id": org_id,
                "entity_type": ApprovalEntityType.AGENT_RUN if is_agent else ApprovalEntityType.WORKFLOW_ACTION_RUN,
                "entity_id": entity_id,
                "status": status,
                "requested_by": admin_id,
                "decided_by": decided_by,
                "decided_at": decided_at,
                "notes": f"qa approval {idx}",
            },
        )


def _seed_metrics_and_compliance(db: Session, org_id: uuid.UUID, org_key: str) -> None:
    _upsert(
        db,
        ModelMetadata,
        lookup={"org_id": org_id, "name": "lead_score_model", "version": "qa-v1"},
        defaults={
            "id": _uid("model-metadata", org_key),
            "training_window": "90d",
            "metrics_json": {"auc": 0.78, "precision": 0.72, "recall": 0.69},
            "status": ModelStatus.EXPERIMENTAL,
            "trained_at": ANCHOR - timedelta(days=2),
        },
    )
    month_start = date(2026, 3, 1)
    month_end = date(2026, 3, 31)
    for idx, metric in enumerate(
        [
            UsageMetricType.POST_CREATED,
            UsageMetricType.AI_GENERATION,
            UsageMetricType.WORKFLOW_EXECUTED,
            UsageMetricType.AD_IMPRESSION,
            UsageMetricType.USER_CREATED,
        ]
    ):
        _upsert(
            db,
            UsageMetric,
            lookup={"org_id": org_id, "metric_type": metric, "period_start": month_start, "period_end": month_end},
            defaults={
                "id": _uid("usage-metric", org_key, idx),
                "count": 10 * (idx + 1),
            },
        )

    _upsert(
        db,
        DataRetentionPolicy,
        lookup={"org_id": org_id, "entity_type": "lead"},
        defaults={
            "id": _uid("retention-policy", org_key),
            "retention_days": 365,
            "hard_delete_after_days": 395,
        },
    )


def _seed_full_org_dataset(db: Session, spec: OrgSpec, org_id: uuid.UUID, admin_id: uuid.UUID, member_id: uuid.UUID) -> None:
    lead_ids = _seed_leads(db, org_id, spec.key)
    _seed_inbox(db, org_id, spec.key, lead_ids, admin_id)
    _seed_events(db, org_id, spec.key, sla_breaches=3 if spec.key == "alpha" else 1)
    _seed_content_and_publish(db, org_id, spec.key, admin_id, spec.pack_slug)
    _seed_presence_seo_reputation(db, org_id, spec.key)
    _seed_workflows_agents_and_approvals(db, org_id, spec.key, admin_id, member_id)
    _seed_metrics_and_compliance(db, org_id, spec.key)


def main() -> None:
    if os.getenv("ALLOW_QA_SEED", "").lower() not in {"1", "true", "yes"}:
        raise SystemExit("Refusing to run qa seed. Set ALLOW_QA_SEED=true.")
    if not inspect(engine).has_table("orgs"):
        raise SystemExit("Database schema is not ready (missing table: orgs). Run `pnpm run migrate` first.")

    with SessionLocal() as db:
        for spec in ORGS:
            org_id, admin_id, member_id = _seed_org_basics(db, spec)
            _seed_plan_and_subscription(db, org_id, spec.key)
            if spec.include_full_dataset:
                _seed_full_org_dataset(db, spec, org_id, admin_id, member_id)
            db.flush()
        db.commit()

    print(f"Seed complete: {SEED_VERSION}")


if __name__ == "__main__":
    main()



