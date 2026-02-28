from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Role, VerticalPack
from ..schemas import VerticalPackManifestResponse, VerticalPackResponse, VerticalPackSelectRequest
from ..services.audit import write_audit_log
from ..services.billing import is_vertical_allowed
from ..services.events import write_event
from ..services.verticals import PackInstallService, get_pack_manifest, list_available_pack_manifests
from ..services.workflows import seed_pack_workflows
from ..tenancy import RequestContext, get_request_context, org_scoped, require_role

router = APIRouter(prefix="/verticals", tags=["verticals"])


def _manifest_index() -> dict[str, dict[str, object]]:
    manifests = list_available_pack_manifests()
    return {str(item["slug"]): item for item in manifests}


@router.get("/packs")
def get_packs() -> dict[str, list[str]]:
    # Legacy endpoint kept for existing clients.
    return {"packs": sorted(_manifest_index().keys())}


@router.get("/available", response_model=list[VerticalPackManifestResponse])
def get_available_packs() -> list[VerticalPackManifestResponse]:
    manifests = list_available_pack_manifests()
    return [
        VerticalPackManifestResponse(
            slug=str(item["slug"]),
            name=str(item["name"]),
            version=str(item["version"]),
            compatible_core_version=str(item["compatible_core_version"]),
            features=dict(item.get("features") or {}),
            checksum=str(item["checksum"]),
            status=str(item.get("status") or "active"),
        )
        for item in manifests
    ]


@router.get("/{slug}/manifest", response_model=VerticalPackManifestResponse)
def get_pack_manifest_detail(slug: str) -> VerticalPackManifestResponse:
    manifest = get_pack_manifest(slug)
    row = next((item for item in list_available_pack_manifests() if item["slug"] == slug), None)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vertical pack not found")
    return VerticalPackManifestResponse(
        slug=slug,
        name=str(manifest.get("name", slug)),
        version=str(manifest.get("version", "")),
        compatible_core_version=str(manifest.get("compatible_core_version", "")),
        features=dict(manifest.get("features") or {}),
        checksum=str(row["checksum"]),
        status="active",
    )


@router.post("/select", response_model=VerticalPackResponse)
def select_pack(
    payload: VerticalPackSelectRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> VerticalPackResponse:
    require_role(context, Role.ADMIN)
    manifests = _manifest_index()
    details = manifests.get(payload.pack_slug)
    if details is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vertical pack not found")

    if not is_vertical_allowed(db=db, org_id=context.current_org_id, pack_slug=payload.pack_slug):
        metadata = {"pack_slug": payload.pack_slug, "reason": "entitlement_not_allowed"}
        write_audit_log(
            db=db,
            context=context,
            action="vertical_pack.activation_blocked",
            target_type="vertical_pack",
            target_id=payload.pack_slug,
            metadata_json=metadata,
        )
        write_event(
            db=db,
            org_id=context.current_org_id,
            source="verticals",
            channel="verticals",
            event_type="PACK_ACTIVATION_BLOCKED",
            payload_json=metadata,
            actor_id=str(context.current_user_id),
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="pack not allowed for current plan")

    existing = db.scalar(
        org_scoped(select(VerticalPack).where(VerticalPack.deleted_at.is_(None)), context.current_org_id, VerticalPack)
    )
    if existing is None:
        existing = VerticalPack(org_id=context.current_org_id, pack_slug=payload.pack_slug)
        db.add(existing)
    else:
        existing.pack_slug = payload.pack_slug

    install_service = PackInstallService(db=db)
    install_service.install_pack(payload.pack_slug, str(details["version"]))

    seeded_workflows = seed_pack_workflows(db=db, org_id=context.current_org_id, pack_slug=payload.pack_slug)

    write_audit_log(
        db=db,
        context=context,
        action="vertical_pack.selected",
        target_type="vertical_pack",
        target_id=payload.pack_slug,
        metadata_json={"seeded_workflows": seeded_workflows, "pack_version": details["version"]},
    )
    write_event(
        db=db,
        org_id=context.current_org_id,
        source="verticals",
        channel="verticals",
        event_type="VERTICAL_PACK_SELECTED",
        payload_json={"pack_slug": payload.pack_slug, "seeded_workflows": seeded_workflows, "pack_version": details["version"]},
        actor_id=str(context.current_user_id),
    )
    db.commit()
    db.refresh(existing)
    return VerticalPackResponse(
        id=existing.id,
        org_id=existing.org_id,
        pack_slug=existing.pack_slug,
        created_at=existing.created_at,
    )


@router.get("/current", response_model=VerticalPackResponse)
def get_current_pack(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> VerticalPackResponse:
    row = db.scalar(
        org_scoped(select(VerticalPack).where(VerticalPack.deleted_at.is_(None)), context.current_org_id, VerticalPack)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="vertical pack not selected")
    return VerticalPackResponse(id=row.id, org_id=row.org_id, pack_slug=row.pack_slug, created_at=row.created_at)
