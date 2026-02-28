from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Event, Org, OrgStatus, Role, VerticalPack, VerticalPackRegistry
from ..schemas import (
    AdminBillingOverviewResponse,
    AdminImpersonationResponse,
    AdminOrgResponse,
    AdminVerticalPerformanceResponse,
    AdminVerticalRegistryResponse,
)
from ..services.audit import write_audit_log
from ..services.billing import ensure_global_admin, summarize_revenue
from ..services.events import write_event
from ..tenancy import RequestContext, get_request_context, require_role

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_global_admin(db: Session, context: RequestContext) -> None:
    require_role(context, Role.OWNER)
    ensure_global_admin(db=db, user_id=context.current_user_id)


@router.get("/orgs", response_model=list[AdminOrgResponse])
def list_orgs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[AdminOrgResponse]:
    _require_global_admin(db=db, context=context)
    rows = db.scalars(
        select(Org)
        .where(Org.deleted_at.is_(None))
        .order_by(Org.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        AdminOrgResponse(id=row.id, name=row.name, org_status=row.org_status.value, created_at=row.created_at)
        for row in rows
    ]


@router.get("/orgs/{org_id}", response_model=AdminOrgResponse)
def get_org(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdminOrgResponse:
    _require_global_admin(db=db, context=context)
    row = db.scalar(select(Org).where(Org.id == org_id, Org.deleted_at.is_(None)))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="org not found")
    return AdminOrgResponse(id=row.id, name=row.name, org_status=row.org_status.value, created_at=row.created_at)


@router.post("/orgs/{org_id}/impersonate", response_model=AdminImpersonationResponse)
def impersonate_org(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdminImpersonationResponse:
    _require_global_admin(db=db, context=context)
    org = db.scalar(select(Org).where(Org.id == org_id, Org.deleted_at.is_(None)))
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="org not found")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    token = f"imp_{uuid.uuid4().hex}"
    metadata = {"target_org_id": str(org.id), "expires_at": expires_at.isoformat()}

    write_audit_log(
        db=db,
        context=context,
        action="admin.impersonation.started",
        target_type="org",
        target_id=str(org.id),
        metadata_json=metadata,
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="admin",
        channel="admin",
        event_type="ADMIN_IMPERSONATION_STARTED",
        payload_json=metadata,
        actor_id=str(context.current_user_id),
    )
    db.commit()
    return AdminImpersonationResponse(org_id=org.id, impersonation_token=token, expires_at=expires_at)


@router.post("/orgs/{org_id}/suspend", response_model=AdminOrgResponse)
def suspend_org(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdminOrgResponse:
    _require_global_admin(db=db, context=context)
    org = db.scalar(select(Org).where(Org.id == org_id, Org.deleted_at.is_(None)))
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="org not found")

    org.org_status = OrgStatus.SUSPENDED
    write_audit_log(
        db=db,
        context=context,
        action="admin.org.suspended",
        target_type="org",
        target_id=str(org.id),
        metadata_json={"org_status": OrgStatus.SUSPENDED.value},
    )
    write_event(
        db=db,
        org_id=org.id,
        source="billing",
        channel="billing",
        event_type="ORG_SUSPENDED",
        payload_json={"reason": "admin_action"},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    return AdminOrgResponse(id=org.id, name=org.name, org_status=org.org_status.value, created_at=org.created_at)


@router.post("/orgs/{org_id}/reactivate", response_model=AdminOrgResponse)
def reactivate_org(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdminOrgResponse:
    _require_global_admin(db=db, context=context)
    org = db.scalar(select(Org).where(Org.id == org_id, Org.deleted_at.is_(None)))
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="org not found")

    org.org_status = OrgStatus.ACTIVE
    write_audit_log(
        db=db,
        context=context,
        action="admin.org.reactivated",
        target_type="org",
        target_id=str(org.id),
        metadata_json={"org_status": OrgStatus.ACTIVE.value},
    )
    write_event(
        db=db,
        org_id=org.id,
        source="billing",
        channel="billing",
        event_type="BILLING_UPDATED",
        payload_json={"org_status": OrgStatus.ACTIVE.value},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    return AdminOrgResponse(id=org.id, name=org.name, org_status=org.org_status.value, created_at=org.created_at)


@router.get("/billing/overview", response_model=AdminBillingOverviewResponse)
def billing_overview(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> AdminBillingOverviewResponse:
    _require_global_admin(db=db, context=context)
    snapshot = summarize_revenue(db=db)
    return AdminBillingOverviewResponse(**snapshot)


@router.get("/vertical-performance", response_model=list[AdminVerticalPerformanceResponse])
def vertical_performance(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[AdminVerticalPerformanceResponse]:
    _require_global_admin(db=db, context=context)

    org_counts = {
        str(slug): int(count)
        for slug, count in db.execute(
            select(VerticalPack.pack_slug, func.count(VerticalPack.id))
            .where(VerticalPack.deleted_at.is_(None))
            .group_by(VerticalPack.pack_slug)
            .order_by(VerticalPack.pack_slug.asc())
        ).all()
    }

    metric_rows = db.execute(
        select(
            VerticalPack.pack_slug,
            func.sum(case((Event.type.like("%LEAD%"), 1), else_=0)),
            func.sum(case((Event.type.like("%BILLING%"), 1), else_=0)),
            func.sum(case((Event.type.like("%WORKFLOW%"), 1), else_=0)),
            func.sum(case((Event.type.like("%PREDICTIVE%"), 1), else_=0)),
        )
        .select_from(VerticalPack)
        .join(Event, Event.org_id == VerticalPack.org_id)
        .where(VerticalPack.deleted_at.is_(None), Event.deleted_at.is_(None))
        .group_by(VerticalPack.pack_slug)
        .order_by(VerticalPack.pack_slug.asc())
    ).all()

    by_slug: dict[str, AdminVerticalPerformanceResponse] = {
        slug: AdminVerticalPerformanceResponse(pack_slug=slug, org_count=count)
        for slug, count in org_counts.items()
    }

    for slug, funnel, revenue, automation, predictive in metric_rows:
        key = str(slug)
        base = by_slug.get(key)
        if base is None:
            base = AdminVerticalPerformanceResponse(pack_slug=key, org_count=0)
            by_slug[key] = base
        base.funnel_events = int(funnel or 0)
        base.revenue_events = int(revenue or 0)
        base.automation_events = int(automation or 0)
        base.predictive_events = int(predictive or 0)

    return sorted(by_slug.values(), key=lambda item: item.pack_slug)


@router.get("/verticals", response_model=list[AdminVerticalRegistryResponse])
def list_vertical_registry(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[AdminVerticalRegistryResponse]:
    _require_global_admin(db=db, context=context)
    rows = db.scalars(
        select(VerticalPackRegistry)
        .where(VerticalPackRegistry.deleted_at.is_(None))
        .order_by(VerticalPackRegistry.installed_at.desc())
    ).all()
    return [
        AdminVerticalRegistryResponse(
            slug=row.slug,
            version=row.version,
            status=row.status,
            checksum=row.checksum,
            installed_at=row.installed_at,
        )
        for row in rows
    ]


