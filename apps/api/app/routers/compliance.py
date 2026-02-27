from __future__ import annotations

import hashlib
import json
import uuid
from typing import cast
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    Approval,
    ApprovalEntityType,
    AuditLog,
    DataRetentionPolicy,
    DSARRequest,
    DSARRequestStatus,
    DSARRequestType,
    Event,
    InboxMessage,
    Lead,
    OrgSettings,
    PermissionAuditReport,
    REDeal,
    RECMAReport,
    ReputationReview,
    RiskTier,
    Role,
    WorkflowActionRun,
    WorkflowRun,
)
from ..schemas import (
    DSARRequestCreateRequest,
    DSARRequestProcessResponse,
    DSARRequestResponse,
    DataRetentionPolicyPatchRequest,
    DataRetentionPolicyResponse,
    EvidenceBundleResponse,
    PermissionAuditReportResponse,
    RBACMatrixResponse,
)
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..services.org_settings import get_org_settings_payload, update_org_settings_payload
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(prefix="/compliance", tags=["compliance"])

DEFAULT_RETENTION_POLICIES: dict[str, tuple[int, int]] = {
    "inbox_message": (365, 395),
    "audit": (365, 395),
    "event": (365, 395),
    "lead": (36500, 36530),
    "review": (730, 760),
}

