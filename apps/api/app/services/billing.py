from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    BillingSubscriptionStatus,
    Org,
    OrgStatus,
    OrgSubscription,
    SubscriptionPlan,
    UsageMetric,
    UsageMetricType,
)
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..tenancy import RequestContext

DEFAULT_PLANS: tuple[dict[str, Any], ...] = (
    {
        "name": "Free",
        "price_monthly_usd": 0.0,
        "price_yearly_usd": 0.0,
        "entitlements_json": {
            "max_org_users": 2,
            "max_monthly_posts": 20,
            "max_monthly_ai_generations": 50,
            "max_workflows": 3,
            "ads_enabled": False,
            "real_estate_pack_enabled": False,
            "home_care_pack_enabled": False,
            "priority_support": False,
            "advanced_analytics": False,
        },
    },
    {
        "name": "Starter",
        "price_monthly_usd": 49.0,
        "price_yearly_usd": 490.0,
        "entitlements_json": {
            "max_org_users": 5,
            "max_monthly_posts": 120,
            "max_monthly_ai_generations": 300,
            "max_workflows": 10,
            "ads_enabled": False,
            "real_estate_pack_enabled": True,
            "home_care_pack_enabled": False,
            "priority_support": False,
            "advanced_analytics": True,
        },
    },
    {
        "name": "Growth",
        "price_monthly_usd": 199.0,
        "price_yearly_usd": 1990.0,
        "entitlements_json": {
            "max_org_users": 20,
            "max_monthly_posts": 1000,
            "max_monthly_ai_generations": 3000,
            "max_workflows": 50,
            "ads_enabled": True,
            "real_estate_pack_enabled": True,
            "home_care_pack_enabled": True,
            "priority_support": True,
            "advanced_analytics": True,
        },
    },
    {
        "name": "Enterprise",
        "price_monthly_usd": 999.0,
        "price_yearly_usd": 9990.0,
        "entitlements_json": {
            "max_org_users": 1000,
            "max_monthly_posts": 100000,
            "max_monthly_ai_generations": 100000,
            "max_workflows": 1000,
            "ads_enabled": True,
            "real_estate_pack_enabled": True,
            "home_care_pack_enabled": True,
            "priority_support": True,
            "advanced_analytics": True,
        },
    },
)

DEFAULT_GRACE_DAYS = 7


@dataclass
class BillingSnapshot:
    org_status: OrgStatus
    subscription_status: BillingSubscriptionStatus
    plan_name: str
    current_period_end: datetime | None
    trial_end: datetime | None
    entitlements: dict[str, Any]


class StripeService:
    # Mock-first deterministic integration for CI/tests.
    def create_customer(self, org_id: uuid.UUID) -> str:
        return f"cus_{str(org_id).replace('-', '')[:24]}"

    def create_checkout_session(self, org_id: uuid.UUID, plan_id: uuid.UUID) -> dict[str, str]:
        token = str(org_id).replace("-", "")[:8]
        return {
            "id": f"cs_test_{token}",
            "url": f"https://stripe.mock/checkout/{plan_id}",
        }

    def cancel_subscription(self, stripe_subscription_id: str) -> dict[str, str]:
        return {"id": stripe_subscription_id, "status": "canceled"}

    def update_subscription_plan(self, stripe_subscription_id: str, plan_id: uuid.UUID) -> dict[str, str]:
        return {"id": stripe_subscription_id, "plan_id": str(plan_id)}


def _month_bounds(today: date | None = None) -> tuple[date, date]:
    target = today or date.today()
    start = date(target.year, target.month, 1)
    if target.month == 12:
        end = date(target.year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(target.year, target.month + 1, 1) - timedelta(days=1)
    return start, end


def seed_default_plans(db: Session) -> None:
    existing = {row.name for row in db.scalars(select(SubscriptionPlan).where(SubscriptionPlan.deleted_at.is_(None))).all()}
    for item in DEFAULT_PLANS:
        if item["name"] in existing:
            continue
        db.add(
            SubscriptionPlan(
                name=str(item["name"]),
                price_monthly_usd=float(item["price_monthly_usd"]),
                price_yearly_usd=float(item["price_yearly_usd"]),
                entitlements_json=dict(item["entitlements_json"]),
            )
        )
    db.flush()


def _get_plan_by_name(db: Session, name: str) -> SubscriptionPlan:
    row = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.name == name, SubscriptionPlan.deleted_at.is_(None)))
    if row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="subscription plan missing")
    return row


