from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from packages.schemas import CampaignPlanJSON, CampaignPlanPost, ContentItemJSON, ListingPackageJSON

from ..db import get_db
from ..models import (
    CampaignPlan,
    CampaignPlanStatus,
    ContentItem,
    ContentItemStatus,
    REChecklistItem,
    REChecklistItemStatus,
    RECommunicationLog,
    RECMAComparable,
    RECMAReport,
    REDeal,
    REDealStatus,
    REDocumentRequest,
    REListingPackage,
    REListingPackageStatus,
    RiskTier,
    Role,
)
from ..schemas import (
    ApprovalDecisionRequest,
    REChecklistApplyTemplateRequest,
    REChecklistItemResponse,
    RECommunicationLogCreateRequest,
    RECommunicationLogResponse,
    RECMACompsImportRequest,
    RECMAReportCreateRequest,
    RECMAReportResponse,
    REDealCreateRequest,
    REDealResponse,
    REDealUpdateRequest,
    REDocumentRequestCreateRequest,
    REDocumentRequestResponse,
    REListingPackageCreateRequest,
    REListingPackageResponse,
)
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..services.phase3 import get_vertical_pack_slug, should_auto_approve, utcnow
from ..services.phase7 import compute_due_at, default_checklist_items_for_deal, ensure_real_estate_pack, resolve_checklist_template
from ..services.phase7 import (
    append_disclaimers,
    build_listing_social_pack,
    calculate_cma_pricing,
    get_required_disclaimers,
    render_cma_narrative,
)
from ..services.policy import load_policy_engine
from ..services.verticals import load_pack_template
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(prefix="/re", tags=["real-estate"])


def _ensure_pack(db: Session, context: RequestContext) -> None:
    if not ensure_real_estate_pack(db=db, org_id=context.current_org_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="real-estate pack required")


def _deal(db: Session, context: RequestContext, deal_id: uuid.UUID) -> REDeal:
    row = db.scalar(org_scoped(select(REDeal).where(REDeal.id == deal_id, REDeal.deleted_at.is_(None)), context.current_org_id, REDeal))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="deal not found")
    return row


