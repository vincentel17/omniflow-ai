from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Role, RiskTier
from ..schemas import OpsSettingsPatchRequest, OpsSettingsResponse
from ..services.audit import write_audit_log
from ..services.events import write_event
from ..services.org_settings import get_org_settings_payload, update_org_settings_payload
from ..tenancy import RequestContext, get_request_context, require_role

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/settings", response_model=OpsSettingsResponse)
def get_ops_settings(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> OpsSettingsResponse:
    require_role(context, Role.ADMIN)
    payload = get_org_settings_payload(db=db, org_id=context.current_org_id)
    db.commit()
    return OpsSettingsResponse.model_validate(payload)


@router.patch("/settings", response_model=OpsSettingsResponse)
def patch_ops_settings(
    payload: OpsSettingsPatchRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> OpsSettingsResponse:
    require_role(context, Role.ADMIN)
    updated = update_org_settings_payload(
        db=db,
        org_id=context.current_org_id,
        patch=payload.model_dump(exclude_none=True),
    )
    write_audit_log(
        db=db,
        context=context,
        action="ops.settings_updated",
        target_type="org_settings",
        target_id=str(context.current_org_id),
        metadata_json={"updated_keys": sorted(payload.model_dump(exclude_none=True).keys())},
        risk_tier=RiskTier.TIER_2,
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="ops",
        channel="settings",
        event_type="OPS_SETTINGS_UPDATED",
        payload_json={"updated_keys": sorted(payload.model_dump(exclude_none=True).keys())},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    return OpsSettingsResponse.model_validate(updated)
