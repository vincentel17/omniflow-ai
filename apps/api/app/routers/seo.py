from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PresenceFinding, RiskTier, SEOWorkItem, SEOWorkItemStatus, SEOWorkItemType, VerticalPack
from ..schemas import (
    SEOPlanRequest,
    SEOPlanResponse,
    SEOWorkItemApproveRequest,
    SEOWorkItemCreateRequest,
    SEOWorkItemResponse,
)
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..services.phase5 import build_seo_content, build_seo_plan
from ..services.policy import load_policy_engine
from ..tenancy import RequestContext, get_request_context, org_scoped

router = APIRouter(prefix="/seo", tags=["seo"])


def _pack_slug(db: Session, org_id: uuid.UUID) -> str:
    row = db.scalar(
        org_scoped(select(VerticalPack).where(VerticalPack.deleted_at.is_(None)), org_id, VerticalPack)
    )
    return "generic" if row is None else row.pack_slug


def _serialize_work_item(row: SEOWorkItem) -> SEOWorkItemResponse:
    return SEOWorkItemResponse(
        id=row.id,
        org_id=row.org_id,
        type=row.type,
        status=row.status,
        target_keyword=row.target_keyword,
        target_location=row.target_location,
        url_slug=row.url_slug,
        content_json=row.content_json,
        rendered_markdown=row.rendered_markdown,
        risk_tier=row.risk_tier,
        policy_warnings_json=row.policy_warnings_json,
        created_at=row.created_at,
    )


@router.post("/plan", response_model=SEOPlanResponse)
def generate_seo_plan(
    payload: SEOPlanRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> SEOPlanResponse:
    pack_slug = _pack_slug(db, context.current_org_id)
    latest_findings: list[PresenceFinding] | None = None
    if payload.audit_run_id is not None:
        latest_findings = list(
            db.scalars(
                org_scoped(
                    select(PresenceFinding).where(
                        PresenceFinding.audit_run_id == payload.audit_run_id,
                        PresenceFinding.deleted_at.is_(None),
                    ),
                    context.current_org_id,
                    PresenceFinding,
                )
            ).all()
        )
    plan = build_seo_plan(pack_slug=pack_slug, locations=payload.target_locations, latest_findings=latest_findings)
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="seo",
        channel="planning",
        event_type="SEO_PLAN_GENERATED",
        payload_json={"service_pages": len(plan.service_pages), "clusters": len(plan.blog_clusters)},
        actor_id=str(context.current_user_id),
    )
    write_audit_log(
        db=db,
        context=context,
        action="seo.plan_generated",
        target_type="seo_plan",
        target_id=f"org:{context.current_org_id}",
        metadata_json={"service_pages": len(plan.service_pages), "clusters": len(plan.blog_clusters)},
        risk_tier=RiskTier.TIER_1,
    )
    db.commit()
    return SEOPlanResponse(**plan.model_dump(mode="json"))


@router.post("/work-items", response_model=SEOWorkItemResponse, status_code=status.HTTP_201_CREATED)
def create_seo_work_item(
    payload: SEOWorkItemCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> SEOWorkItemResponse:
    policy = load_policy_engine(_pack_slug(db, context.current_org_id))
    validation = policy.validate_content(str(payload.content_json), context={"surface": "seo"})
    risk_tier = RiskTier(policy.risk_tier("seo_workitem_create", context={"surface": "seo"}).value)
    row = SEOWorkItem(
        org_id=context.current_org_id,
        type=payload.type,
        status=SEOWorkItemStatus.DRAFT,
        target_keyword=payload.target_keyword,
        target_location=payload.target_location,
        url_slug=payload.url_slug,
        content_json=payload.content_json,
        rendered_markdown=None,
        risk_tier=risk_tier,
        policy_warnings_json=validation.reasons,
    )
    db.add(row)
    db.flush()
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="seo",
        channel="workitem",
        event_type="SEO_WORKITEM_CREATED",
        payload_json={"work_item_id": str(row.id), "type": row.type.value},
        actor_id=str(context.current_user_id),
    )
    write_audit_log(
        db=db,
        context=context,
        action="seo.workitem_created",
        target_type="seo_work_item",
        target_id=str(row.id),
        metadata_json={"type": row.type.value},
        risk_tier=row.risk_tier,
    )
    db.commit()
    db.refresh(row)
    return _serialize_work_item(row)


