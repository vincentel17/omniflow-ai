from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import BillingSubscriptionStatus, Role, SubscriptionPlan, UsageMetricType
from ..schemas import (
    BillingCheckoutRequest,
    BillingCheckoutResponse,
    BillingPlanResponse,
    BillingStatusResponse,
    BillingSubscriptionResponse,
    BillingWebhookRequest,
)
from ..services.billing import (
    StripeService,
    apply_subscription_status_to_org,
    get_or_create_subscription,
    get_usage_remaining,
    increment_usage,
    seed_default_plans,
    track_billing_update_event,
)
from ..tenancy import RequestContext, get_request_context, require_role

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=list[BillingPlanResponse])
def list_plans(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[BillingPlanResponse]:
    require_role(context, Role.AGENT)
    seed_default_plans(db)
    rows = db.scalars(select(SubscriptionPlan).where(SubscriptionPlan.deleted_at.is_(None))).all()
    db.commit()
    return [
        BillingPlanResponse(
            id=row.id,
            name=row.name,
            price_monthly_usd=row.price_monthly_usd,
            price_yearly_usd=row.price_yearly_usd,
            entitlements_json=row.entitlements_json if isinstance(row.entitlements_json, dict) else {},
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/checkout", response_model=BillingCheckoutResponse)
def create_checkout(
    payload: BillingCheckoutRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> BillingCheckoutResponse:
    require_role(context, Role.ADMIN)
    plan = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.id == payload.plan_id, SubscriptionPlan.deleted_at.is_(None)))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="plan not found")

    stripe = StripeService()
    session = stripe.create_checkout_session(org_id=context.current_org_id, plan_id=plan.id)
    track_billing_update_event(
        db=db,
        context=context,
        action="billing.checkout_created",
        target_id=str(plan.id),
        metadata_json={"plan_id": str(plan.id), "checkout_session_id": session["id"]},
    )
    db.commit()
    return BillingCheckoutResponse(checkout_session_id=session["id"], checkout_url=session["url"])


@router.get("/subscription", response_model=BillingSubscriptionResponse)
def get_subscription(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> BillingSubscriptionResponse:
    require_role(context, Role.AGENT)
    sub = get_or_create_subscription(db=db, org_id=context.current_org_id)
    plan = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.id == sub.plan_id))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="plan missing")
    return BillingSubscriptionResponse(
        id=sub.id,
        org_id=sub.org_id,
        stripe_customer_id=sub.stripe_customer_id,
        stripe_subscription_id=sub.stripe_subscription_id,
        plan_id=sub.plan_id,
        plan_name=plan.name,
        status=sub.status,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        trial_end=sub.trial_end,
        created_at=sub.created_at,
    )


@router.post("/change-plan", response_model=BillingSubscriptionResponse)
def change_plan(
    payload: BillingCheckoutRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> BillingSubscriptionResponse:
    require_role(context, Role.ADMIN)
    plan = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.id == payload.plan_id, SubscriptionPlan.deleted_at.is_(None)))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="plan not found")

    sub = get_or_create_subscription(db=db, org_id=context.current_org_id)
    sub.plan_id = plan.id
    sub.status = BillingSubscriptionStatus.ACTIVE
    now = datetime.now(timezone.utc)
    sub.current_period_start = now
    sub.current_period_end = now + timedelta(days=30)
    apply_subscription_status_to_org(db=db, org_id=context.current_org_id)

    track_billing_update_event(
        db=db,
        context=context,
        action="billing.plan_changed",
        target_id=str(sub.id),
        metadata_json={"plan_id": str(plan.id), "plan_name": plan.name},
    )
    db.commit()
    return get_subscription(db=db, context=context)


@router.post("/cancel", response_model=BillingSubscriptionResponse)
def cancel_subscription(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> BillingSubscriptionResponse:
    require_role(context, Role.ADMIN)
    sub = get_or_create_subscription(db=db, org_id=context.current_org_id)
    sub.status = BillingSubscriptionStatus.CANCELED
    apply_subscription_status_to_org(db=db, org_id=context.current_org_id)

    track_billing_update_event(
        db=db,
        context=context,
        action="billing.subscription_canceled",
        target_id=str(sub.id),
        metadata_json={"subscription_id": str(sub.id)},
    )
    db.commit()
    return get_subscription(db=db, context=context)


@router.get("/status", response_model=BillingStatusResponse)
def billing_status(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> BillingStatusResponse:
    require_role(context, Role.AGENT)
    sub = get_or_create_subscription(db=db, org_id=context.current_org_id)
    org_status = apply_subscription_status_to_org(db=db, org_id=context.current_org_id)
    db.commit()
    return BillingStatusResponse(org_status=org_status, subscription_status=sub.status)


@router.post("/webhook")
def stripe_webhook(
    payload: BillingWebhookRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    event_type = payload.event_type
    data = payload.data
    org_id_raw = data.get("org_id")
    if not isinstance(org_id_raw, str):
        return {"processed": False, "reason": "missing_org_id"}

    try:
        org_id = uuid.UUID(org_id_raw)
    except ValueError:
        return {"processed": False, "reason": "invalid_org_id"}

    sub = get_or_create_subscription(db=db, org_id=org_id)

    if event_type == "checkout.session.completed":
        plan_id_raw = data.get("plan_id")
        if isinstance(plan_id_raw, str):
            try:
                plan_id = uuid.UUID(plan_id_raw)
            except ValueError:
                plan_id = None
            plan = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)) if plan_id else None
            if plan is not None:
                sub.plan_id = plan.id
        subscription_id = data.get("stripe_subscription_id")
        customer_id = data.get("stripe_customer_id")
        if isinstance(subscription_id, str) and subscription_id.strip():
            sub.stripe_subscription_id = subscription_id
        if isinstance(customer_id, str) and customer_id.strip():
            sub.stripe_customer_id = customer_id
        sub.status = BillingSubscriptionStatus.ACTIVE
    elif event_type == "customer.subscription.updated":
        status_value = data.get("status")
        if isinstance(status_value, str) and status_value in {item.value for item in BillingSubscriptionStatus}:
            sub.status = BillingSubscriptionStatus(status_value)
    elif event_type == "customer.subscription.deleted":
        sub.status = BillingSubscriptionStatus.CANCELED
    elif event_type == "invoice.payment_failed":
        sub.status = BillingSubscriptionStatus.PAST_DUE

    apply_subscription_status_to_org(db=db, org_id=org_id)
    db.commit()
    return {"processed": True}


@router.post("/usage/{metric_type}")
def record_usage(
    metric_type: str,
    count: int = 1,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    require_role(context, Role.ADMIN)
    lookup = {item.value: item for item in UsageMetricType}
    metric = lookup.get(metric_type)
    if metric is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid metric")
    row = increment_usage(db=db, org_id=context.current_org_id, metric_type=metric, count=count)
    db.commit()
    return {"id": str(row.id), "count": row.count}


@router.get("/usage/{metric_type}")
def get_usage(
    metric_type: str,
    limit: int,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    require_role(context, Role.ADMIN)
    lookup = {item.value: item for item in UsageMetricType}
    metric = lookup.get(metric_type)
    if metric is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid metric")
    remaining = get_usage_remaining(db=db, org_id=context.current_org_id, metric_type=metric, limit_value=limit)
    return {"remaining": remaining}