def _get_org(db: Session, org_id: uuid.UUID) -> Org:
    row = db.scalar(select(Org).where(Org.id == org_id, Org.deleted_at.is_(None)))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="org not found")
    return row


def get_or_create_subscription(db: Session, org_id: uuid.UUID) -> OrgSubscription:
    row = db.scalar(
        select(OrgSubscription).where(OrgSubscription.org_id == org_id, OrgSubscription.deleted_at.is_(None))
    )
    if row is not None:
        return row

    seed_default_plans(db)
    free_plan = _get_plan_by_name(db, "Free")
    now = datetime.now(timezone.utc)
    row = OrgSubscription(
        org_id=org_id,
        plan_id=free_plan.id,
        status=BillingSubscriptionStatus.TRIALING,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        trial_end=now + timedelta(days=14),
    )
    db.add(row)
    db.flush()
    return row


def get_billing_snapshot(db: Session, org_id: uuid.UUID) -> BillingSnapshot:
    org = _get_org(db=db, org_id=org_id)
    sub = get_or_create_subscription(db=db, org_id=org_id)
    plan = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.id == sub.plan_id))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="subscription plan missing")
    entitlements = plan.entitlements_json if isinstance(plan.entitlements_json, dict) else {}
    return BillingSnapshot(
        org_status=org.org_status,
        subscription_status=sub.status,
        plan_name=plan.name,
        current_period_end=sub.current_period_end,
        trial_end=sub.trial_end,
        entitlements=entitlements,
    )


def get_usage_remaining(db: Session, org_id: uuid.UUID, metric_type: UsageMetricType, limit_value: int) -> int:
    month_start, month_end = _month_bounds()
    used = db.scalar(
        select(func.coalesce(func.sum(UsageMetric.count), 0)).where(
            UsageMetric.org_id == org_id,
            UsageMetric.metric_type == metric_type,
            UsageMetric.period_start >= month_start,
            UsageMetric.period_end <= month_end,
            UsageMetric.deleted_at.is_(None),
        )
    )
    used_int = int(used or 0)
    return max(0, limit_value - used_int)


def increment_usage(db: Session, org_id: uuid.UUID, metric_type: UsageMetricType, count: int = 1) -> UsageMetric:
    month_start, month_end = _month_bounds()
    row = db.scalar(
        select(UsageMetric).where(
            UsageMetric.org_id == org_id,
            UsageMetric.metric_type == metric_type,
            UsageMetric.period_start == month_start,
            UsageMetric.period_end == month_end,
            UsageMetric.deleted_at.is_(None),
        )
    )
    if row is None:
        row = UsageMetric(
            org_id=org_id,
            metric_type=metric_type,
            count=max(0, count),
            period_start=month_start,
            period_end=month_end,
        )
        db.add(row)
        db.flush()
        return row
    row.count = max(0, int(row.count) + max(0, count))
    db.flush()
    return row


def is_feature_enabled(db: Session, org_id: uuid.UUID, feature_key: str) -> bool:
    snapshot = get_billing_snapshot(db=db, org_id=org_id)
    value = snapshot.entitlements.get(feature_key)
    return value is True


def _entitlement_limit(snapshot: BillingSnapshot, metric_type: UsageMetricType) -> int | None:
    mapping: dict[UsageMetricType, str] = {
        UsageMetricType.POST_CREATED: "max_monthly_posts",
        UsageMetricType.AI_GENERATION: "max_monthly_ai_generations",
        UsageMetricType.WORKFLOW_EXECUTED: "max_workflows",
        UsageMetricType.USER_CREATED: "max_org_users",
        UsageMetricType.AD_IMPRESSION: "max_monthly_posts",
    }
    key = mapping.get(metric_type)
    raw = snapshot.entitlements.get(key) if key else None
    return int(raw) if isinstance(raw, int) else None