def _get_work_item(db: Session, context: RequestContext, work_item_id: uuid.UUID) -> SEOWorkItem:
    row = db.scalar(
        org_scoped(
            select(SEOWorkItem).where(SEOWorkItem.id == work_item_id, SEOWorkItem.deleted_at.is_(None)),
            context.current_org_id,
            SEOWorkItem,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="seo work item not found")
    return row


@router.post("/work-items/{work_item_id}/generate", response_model=SEOWorkItemResponse)
def generate_seo_content(
    work_item_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> SEOWorkItemResponse:
    row = _get_work_item(db=db, context=context, work_item_id=work_item_id)
    policy = load_policy_engine(_pack_slug(db, context.current_org_id))
    title_value = row.content_json.get("title") if isinstance(row.content_json, dict) else None
    title = str(title_value) if isinstance(title_value, str) and title_value else row.target_keyword.title()
    content, warnings, risk_tier = build_seo_content(
        title=title,
        slug=row.url_slug,
        keyword=row.target_keyword,
        location=row.target_location,
        policy=policy,
    )
    row.content_json = content.model_dump(mode="json", by_alias=True)
    row.rendered_markdown = content.body_markdown
    row.policy_warnings_json = warnings
    row.risk_tier = risk_tier
    db.flush()
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="seo",
        channel="workitem",
        event_type="SEO_CONTENT_GENERATED",
        payload_json={"work_item_id": str(row.id)},
        actor_id=str(context.current_user_id),
    )
    write_audit_log(
        db=db,
        context=context,
        action="seo.content_generated",
        target_type="seo_work_item",
        target_id=str(row.id),
        metadata_json={"warnings": warnings},
        risk_tier=row.risk_tier,
    )
    db.commit()
    db.refresh(row)
    return _serialize_work_item(row)


@router.post("/work-items/{work_item_id}/approve", response_model=SEOWorkItemResponse)
def approve_seo_work_item(
    work_item_id: uuid.UUID,
    payload: SEOWorkItemApproveRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> SEOWorkItemResponse:
    row = _get_work_item(db=db, context=context, work_item_id=work_item_id)
    if payload.status not in {SEOWorkItemStatus.APPROVED, SEOWorkItemStatus.ARCHIVED}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid approval status")
    row.status = payload.status
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="seo.workitem_approved",
        target_type="seo_work_item",
        target_id=str(row.id),
        metadata_json={"status": row.status.value},
        risk_tier=row.risk_tier,
    )
    db.commit()
    db.refresh(row)
    return _serialize_work_item(row)


@router.get("/work-items", response_model=list[SEOWorkItemResponse])
def list_seo_work_items(
    type_filter: str | None = Query(default=None, alias="type"),
    status_filter: SEOWorkItemStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[SEOWorkItemResponse]:
    stmt = org_scoped(
        select(SEOWorkItem)
        .where(SEOWorkItem.deleted_at.is_(None))
        .order_by(desc(SEOWorkItem.created_at))
        .limit(limit)
        .offset(offset),
        context.current_org_id,
        SEOWorkItem,
    )
    if type_filter is not None:
        try:
            parsed_type = SEOWorkItemType(type_filter)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid seo type") from exc
        stmt = stmt.where(SEOWorkItem.type == parsed_type)
    if status_filter is not None:
        stmt = stmt.where(SEOWorkItem.status == status_filter)
    rows = db.scalars(stmt).all()
    return [_serialize_work_item(row) for row in rows]


@router.get("/work-items/{work_item_id}", response_model=SEOWorkItemResponse)
def get_seo_work_item(
    work_item_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> SEOWorkItemResponse:
    return _serialize_work_item(_get_work_item(db=db, context=context, work_item_id=work_item_id))


@router.get("/work-items/{work_item_id}/export")
def export_seo_markdown(
    work_item_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> Response:
    row = _get_work_item(db=db, context=context, work_item_id=work_item_id)
    return Response(content=row.rendered_markdown or "", media_type="text/markdown")