def _list_row(db: Session, context: RequestContext, listing_id: uuid.UUID) -> REListingPackage:
    row = db.scalar(
        org_scoped(select(REListingPackage).where(REListingPackage.id == listing_id, REListingPackage.deleted_at.is_(None)), context.current_org_id, REListingPackage)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing package not found")
    return row


def _cma_row(db: Session, context: RequestContext, report_id: uuid.UUID) -> RECMAReport:
    row = db.scalar(
        org_scoped(select(RECMAReport).where(RECMAReport.id == report_id, RECMAReport.deleted_at.is_(None)), context.current_org_id, RECMAReport)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cma report not found")
    return row


@router.post("/deals", response_model=REDealResponse, status_code=status.HTTP_201_CREATED)
def create_deal(payload: REDealCreateRequest, db: Session = Depends(get_db), context: RequestContext = Depends(get_request_context)) -> REDealResponse:
    require_role(context, Role.AGENT)
    _ensure_pack(db, context)
    row = REDeal(
        org_id=context.current_org_id,
        deal_type=payload.deal_type,
        status=REDealStatus.ACTIVE,
        pipeline_stage=payload.pipeline_stage,
        lead_id=payload.lead_id,
        primary_contact_name=payload.primary_contact_name,
        primary_contact_email=payload.primary_contact_email,
        primary_contact_phone=payload.primary_contact_phone,
        property_address_json=payload.property_address_json,
        important_dates_json=payload.important_dates_json,
    )
    db.add(row)
    db.flush()
    write_event(db, context.current_org_id, "real_estate", "deal", "DEAL_CREATED", {"deal_id": str(row.id)})
    write_audit_log(db, context, "deal.created", "re_deal", str(row.id))
    db.commit()
    db.refresh(row)
    return REDealResponse.model_validate(row, from_attributes=True)


@router.get("/deals", response_model=list[REDealResponse])
def list_deals(
    stage: str | None = Query(default=None),
    deal_type: str | None = Query(default=None),
    status_filter: REDealStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[REDealResponse]:
    _ensure_pack(db, context)
    stmt = org_scoped(select(REDeal).where(REDeal.deleted_at.is_(None)).order_by(desc(REDeal.created_at)).limit(limit).offset(offset), context.current_org_id, REDeal)
    if stage:
        stmt = stmt.where(REDeal.pipeline_stage == stage)
    if deal_type:
        stmt = stmt.where(REDeal.deal_type == deal_type)
    if status_filter is not None:
        stmt = stmt.where(REDeal.status == status_filter)
    return [REDealResponse.model_validate(row, from_attributes=True) for row in db.scalars(stmt).all()]


@router.get("/deals/{deal_id}", response_model=REDealResponse)
def get_deal(deal_id: uuid.UUID, db: Session = Depends(get_db), context: RequestContext = Depends(get_request_context)) -> REDealResponse:
    _ensure_pack(db, context)
    return REDealResponse.model_validate(_deal(db, context, deal_id), from_attributes=True)


@router.patch("/deals/{deal_id}", response_model=REDealResponse)
def update_deal(
    deal_id: uuid.UUID,
    payload: REDealUpdateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> REDealResponse:
    require_role(context, Role.AGENT)
    _ensure_pack(db, context)
    row = _deal(db, context, deal_id)
    old_stage = row.pipeline_stage
    if payload.status is not None:
        row.status = payload.status
    if payload.pipeline_stage is not None:
        row.pipeline_stage = payload.pipeline_stage
    if payload.property_address_json is not None:
        row.property_address_json = payload.property_address_json
    if payload.important_dates_json is not None:
        row.important_dates_json = payload.important_dates_json
    if row.pipeline_stage != old_stage:
        write_event(db, context.current_org_id, "real_estate", "deal", "DEAL_STAGE_CHANGED", {"deal_id": str(row.id), "pipeline_stage": row.pipeline_stage})
    write_audit_log(db, context, "deal.updated", "re_deal", str(row.id))
    db.commit()
    db.refresh(row)
    return REDealResponse.model_validate(row, from_attributes=True)


@router.post("/deals/{deal_id}/checklists/apply-template", response_model=list[REChecklistItemResponse])
def apply_checklist_template(
    deal_id: uuid.UUID,
    payload: REChecklistApplyTemplateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[REChecklistItemResponse]:
    require_role(context, Role.AGENT)
    _ensure_pack(db, context)
    deal = _deal(db, context, deal_id)
    tpl = resolve_checklist_template(db, context.current_org_id, deal.deal_type.value, payload.template_name, payload.state_code)
    items_json = tpl.items_json if tpl is not None and tpl.items_json else default_checklist_items_for_deal(deal)
    rows: list[REChecklistItem] = []
    for item in items_json:
        offset_raw = item.get("offset_days", 0)
        offset_days = int(offset_raw) if isinstance(offset_raw, (int, float, str)) else 0
        row = REChecklistItem(
            org_id=context.current_org_id,
            deal_id=deal.id,
            title=str(item.get("title", "Checklist item")),
            description=str(item.get("description", "")) or None,
            due_at=compute_due_at(deal.important_dates_json, str(item.get("anchor_date_field", "")) or None, offset_days),
            status=REChecklistItemStatus.OPEN,
            source_template_id=(tpl.id if tpl is not None else None),
        )
        rows.append(row)
        db.add(row)
    db.flush()
    write_event(db, context.current_org_id, "real_estate", "deal", "CHECKLIST_APPLIED", {"deal_id": str(deal.id), "items_created": len(rows)})
    write_audit_log(db, context, "checklist.applied", "re_deal", str(deal.id), {"items_created": len(rows)})
    db.commit()
    return [REChecklistItemResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/deals/{deal_id}/checklist-items/{item_id}/complete", response_model=REChecklistItemResponse)
def complete_checklist_item(
    deal_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> REChecklistItemResponse:
    require_role(context, Role.AGENT)
    _ensure_pack(db, context)
    _deal(db, context, deal_id)
    row = db.scalar(
        org_scoped(select(REChecklistItem).where(REChecklistItem.id == item_id, REChecklistItem.deal_id == deal_id, REChecklistItem.deleted_at.is_(None)), context.current_org_id, REChecklistItem)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="checklist item not found")
    row.status = REChecklistItemStatus.DONE
    write_event(db, context.current_org_id, "real_estate", "deal", "CHECKLIST_ITEM_DONE", {"deal_id": str(deal_id), "item_id": str(item_id)})
    write_audit_log(db, context, "checklist_item.completed", "re_checklist_item", str(item_id))
    db.commit()
    return REChecklistItemResponse.model_validate(row, from_attributes=True)


@router.get("/deals/{deal_id}/checklist-items", response_model=list[REChecklistItemResponse])
def list_checklist_items(
    deal_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[REChecklistItemResponse]:
    _ensure_pack(db, context)
    _deal(db, context, deal_id)
    rows = db.scalars(
        org_scoped(
            select(REChecklistItem)
            .where(REChecklistItem.deal_id == deal_id, REChecklistItem.deleted_at.is_(None))
            .order_by(desc(REChecklistItem.created_at))
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            REChecklistItem,
        )
    ).all()
    return [REChecklistItemResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/deals/{deal_id}/documents/request", response_model=REDocumentRequestResponse, status_code=status.HTTP_201_CREATED)
def create_document_request(
    deal_id: uuid.UUID,
    payload: REDocumentRequestCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> REDocumentRequestResponse:
    require_role(context, Role.AGENT)
    _ensure_pack(db, context)
    _deal(db, context, deal_id)
    row = REDocumentRequest(org_id=context.current_org_id, deal_id=deal_id, doc_type=payload.doc_type, requested_from=payload.requested_from)
    db.add(row)
    db.flush()
    write_event(db, context.current_org_id, "real_estate", "deal", "DOC_REQUESTED", {"deal_id": str(deal_id), "doc_type": payload.doc_type})
    write_audit_log(db, context, "document.requested", "re_document_request", str(row.id))
    db.commit()
    return REDocumentRequestResponse.model_validate(row, from_attributes=True)


@router.get("/deals/{deal_id}/documents", response_model=list[REDocumentRequestResponse])
def list_document_requests(
    deal_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[REDocumentRequestResponse]:
    _ensure_pack(db, context)
    _deal(db, context, deal_id)
    rows = db.scalars(
        org_scoped(
            select(REDocumentRequest)
            .where(REDocumentRequest.deal_id == deal_id, REDocumentRequest.deleted_at.is_(None))
            .order_by(desc(REDocumentRequest.created_at))
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            REDocumentRequest,
        )
    ).all()
    return [REDocumentRequestResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/deals/{deal_id}/communications/log", response_model=RECommunicationLogResponse, status_code=status.HTTP_201_CREATED)
def log_communication(
    deal_id: uuid.UUID,
    payload: RECommunicationLogCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> RECommunicationLogResponse:
    require_role(context, Role.AGENT)
    _ensure_pack(db, context)
    _deal(db, context, deal_id)
    row = RECommunicationLog(
        org_id=context.current_org_id,
        deal_id=deal_id,
        thread_id=payload.thread_id,
        channel=payload.channel,
        direction=payload.direction,
        subject=payload.subject,
        body_text=payload.body_text,
        created_by_user_id=context.current_user_id,
    )
    db.add(row)
    db.flush()
    write_event(db, context.current_org_id, "real_estate", "deal", "COMM_LOGGED", {"deal_id": str(deal_id), "channel": payload.channel.value})
    write_audit_log(db, context, "communication.logged", "re_communication_log", str(row.id))
    db.commit()
    return RECommunicationLogResponse.model_validate(row, from_attributes=True)


@router.get("/deals/{deal_id}/communications", response_model=list[RECommunicationLogResponse])
def list_communications(
    deal_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[RECommunicationLogResponse]:
    _ensure_pack(db, context)
    _deal(db, context, deal_id)
    rows = db.scalars(
        org_scoped(
            select(RECommunicationLog)
            .where(RECommunicationLog.deal_id == deal_id, RECommunicationLog.deleted_at.is_(None))
            .order_by(desc(RECommunicationLog.created_at))
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            RECommunicationLog,
        )
    ).all()
    return [RECommunicationLogResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/deals/{deal_id}/timeline/auto")
def auto_timeline(
    deal_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    _ensure_pack(db, context)
    deal = _deal(db, context, deal_id)
    write_audit_log(db, context, "deal.timeline_generated", "re_deal", str(deal.id))
    db.commit()
    return {"deal_id": str(deal.id), "timeline": [{"label": "contract_date", "value": deal.important_dates_json.get("contract_date")}]}


@router.post("/cma/reports", response_model=RECMAReportResponse, status_code=status.HTTP_201_CREATED)
def create_cma_report(
    payload: RECMAReportCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> RECMAReportResponse:
    require_role(context, Role.AGENT)
    _ensure_pack(db, context)
    row = RECMAReport(
        org_id=context.current_org_id,
        lead_id=payload.lead_id,
        deal_id=payload.deal_id,
        subject_property_json=payload.subject_property_json,
        pricing_json={},
        policy_warnings_json=[],
        risk_tier=RiskTier.TIER_1,
    )
    db.add(row)
    db.flush()
    write_event(db, context.current_org_id, "real_estate", "cma", "CMA_CREATED", {"report_id": str(row.id)})
    write_audit_log(db, context, "cma.created", "re_cma_report", str(row.id))
    db.commit()
    return RECMAReportResponse.model_validate(row, from_attributes=True)


@router.post("/cma/reports/{report_id}/comps/import")
def import_cma_comps(
    report_id: uuid.UUID,
    payload: RECMACompsImportRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> dict[str, int]:
    require_role(context, Role.AGENT)
    _ensure_pack(db, context)
    report = _cma_row(db, context, report_id)
    inserted = 0
    for comp in payload.comparables:
        db.add(
            RECMAComparable(
                org_id=context.current_org_id,
                cma_report_id=report.id,
                address=comp.address,
                status=comp.status,
                sold_price=comp.sold_price,
                list_price=comp.list_price,
                beds=comp.beds,
                baths=comp.baths,
                sqft=comp.sqft,
                year_built=comp.year_built,
                days_on_market=comp.days_on_market,
                distance_miles=comp.distance_miles,
                adjustments_json=comp.adjustments_json,
            )
        )
        inserted += 1
    db.flush()
    write_event(db, context.current_org_id, "real_estate", "cma", "CMA_COMPS_IMPORTED", {"report_id": str(report.id), "count": inserted})
    write_audit_log(db, context, "cma.comps_imported", "re_cma_report", str(report.id), {"count": inserted})
    db.commit()
    return {"inserted": inserted}


@router.post("/cma/reports/{report_id}/generate", response_model=RECMAReportResponse)
def generate_cma(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> RECMAReportResponse:
    require_role(context, Role.AGENT)
    _ensure_pack(db, context)
    report = _cma_row(db, context, report_id)
    policy = load_policy_engine(get_vertical_pack_slug(db, context.current_org_id))
    comps = list(
        db.scalars(
        org_scoped(select(RECMAComparable).where(RECMAComparable.cma_report_id == report.id, RECMAComparable.deleted_at.is_(None)), context.current_org_id, RECMAComparable)
        ).all()
    )
    pricing = calculate_cma_pricing(comps)
    narrative = render_cma_narrative(pricing, report.subject_property_json)
    disclaimers = get_required_disclaimers(policy.rules, "cma_narrative")
    narrative = append_disclaimers(narrative, disclaimers)
    validation = policy.validate_content(narrative, context={"surface": "cma"})
    report.pricing_json = {**pricing, "disclaimers": disclaimers}
    report.narrative_text = narrative
    report.policy_warnings_json = validation.reasons
    report.risk_tier = RiskTier(policy.risk_tier("cma_generate", context={"surface": "cma"}).value)
    write_event(db, context.current_org_id, "real_estate", "cma", "CMA_GENERATED", {"report_id": str(report.id)})
    write_audit_log(db, context, "cma.generated", "re_cma_report", str(report.id), {"warnings": validation.reasons}, risk_tier=report.risk_tier)
    db.commit()
    db.refresh(report)
    return RECMAReportResponse.model_validate(report, from_attributes=True)


@router.get("/cma/reports", response_model=list[RECMAReportResponse])
def list_cma_reports(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[RECMAReportResponse]:
    _ensure_pack(db, context)
    rows = db.scalars(
        org_scoped(
            select(RECMAReport).where(RECMAReport.deleted_at.is_(None)).order_by(desc(RECMAReport.created_at)).limit(limit).offset(offset),
            context.current_org_id,
            RECMAReport,
        )
    ).all()
    return [RECMAReportResponse.model_validate(row, from_attributes=True) for row in rows]


@router.get("/cma/reports/{report_id}", response_model=RECMAReportResponse)
def get_cma_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> RECMAReportResponse:
    _ensure_pack(db, context)
    return RECMAReportResponse.model_validate(_cma_row(db, context, report_id), from_attributes=True)


@router.get("/cma/reports/{report_id}/export")
def export_cma_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> Response:
    _ensure_pack(db, context)
    row = _cma_row(db, context, report_id)
    write_event(db, context.current_org_id, "real_estate", "cma", "CMA_EXPORTED", {"report_id": str(row.id)})
    write_audit_log(db, context, "cma.exported", "re_cma_report", str(row.id))
    db.commit()
    html = (
        "<html><head><title>CMA Report</title></head><body>"
        f"<h1>CMA Report</h1><p>ID: {row.id}</p>"
        f"<p>Suggested Price: {row.pricing_json.get('suggested_price', 0)}</p>"
        f"<pre>{(row.narrative_text or '').replace('<', '&lt;')}</pre></body></html>"
    )
    return Response(content=html, media_type="text/html")


@router.post("/listings/packages", response_model=REListingPackageResponse, status_code=status.HTTP_201_CREATED)
def create_listing_package(
    payload: REListingPackageCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> REListingPackageResponse:
    require_role(context, Role.AGENT)
    _ensure_pack(db, context)
    row = REListingPackage(
        org_id=context.current_org_id,
        deal_id=payload.deal_id,
        property_address_json=payload.property_address_json,
        status=REListingPackageStatus.DRAFT,
        description_variants_json={},
        key_features_json=payload.key_features_json,
        open_house_plan_json={},
        social_campaign_pack_json={},
        risk_tier=RiskTier.TIER_1,
        policy_warnings_json=[],
    )
    db.add(row)
    db.flush()
    write_event(db, context.current_org_id, "real_estate", "listing", "LISTING_PACKAGE_CREATED", {"listing_package_id": str(row.id)})
    write_audit_log(db, context, "listing_package.created", "re_listing_package", str(row.id))
    db.commit()
    return REListingPackageResponse.model_validate(row, from_attributes=True)


@router.get("/listings/packages", response_model=list[REListingPackageResponse])
def list_listing_packages(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[REListingPackageResponse]:
    _ensure_pack(db, context)
    rows = db.scalars(
        org_scoped(
            select(REListingPackage).where(REListingPackage.deleted_at.is_(None)).order_by(desc(REListingPackage.created_at)).limit(limit).offset(offset),
            context.current_org_id,
            REListingPackage,
        )
    ).all()
    return [REListingPackageResponse.model_validate(row, from_attributes=True) for row in rows]


@router.get("/listings/packages/{listing_id}", response_model=REListingPackageResponse)
def get_listing_package(
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> REListingPackageResponse:
    _ensure_pack(db, context)
    return REListingPackageResponse.model_validate(_list_row(db, context, listing_id), from_attributes=True)


@router.post("/listings/packages/{listing_id}/generate", response_model=REListingPackageResponse)
def generate_listing_package(
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> REListingPackageResponse:
    require_role(context, Role.AGENT)
    _ensure_pack(db, context)
    row = _list_row(db, context, listing_id)
    policy = load_policy_engine(get_vertical_pack_slug(db, context.current_org_id))
    address = str(row.property_address_json.get("street") or row.property_address_json.get("address") or "the property")
    short_template = load_pack_template("real-estate", "listing_description_short.txt")
    long_template = load_pack_template("real-estate", "listing_description_long.txt")
    open_house_template = load_pack_template("real-estate", "open_house_plan.txt")
    feature_1 = str((row.key_features_json or ["Feature 1"])[0])
    feature_2 = str((row.key_features_json or ["Feature 1", "Feature 2"])[1] if len(row.key_features_json) > 1 else "Feature 2")
    feature_3 = str((row.key_features_json or ["Feature 1", "Feature 2", "Feature 3"])[2] if len(row.key_features_json) > 2 else "Feature 3")
    feature_4 = str((row.key_features_json or ["Feature 1", "Feature 2", "Feature 3", "Feature 4"])[3] if len(row.key_features_json) > 3 else "Feature 4")
    short_text = (
        short_template.replace("{{property_address}}", address)
        .replace("{{beds}}", str(row.property_address_json.get("beds", "-")))
        .replace("{{baths}}", str(row.property_address_json.get("baths", "-")))
        .replace("{{feature_1}}", feature_1)
        .replace("{{feature_2}}", feature_2)
        .replace("{{feature_3}}", feature_3)
        .replace("{{cta_line}}", "Contact us to schedule your showing.")
    )
    long_text = (
        long_template.replace("{{property_address}}", address)
        .replace("{{beds}}", str(row.property_address_json.get("beds", "-")))
        .replace("{{baths}}", str(row.property_address_json.get("baths", "-")))
        .replace("{{sqft}}", str(row.property_address_json.get("sqft", "-")))
        .replace("{{feature_1}}", feature_1)
        .replace("{{feature_2}}", feature_2)
        .replace("{{feature_3}}", feature_3)
        .replace("{{feature_4}}", feature_4)
        .replace("{{location_benefit_1}}", str(row.property_address_json.get("city", "Prime local location")))
        .replace("{{location_benefit_2}}", "Convenient access to transit, shopping, and schools.")
        .replace("{{agent_name}}", "Your Agent")
    )
    disclaimers = get_required_disclaimers(policy.rules, "listing_description")
    short_text = append_disclaimers(short_text, disclaimers)
    medium_text = append_disclaimers(f"{short_text}\n\nAdditional highlights available upon request.", disclaimers)
    long_text = append_disclaimers(long_text, disclaimers)
    social_pack = build_listing_social_pack(address)
    payload = ListingPackageJSON(
        description_variants={"short": short_text, "medium": medium_text, "long": long_text},
        key_features=row.key_features_json,
        open_house_plan={"template": open_house_template, "property_address": address},
        social_campaign_pack=social_pack,
        disclaimers=disclaimers,
    )
    validation = policy.validate_content(f"{short_text}\n{medium_text}\n{long_text}", context={"surface": "listing"})
    row.description_variants_json = cast(dict[str, object], payload.description_variants)
    row.open_house_plan_json = payload.open_house_plan
    row.social_campaign_pack_json = payload.social_campaign_pack
    row.policy_warnings_json = validation.reasons
    row.risk_tier = RiskTier(policy.risk_tier("listing_package_generate", context={"surface": "listing"}).value)
    write_event(db, context.current_org_id, "real_estate", "listing", "LISTING_PACKAGE_GENERATED", {"listing_package_id": str(row.id)})
    write_audit_log(db, context, "listing_package.generated", "re_listing_package", str(row.id), {"warnings": validation.reasons}, risk_tier=row.risk_tier)
    db.commit()
    db.refresh(row)
    return REListingPackageResponse.model_validate(row, from_attributes=True)


@router.post("/listings/packages/{listing_id}/approve", response_model=REListingPackageResponse)
def approve_listing_package(
    listing_id: uuid.UUID,
    payload: ApprovalDecisionRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> REListingPackageResponse:
    require_role(context, Role.ADMIN)
    _ensure_pack(db, context)
    row = _list_row(db, context, listing_id)
    row.status = REListingPackageStatus.APPROVED if payload.status.value == "approved" else REListingPackageStatus.DRAFT
    write_event(db, context.current_org_id, "real_estate", "listing", "LISTING_PACKAGE_APPROVED", {"listing_package_id": str(row.id), "status": row.status.value})
    write_audit_log(db, context, "listing_package.approved", "re_listing_package", str(row.id), {"status": row.status.value})
    db.commit()
    return REListingPackageResponse.model_validate(row, from_attributes=True)


@router.post("/listings/packages/{listing_id}/push-to-content-queue")
def push_listing_to_content_queue(
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    require_role(context, Role.AGENT)
    _ensure_pack(db, context)
    row = _list_row(db, context, listing_id)
    if row.status != REListingPackageStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="listing package must be approved first")
    social_pack_data = cast(dict[str, Any], row.social_campaign_pack_json)
    posts = [CampaignPlanPost.model_validate(post) for post in social_pack_data.get("posts", [])]
    if not posts:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="listing package has no social campaign pack")
    pack_slug = get_vertical_pack_slug(db, context.current_org_id)
    week_start = datetime.now(tz=UTC).date()
    campaign = CampaignPlan(
        org_id=context.current_org_id,
        vertical_pack_slug=pack_slug,
        week_start_date=week_start,
        status=CampaignPlanStatus.APPROVED,
        created_by=context.current_user_id,
        approved_by=context.current_user_id,
        approved_at=utcnow(),
        plan_json=CampaignPlanJSON(
            week_start=week_start,
            objectives=["Promote listing visibility"],
            themes=["Listing launch"],
            channels=list(cast(list[str], social_pack_data.get("channels", []))),
            posts=posts,
        ).model_dump(mode="json"),
        metadata_json={"source": "listing_package", "listing_package_id": str(row.id)},
    )
    db.add(campaign)
    db.flush()
    policy = load_policy_engine(pack_slug)
    created = 0
    for post in posts:
        caption = f"{post.hook}\n\n" + "\n".join(f"- {point}" for point in post.value_points) + f"\n\n{post.cta}"
        item_json = ContentItemJSON(
            channel=post.channel,
            caption=caption,
            hashtags=[],
            cta=post.cta,
            link_url=None,
            media_prompt=None,
            disclaimers=[],
        )
        validation = policy.validate_content(item_json.caption, context={"channel": post.channel})
        risk = RiskTier(policy.risk_tier("publish_content", context={"channel": post.channel}).value)
        db.add(
            ContentItem(
                org_id=context.current_org_id,
                campaign_plan_id=campaign.id,
                channel=post.channel,
                account_ref=post.account_ref,
                status=ContentItemStatus.APPROVED if should_auto_approve(risk, 1) else ContentItemStatus.PENDING_APPROVAL,
                content_json=item_json.model_dump(mode="json"),
                text_rendered=item_json.caption,
                media_refs_json=[],
                link_url=None,
                tags_json=[],
                risk_tier=risk,
                policy_warnings_json=validation.reasons,
            )
        )
        created += 1
    write_event(db, context.current_org_id, "real_estate", "listing", "LISTING_CONTENT_PUSHED", {"listing_package_id": str(row.id), "campaign_id": str(campaign.id), "content_items_created": created})
    write_audit_log(db, context, "listing_package.pushed_to_content_queue", "re_listing_package", str(row.id), {"campaign_id": str(campaign.id), "content_items_created": created})
    db.commit()
    return {"campaign_plan_id": str(campaign.id), "content_items_created": created}