def assert_usage_allowed(db: Session, org_id: uuid.UUID, metric_type: UsageMetricType, increment: int = 1) -> None:
    snapshot = get_billing_snapshot(db=db, org_id=org_id)
    limit_value = _entitlement_limit(snapshot, metric_type)
    if limit_value is None:
        return
    remaining = get_usage_remaining(db=db, org_id=org_id, metric_type=metric_type, limit_value=limit_value)
    if remaining < increment:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="USAGE_LIMIT_EXCEEDED")


def ensure_org_active(db: Session, org_id: uuid.UUID) -> None:
    org = _get_org(db=db, org_id=org_id)
    if org.org_status != OrgStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ORG_NOT_ACTIVE")


def apply_subscription_status_to_org(db: Session, org_id: uuid.UUID, grace_days: int = DEFAULT_GRACE_DAYS) -> OrgStatus:
    org = _get_org(db=db, org_id=org_id)
    sub = get_or_create_subscription(db=db, org_id=org_id)

    if sub.status in {BillingSubscriptionStatus.ACTIVE, BillingSubscriptionStatus.TRIALING}:
        org.org_status = OrgStatus.ACTIVE
        db.flush()
        return org.org_status

    if sub.status == BillingSubscriptionStatus.CANCELED:
        org.org_status = OrgStatus.CANCELED
        db.flush()
        return org.org_status

    if sub.status in {BillingSubscriptionStatus.PAST_DUE, BillingSubscriptionStatus.SUSPENDED}:
        past_grace = False
        if sub.current_period_end is not None:
            past_grace = datetime.now(timezone.utc) >= (sub.current_period_end + timedelta(days=grace_days))
        if past_grace or sub.status == BillingSubscriptionStatus.SUSPENDED:
            org.org_status = OrgStatus.SUSPENDED
            db.flush()
            return org.org_status

    return org.org_status


def track_billing_update_event(
    db: Session,
    context: RequestContext,
    action: str,
    target_id: str,
    metadata_json: dict[str, Any],
) -> None:
    write_audit_log(
        db=db,
        context=context,
        action=action,
        target_type="billing",
        target_id=target_id,
        metadata_json=metadata_json,
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="billing",
        channel="billing",
        event_type="BILLING_UPDATED",
        payload_json=metadata_json,
        actor_id=str(context.current_user_id),
    )


def summarize_revenue(db: Session) -> dict[str, Any]:
    subs = db.scalars(select(OrgSubscription).where(OrgSubscription.deleted_at.is_(None))).all()
    plans = {row.id: row for row in db.scalars(select(SubscriptionPlan).where(SubscriptionPlan.deleted_at.is_(None))).all()}
    mrr = 0.0
    churn = 0
    active = 0
    distribution: dict[str, int] = {}
    for sub in subs:
        plan = plans.get(sub.plan_id)
        if plan is None:
            continue
        distribution[plan.name] = distribution.get(plan.name, 0) + 1
        if sub.status in {BillingSubscriptionStatus.ACTIVE, BillingSubscriptionStatus.TRIALING}:
            mrr += float(plan.price_monthly_usd)
            active += 1
        if sub.status in {BillingSubscriptionStatus.CANCELED, BillingSubscriptionStatus.SUSPENDED}:
            churn += 1
    return {
        "mrr_usd": round(mrr, 2),
        "arr_projection_usd": round(mrr * 12, 2),
        "active_subscriptions": active,
        "churn_count": churn,
        "plan_distribution": distribution,
    }


def ensure_global_admin(db: Session, user_id: uuid.UUID) -> None:
    from ..models import GlobalAdmin

    row = db.scalar(
        select(GlobalAdmin).where(
            GlobalAdmin.user_id == user_id,
            GlobalAdmin.active.is_(True),
            GlobalAdmin.deleted_at.is_(None),
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="global admin required")
