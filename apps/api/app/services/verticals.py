from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

REQUIRED_PACK_FILES = (
    "policy.rules.yaml",
    "pipelines.json",
    "workflows.json",
    "scoring.json",
    "seo_archetypes.json",
)


def _verticals_root() -> Path:
    return Path(__file__).resolve().parents[4] / "packages" / "verticals"


def list_available_packs() -> list[str]:
    packs: list[str] = []
    for entry in _verticals_root().iterdir():
        if not entry.is_dir():
            continue
        if all((entry / required_file).exists() for required_file in REQUIRED_PACK_FILES):
            packs.append(entry.name)
    return sorted(packs)


def load_pack_file(pack_slug: str, filename: str) -> dict[str, Any]:
    pack_dir = _verticals_root() / pack_slug
    if not pack_dir.exists():
        raise FileNotFoundError(f"Unknown vertical pack: {pack_slug}")
    target = pack_dir / filename
    if filename.endswith(".yaml"):
        return yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    return json.loads(target.read_text(encoding="utf-8"))
