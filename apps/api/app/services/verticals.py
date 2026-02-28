from __future__ import annotations

import hashlib
import json
import os

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import VerticalPackRegistry

CORE_VERSION = os.getenv("OMNIFLOW_CORE_VERSION", "0.1.0")
REQUIRED_PACK_FILES_V2 = (
    "manifest.json",
    "pipelines.json",
    "scoring.json",
    "seo_archetypes.json",
    "workflows.runtime.json",
    "policy.rules.yaml",
    "optimization_config.json",
    "entitlement_overrides.json",
)
LEGACY_WORKFLOW_FILE = "workflows.json"


def _verticals_root() -> Path:
    return Path(__file__).resolve().parents[4] / "packages" / "verticals"


def _parse_version(value: str) -> tuple[int, int, int]:
    parts = value.strip().split(".")
    padded = (parts + ["0", "0", "0"])[:3]
    return int(padded[0]), int(padded[1]), int(padded[2])


def _supports_core_version(constraint: str, core_version: str) -> bool:
    raw = constraint.strip()
    if not raw:
        return False
    if raw.startswith(">="):
        return _parse_version(core_version) >= _parse_version(raw[2:])
    return _parse_version(core_version) == _parse_version(raw)


def _validate_pack_manifest(pack_slug: str, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if str(payload.get("slug", "")).strip() != pack_slug:
        errors.append("manifest.slug must match folder name")
    if not str(payload.get("name", "")).strip():
        errors.append("manifest.name is required")
    if not str(payload.get("version", "")).strip():
        errors.append("manifest.version is required")
    compatibility = str(payload.get("compatible_core_version", "")).strip()
    if not compatibility:
        errors.append("manifest.compatible_core_version is required")
    elif not _supports_core_version(compatibility, CORE_VERSION):
        errors.append(f"manifest.compatible_core_version '{compatibility}' does not allow core '{CORE_VERSION}'")
    features = payload.get("features")
    if not isinstance(features, dict):
        errors.append("manifest.features must be an object")
    else:
        required_feature_keys = ("pipelines", "seo", "compliance", "ads", "workflows", "optimization")
        for key in required_feature_keys:
            if not isinstance(features.get(key), bool):
                errors.append(f"manifest.features.{key} must be boolean")
    return errors


def _pack_checksum(pack_dir: Path) -> str:
    digest = hashlib.sha256()
    for filename in REQUIRED_PACK_FILES_V2:
        target = pack_dir / filename
        if target.exists():
            digest.update(target.read_bytes())
    return digest.hexdigest()


def _load_manifest(pack_dir: Path) -> dict[str, Any]:
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing required file manifest.json for pack '{pack_dir.name}'")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def validate_pack(pack_slug: str) -> tuple[bool, list[str]]:
    pack_dir = _verticals_root() / pack_slug
    if not pack_dir.exists() or not pack_dir.is_dir():
        return False, [f"Unknown vertical pack: {pack_slug}"]
    errors: list[str] = []
    for required_file in REQUIRED_PACK_FILES_V2:
        if not (pack_dir / required_file).exists():
            errors.append(f"missing required file: {required_file}")
    if errors:
        return False, errors
    try:
        manifest = _load_manifest(pack_dir)
    except Exception as exc:
        return False, [f"invalid manifest: {exc}"]
    errors.extend(_validate_pack_manifest(pack_slug, manifest))
    return len(errors) == 0, errors


def list_available_packs() -> list[str]:
    packs: list[str] = []
    for entry in _verticals_root().iterdir():
        if not entry.is_dir():
            continue
        valid, _ = validate_pack(entry.name)
        if valid:
            packs.append(entry.name)
    return sorted(packs)


def list_available_pack_manifests() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for slug in list_available_packs():
        pack_dir = _verticals_root() / slug
        manifest = _load_manifest(pack_dir)
        rows.append(
            {
                "slug": slug,
                "name": str(manifest.get("name", slug)),
                "version": str(manifest.get("version", "")),
                "compatible_core_version": str(manifest.get("compatible_core_version", "")),
                "features": manifest.get("features", {}),
                "checksum": _pack_checksum(pack_dir),
                "status": "active",
                "manifest": manifest,
            }
        )
    return rows


def get_pack_manifest(pack_slug: str) -> dict[str, Any]:
    valid, errors = validate_pack(pack_slug)
    if not valid:
        raise FileNotFoundError(f"Invalid vertical pack '{pack_slug}': {', '.join(errors)}")
    pack_dir = _verticals_root() / pack_slug
    return _load_manifest(pack_dir)


def load_pack_file(pack_slug: str, filename: str) -> dict[str, Any]:
    pack_dir = _verticals_root() / pack_slug
    if not pack_dir.exists():
        raise FileNotFoundError(f"Unknown vertical pack: {pack_slug}")
    target = pack_dir / filename
    if not target.exists() and filename == "workflows.runtime.json":
        legacy = pack_dir / LEGACY_WORKFLOW_FILE
        if legacy.exists():
            target = legacy
    if not target.exists():
        raise FileNotFoundError(f"Pack file not found: {filename}")
    if filename.endswith(".yaml"):
        return yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    return json.loads(target.read_text(encoding="utf-8"))


def load_pack_template(pack_slug: str, template_name: str) -> str:
    pack_dir = _verticals_root() / pack_slug
    if not pack_dir.exists():
        raise FileNotFoundError(f"Unknown vertical pack: {pack_slug}")
    target = pack_dir / "templates" / template_name
    if not target.exists():
        raise FileNotFoundError(f"Template not found: {template_name}")
    return target.read_text(encoding="utf-8")


def pack_feature_flags(pack_slug: str) -> dict[str, bool]:
    manifest = get_pack_manifest(pack_slug)
    raw = manifest.get("features") if isinstance(manifest, dict) else {}
    if not isinstance(raw, dict):
        return {}
    return {str(key): bool(value) for key, value in raw.items()}


class PackInstallService:
    def __init__(self, db: Session):
        self.db = db

    def verify_checksum(self, slug: str, expected_checksum: str | None = None) -> str:
        pack_dir = _verticals_root() / slug
        if not pack_dir.exists():
            raise FileNotFoundError(f"Unknown vertical pack: {slug}")
        actual = _pack_checksum(pack_dir)
        if expected_checksum and actual != expected_checksum:
            raise ValueError("pack checksum mismatch")
        return actual

    def validate_schema(self, slug: str) -> tuple[bool, list[str]]:
        return validate_pack(slug)

    def install_pack(self, slug: str, version: str | None = None) -> VerticalPackRegistry:
        valid, errors = self.validate_schema(slug)
        if not valid:
            raise ValueError(f"invalid pack '{slug}': {', '.join(errors)}")
        manifest = get_pack_manifest(slug)
        resolved_version = version or str(manifest.get("version", "")).strip()
        if not resolved_version:
            raise ValueError("pack version is required")
        checksum = self.verify_checksum(slug)
        row = self.db.scalar(
            select(VerticalPackRegistry).where(
                VerticalPackRegistry.slug == slug,
                VerticalPackRegistry.version == resolved_version,
                VerticalPackRegistry.deleted_at.is_(None),
            )
        )
        if row is None:
            row = VerticalPackRegistry(
                slug=slug,
                version=resolved_version,
                status="active",
                checksum=checksum,
            )
            self.db.add(row)
        else:
            row.status = "active"
            row.checksum = checksum
        self.db.flush()
        return row

    def deactivate_pack(self, slug: str, version: str | None = None) -> int:
        rows = self.db.scalars(
            select(VerticalPackRegistry).where(
                VerticalPackRegistry.slug == slug,
                VerticalPackRegistry.deleted_at.is_(None),
            )
        ).all()
        updated = 0
        for row in rows:
            if version is not None and row.version != version:
                continue
            row.status = "inactive"
            updated += 1
        self.db.flush()
        return updated