RBAC_MATRIX: dict[str, list[str]] = {
    "owner": ["*"],
    "admin": [
        "ops.settings.patch",
        "workflows.manage",
        "ads.manage",
        "compliance.manage",
        "approvals.decide",
    ],
    "agent": ["inbox.reply", "lead.update", "task.manage", "content.draft"],
    "member": ["dashboard.read", "analytics.read"],
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_subject(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum() or ch in {"@", "+"})


def _subject_hash(value: str) -> str:
    return hashlib.sha256(_normalize_subject(value).encode("utf-8")).hexdigest()


def _mask_text(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= 4:
        return "***"
    return value[:2] + "***" + value[-2:]


def _serialize_retention(row: DataRetentionPolicy) -> dict[str, object]:
    return {
        "id": row.id,
        "org_id": row.org_id,
        "entity_type": row.entity_type,
        "retention_days": row.retention_days,
        "hard_delete_after_days": row.hard_delete_after_days,
        "created_at": row.created_at,
    }


def _serialize_dsar(row: DSARRequest) -> dict[str, object]:
    return {
        "id": row.id,
        "org_id": row.org_id,
        "request_type": row.request_type.value,
        "subject_identifier": row.subject_identifier,
        "status": row.status.value,
        "requested_at": row.requested_at,
        "completed_at": row.completed_at,
        "export_ref": row.export_ref,
        "created_at": row.created_at,
    }


def _ensure_default_retention(db: Session, org_id: uuid.UUID) -> list[DataRetentionPolicy]:
    rows: list[DataRetentionPolicy] = list(db.scalars(
        org_scoped(
            select(DataRetentionPolicy).where(DataRetentionPolicy.deleted_at.is_(None)),
            org_id,
            DataRetentionPolicy,
        
        )
    ).all())
    existing = {row.entity_type for row in rows}
    created = False
    for entity_type, (retention_days, hard_delete_after_days) in DEFAULT_RETENTION_POLICIES.items():
        if entity_type in existing:
            continue
        db.add(
            DataRetentionPolicy(
                org_id=org_id,
                entity_type=entity_type,
                retention_days=retention_days,
                hard_delete_after_days=hard_delete_after_days,
            )
        )
        created = True
    if created:
        db.flush()
        rows = list(db.scalars(
        org_scoped(
                select(DataRetentionPolicy).where(DataRetentionPolicy.deleted_at.is_(None)),
                org_id,
                DataRetentionPolicy,
            
        )
    ).all())
    return rows


def _collect_dsar_records(db: Session, org_id: uuid.UUID, subject_identifier: str) -> dict[str, object]:
    token = _subject_hash(subject_identifier)

    leads = db.scalars(
        org_scoped(select(Lead).where(Lead.deleted_at.is_(None)), org_id, Lead)
    ).all()
    matched_leads = [
        {
            "id": str(lead.id),
            "name": _mask_text(lead.name),
            "email": _mask_text(lead.email),
            "phone": _mask_text(lead.phone),
            "status": lead.status.value,
        }
        for lead in leads
        if (lead.email and _subject_hash(lead.email) == token) or (lead.phone and _subject_hash(lead.phone) == token)
    ]
    lead_ids = {item["id"] for item in matched_leads}

    inbox_messages = db.scalars(
        org_scoped(select(InboxMessage).where(InboxMessage.deleted_at.is_(None)), org_id, InboxMessage
        )
    ).all()
    matched_messages = [
        {
            "id": str(message.id),
            "thread_id": str(message.thread_id),
            "direction": message.direction.value,
            "sender_display": _mask_text(message.sender_display),
            "body_text": _mask_text(message.body_text),
        }
        for message in inbox_messages
        if (message.sender_display and _subject_hash(message.sender_display) == token)
        or (message.sender_ref and _subject_hash(message.sender_ref) == token)
    ]

    deals = db.scalars(org_scoped(select(REDeal).where(REDeal.deleted_at.is_(None)), org_id, REDeal)).all()
    matched_deals = [
        {
            "id": str(deal.id),
            "deal_type": deal.deal_type.value,
            "status": deal.status.value,
            "primary_contact_name": _mask_text(deal.primary_contact_name),
            "primary_contact_email": _mask_text(deal.primary_contact_email),
            "primary_contact_phone": _mask_text(deal.primary_contact_phone),
        }
        for deal in deals
        if (deal.primary_contact_email and _subject_hash(deal.primary_contact_email) == token)
        or (deal.primary_contact_phone and _subject_hash(deal.primary_contact_phone) == token)
        or (deal.lead_id and str(deal.lead_id) in lead_ids)
    ]

    cma_rows = db.scalars(org_scoped(select(RECMAReport).where(RECMAReport.deleted_at.is_(None)), org_id, RECMAReport)).all()
    matched_cma = [
        {
            "id": str(cma.id),
            "lead_id": str(cma.lead_id) if cma.lead_id else None,
            "deal_id": str(cma.deal_id) if cma.deal_id else None,
            "sensitive_level": cma.sensitive_level,
        }
        for cma in cma_rows
        if (cma.lead_id and str(cma.lead_id) in lead_ids)
    ]

    reviews = db.scalars(
        org_scoped(select(ReputationReview).where(ReputationReview.deleted_at.is_(None)), org_id, ReputationReview
        )
    ).all()
    matched_reviews = [
        {
            "id": str(review.id),
            "source": review.source.value,
            "rating": review.rating,
            "reviewer_name_masked": review.reviewer_name_masked,
        }
        for review in reviews
        if review.reviewer_name_masked and _subject_hash(review.reviewer_name_masked) == token
    ]

    audit_rows: list[AuditLog] = list(db.scalars(
        org_scoped(
            select(AuditLog).where(AuditLog.deleted_at.is_(None)).order_by(desc(AuditLog.created_at)).limit(100),
            org_id,
            AuditLog,
        
        )
    ).all())
    audit_subset = [
        {
            "id": str(row.id),
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "created_at": row.created_at.isoformat(),
        }
        for row in audit_rows
        if row.target_id in lead_ids
    ]

    return {
        "subject_hash": token,
        "leads": matched_leads,
        "inbox_messages": matched_messages,
        "deals": matched_deals,
        "cma_reports": matched_cma,
        "reviews": matched_reviews,
        "audit_entries": audit_subset,
    }


@router.get("/retention", response_model=list[DataRetentionPolicyResponse])
def list_retention_policies(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[DataRetentionPolicyResponse]:
    require_role(context, Role.ADMIN)
    rows = _ensure_default_retention(db=db, org_id=context.current_org_id)
    db.commit()
    return [DataRetentionPolicyResponse.model_validate(_serialize_retention(row)) for row in rows]


@router.patch("/retention", response_model=list[DataRetentionPolicyResponse])
def patch_retention_policies(
    payload: DataRetentionPolicyPatchRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[DataRetentionPolicyResponse]:
    require_role(context, Role.ADMIN)
    rows = _ensure_default_retention(db=db, org_id=context.current_org_id)
    by_entity = {row.entity_type: row for row in rows}
    for item in payload.policies:
        row = by_entity.get(item.entity_type)
        if row is None:
            row = DataRetentionPolicy(
                org_id=context.current_org_id,
                entity_type=item.entity_type,
                retention_days=item.retention_days,
                hard_delete_after_days=item.hard_delete_after_days,
            )
            db.add(row)
            by_entity[item.entity_type] = row
        else:
            row.retention_days = item.retention_days
            row.hard_delete_after_days = item.hard_delete_after_days
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="compliance.retention_updated",
        target_type="retention_policy",
        target_id=str(context.current_org_id),
        risk_tier=RiskTier.TIER_2,
        metadata_json={"entities": [item.entity_type for item in payload.policies]},
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="compliance",
        channel="governance",
        event_type="DATA_RETENTION_POLICY_UPDATED",
        payload_json={"count": len(payload.policies)},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    rows = list(db.scalars(
        org_scoped(select(DataRetentionPolicy).where(DataRetentionPolicy.deleted_at.is_(None)), context.current_org_id, DataRetentionPolicy
        )
    ).all())
    return [DataRetentionPolicyResponse.model_validate(_serialize_retention(row)) for row in rows]


@router.post("/dsar", response_model=DSARRequestResponse, status_code=status.HTTP_201_CREATED)
def create_dsar_request(
    payload: DSARRequestCreateRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> DSARRequestResponse:
    require_role(context, Role.ADMIN)
    req_type = DSARRequestType(payload.request_type)
    row = DSARRequest(
        org_id=context.current_org_id,
        request_type=req_type,
        subject_identifier=payload.subject_identifier,
        status=DSARRequestStatus.REQUESTED,
    )
    db.add(row)
    db.flush()
    write_audit_log(
        db=db,
        context=context,
        action="compliance.dsar_requested",
        target_type="dsar_request",
        target_id=str(row.id),
        risk_tier=RiskTier.TIER_3,
        metadata_json={"request_type": row.request_type.value},
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="compliance",
        channel="governance",
        event_type="DSAR_REQUESTED",
        payload_json={"dsar_request_id": str(row.id), "request_type": row.request_type.value},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(row)
    return DSARRequestResponse.model_validate(_serialize_dsar(row))


@router.get("/dsar", response_model=list[DSARRequestResponse])
def list_dsar_requests(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[DSARRequestResponse]:
    require_role(context, Role.ADMIN)
    rows: list[DSARRequest] = list(db.scalars(
        org_scoped(
            select(DSARRequest)
            .where(DSARRequest.deleted_at.is_(None))
            .order_by(desc(DSARRequest.created_at))
            .limit(limit)
            .offset(offset),
            context.current_org_id,
            DSARRequest,
        
        )
    ).all())
    return [DSARRequestResponse.model_validate(_serialize_dsar(row)) for row in rows]


@router.post("/dsar/{request_id}/process", response_model=DSARRequestProcessResponse)
def process_dsar_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> DSARRequestProcessResponse:
    require_role(context, Role.ADMIN)
    row = db.scalar(
        org_scoped(
            select(DSARRequest).where(DSARRequest.id == request_id, DSARRequest.deleted_at.is_(None)),
            context.current_org_id,
            DSARRequest,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="dsar request not found")

    row.status = DSARRequestStatus.IN_PROGRESS
    bundle = _collect_dsar_records(db=db, org_id=context.current_org_id, subject_identifier=row.subject_identifier)

    if row.request_type in {DSARRequestType.ACCESS, DSARRequestType.EXPORT}:
        row.export_ref = json.dumps(bundle, separators=(",", ":"))
    elif row.request_type == DSARRequestType.DELETE:
        token = _subject_hash(row.subject_identifier)
        lead_rows = db.scalars(org_scoped(select(Lead).where(Lead.deleted_at.is_(None)), context.current_org_id, Lead)).all()
        for lead in lead_rows:
            if (lead.email and _subject_hash(lead.email) == token) or (lead.phone and _subject_hash(lead.phone) == token):
                lead.deleted_at = _now()
                lead.deletion_reason = "dsar_delete"
                lead.name = None
                lead.email = None
                lead.phone = None
        msg_rows = db.scalars(org_scoped(select(InboxMessage).where(InboxMessage.deleted_at.is_(None)), context.current_org_id, InboxMessage)).all()
        for message in msg_rows:
            if (message.sender_display and _subject_hash(message.sender_display) == token) or (message.sender_ref and _subject_hash(message.sender_ref) == token):
                message.deleted_at = _now()
                message.deletion_reason = "dsar_delete"
                message.body_text = "[redacted]"

    row.status = DSARRequestStatus.COMPLETED
    row.completed_at = _now()

    write_event(
        db=db,
        org_id=context.current_org_id,
        source="compliance",
        channel="governance",
        event_type="DSAR_PROCESSED",
        payload_json={"dsar_request_id": str(row.id), "request_type": row.request_type.value},
        actor_id=str(context.current_user_id),
    )
    write_audit_log(
        db=db,
        context=context,
        action="compliance.dsar_processed",
        target_type="dsar_request",
        target_id=str(row.id),
        risk_tier=RiskTier.TIER_3,
        metadata_json={"request_type": row.request_type.value, "status": row.status.value},
    )
    db.commit()
    return DSARRequestProcessResponse(id=row.id, status=row.status.value, export_ref=row.export_ref, completed_at=row.completed_at)


@router.get("/rbac-matrix", response_model=RBACMatrixResponse)
def get_rbac_matrix(
    context: RequestContext = Depends(get_request_context),
) -> RBACMatrixResponse:
    require_role(context, Role.ADMIN)
    return RBACMatrixResponse(roles=RBAC_MATRIX)


@router.post("/rbac-audit", response_model=PermissionAuditReportResponse)
def run_rbac_audit(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> PermissionAuditReportResponse:
    require_role(context, Role.ADMIN)
    org_settings_row = db.scalar(
        org_scoped(
            select(OrgSettings).where(OrgSettings.deleted_at.is_(None)),
            context.current_org_id,
            OrgSettings,
        )
    )
    raw_settings = dict(org_settings_row.settings_json) if org_settings_row and isinstance(org_settings_row.settings_json, dict) else {}
    settings_payload = get_org_settings_payload(db=db, org_id=context.current_org_id)
    findings: list[dict[str, object]] = []
    recommendations: list[str] = []

    if settings_payload.get("enable_auto_posting") is True and settings_payload.get("max_auto_approve_tier", 0) >= 3:
        findings.append({"risk": "high", "code": "AUTO_POST_HIGH_TIER", "message": "Auto posting enabled with high auto-approve tier"})
        recommendations.append("Lower max_auto_approve_tier or disable auto posting")

    ads_caps = settings_payload.get("ads_budget_caps_json") if isinstance(settings_payload.get("ads_budget_caps_json"), dict) else {}
    raw_ads_caps = raw_settings.get("ads_budget_caps_json") if isinstance(raw_settings.get("ads_budget_caps_json"), dict) else None
    raw_daily_cap = float(raw_ads_caps.get("org_daily_cap_usd", 0)) if isinstance(raw_ads_caps, dict) else 0.0
    if settings_payload.get("enable_ads_live") is True and (
        not ads_caps
        or float(ads_caps.get("org_daily_cap_usd", 0)) <= 0
        or raw_daily_cap <= 0
    ):
        findings.append({"risk": "high", "code": "ADS_LIVE_NO_CAPS", "message": "Ads live mode enabled without valid daily caps"})
        recommendations.append("Configure ads_budget_caps_json with non-zero caps")

    if settings_payload.get("default_autonomy_max_tier", 0) >= 3:
        findings.append({"risk": "medium", "code": "WORKFLOW_HIGH_AUTONOMY", "message": "Workflow autonomy tier allows high-risk execution"})
        recommendations.append("Reduce default_autonomy_max_tier to <=1")

    report = PermissionAuditReport(
        org_id=context.current_org_id,
        findings_json=findings,
        recommendations_json=recommendations,
    )
    db.add(report)
    db.flush()

    write_event(
        db=db,
        org_id=context.current_org_id,
        source="compliance",
        channel="governance",
        event_type="RBAC_AUDIT_COMPLETED",
        payload_json={"report_id": str(report.id), "finding_count": len(findings)},
        actor_id=str(context.current_user_id),
    )
    write_audit_log(
        db=db,
        context=context,
        action="compliance.rbac_audit_completed",
        target_type="permission_audit_report",
        target_id=str(report.id),
        risk_tier=RiskTier.TIER_2,
        metadata_json={"finding_count": len(findings)},
    )
    db.commit()
    return PermissionAuditReportResponse(
        id=report.id,
        org_id=report.org_id,
        findings_json=report.findings_json,
        recommendations_json=report.recommendations_json,
        created_at=report.created_at,
    )


@router.get("/evidence-bundle", response_model=EvidenceBundleResponse)
def get_evidence_bundle(
    from_date: date,
    to_date: date,
    include_pii: bool = False,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> EvidenceBundleResponse:
    require_role(context, Role.ADMIN)
    start = datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(to_date, datetime.max.time(), tzinfo=timezone.utc)

    audits = db.scalars(
        org_scoped(
            select(AuditLog).where(AuditLog.deleted_at.is_(None), AuditLog.created_at >= start, AuditLog.created_at <= end),
            context.current_org_id,
            AuditLog,
        
        )
    ).all()
    workflow_runs = db.scalars(
        org_scoped(
            select(WorkflowRun).where(WorkflowRun.deleted_at.is_(None), WorkflowRun.created_at >= start, WorkflowRun.created_at <= end),
            context.current_org_id,
            WorkflowRun,
        
        )
    ).all()
    workflow_actions = db.scalars(
        org_scoped(
            select(WorkflowActionRun).where(WorkflowActionRun.deleted_at.is_(None), WorkflowActionRun.created_at >= start, WorkflowActionRun.created_at <= end),
            context.current_org_id,
            WorkflowActionRun,
        
        )
    ).all()
    ads_approvals = db.scalars(
        org_scoped(
            select(Approval).where(
                Approval.deleted_at.is_(None),
                Approval.created_at >= start,
                Approval.created_at <= end,
            ),
            context.current_org_id,
            Approval,
        
        )
    ).all()
    ads_approval_entity_types = {
        ApprovalEntityType.AD_CAMPAIGN.value,
        ApprovalEntityType.AD_CREATIVE.value,
        ApprovalEntityType.AD_SPEND_CHANGE.value,
        ApprovalEntityType.AD_EXPERIMENT.value,
    }
    ads_approvals = [row for row in ads_approvals if row.entity_type.value in ads_approval_entity_types]
    retention_events = db.scalars(
        org_scoped(
            select(Event).where(
                Event.deleted_at.is_(None),
                Event.created_at >= start,
                Event.created_at <= end,
                Event.type.in_(["DATA_RETENTION_APPLIED", "DSAR_PROCESSED", "RBAC_AUDIT_COMPLETED"]),
            ),
            context.current_org_id,
            Event,
        
        )
    ).all()
    permission_reports = db.scalars(
        org_scoped(
            select(PermissionAuditReport).where(
                PermissionAuditReport.deleted_at.is_(None),
                PermissionAuditReport.created_at >= start,
                PermissionAuditReport.created_at <= end,
            ),
            context.current_org_id,
            PermissionAuditReport,
        
        )
    ).all()
    dsar_rows: list[DSARRequest] = list(db.scalars(
        org_scoped(
            select(DSARRequest).where(DSARRequest.deleted_at.is_(None), DSARRequest.created_at >= start, DSARRequest.created_at <= end),
            context.current_org_id,
            DSARRequest,
        
        )
    ).all())

    bundle = {
        "audit_logs": [
            {
                "id": str(row.id),
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "risk_tier": row.risk_tier.value,
                "created_at": row.created_at.isoformat(),
                "metadata_json": row.metadata_json if include_pii else {},
            }
            for row in audits
        ],
        "workflow_runs": [{"id": str(row.id), "status": row.status.value, "created_at": row.created_at.isoformat()} for row in workflow_runs],
        "workflow_action_runs": [{"id": str(row.id), "action_type": row.action_type, "status": row.status.value, "created_at": row.created_at.isoformat()} for row in workflow_actions],
        "ads_approvals": [{"id": str(row.id), "entity_type": row.entity_type.value, "status": row.status.value, "created_at": row.created_at.isoformat()} for row in ads_approvals],
        "retention_events": [{"id": str(row.id), "type": row.type, "created_at": row.created_at.isoformat()} for row in retention_events],
        "rbac_audit_reports": [{"id": str(row.id), "findings": row.findings_json, "recommendations": row.recommendations_json, "created_at": row.created_at.isoformat()} for row in permission_reports],
        "dsar_logs": [{"id": str(row.id), "request_type": row.request_type.value, "status": row.status.value, "created_at": row.created_at.isoformat()} for row in dsar_rows],
    }

    write_event(
        db=db,
        org_id=context.current_org_id,
        source="compliance",
        channel="governance",
        event_type="EVIDENCE_EXPORT_GENERATED",
        payload_json={"from": from_date.isoformat(), "to": to_date.isoformat(), "include_pii": include_pii},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    bundle_payload: dict[str, object] = cast(dict[str, object], bundle)
    return EvidenceBundleResponse(from_date=from_date, to_date=to_date, include_pii=include_pii, bundle_json=bundle_payload)


@router.get("/mode", response_model=dict[str, str])
def get_compliance_mode(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> dict[str, str]:
    require_role(context, Role.ADMIN)
    settings_payload = get_org_settings_payload(db=db, org_id=context.current_org_id)
    mode = str(settings_payload.get("compliance_mode", "none"))
    return {"compliance_mode": mode}


@router.patch("/mode", response_model=dict[str, str])
def patch_compliance_mode(
    compliance_mode: str,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> dict[str, str]:
    require_role(context, Role.ADMIN)
    if compliance_mode not in {"none", "real_estate", "home_care"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid compliance_mode")
    updated = update_org_settings_payload(
        db=db,
        org_id=context.current_org_id,
        patch={"compliance_mode": compliance_mode},
    )
    write_audit_log(
        db=db,
        context=context,
        action="compliance.mode_updated",
        target_type="org_settings",
        target_id=str(context.current_org_id),
        risk_tier=RiskTier.TIER_2,
        metadata_json={"compliance_mode": compliance_mode},
    )
    db.commit()
    return {"compliance_mode": str(updated.get("compliance_mode", "none"))}
