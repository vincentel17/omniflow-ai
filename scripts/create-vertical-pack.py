#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


TEMPLATES: dict[str, object] = {
    "manifest.json": {
        "slug": "__SLUG__",
        "name": "__NAME__",
        "version": "2.0.0",
        "compatible_core_version": ">=0.1.0",
        "features": {
            "pipelines": True,
            "seo": True,
            "compliance": True,
            "ads": True,
            "workflows": True,
            "optimization": True,
        },
    },
    "pipelines.json": {"pipelines": [{"key": "default", "name": "Default Pipeline", "stages": ["new", "qualified", "won"]}]},
    "scoring.json": {"weights": {"response_speed": 0.4, "engagement": 0.3, "fit": 0.3}},
    "seo_archetypes.json": {"archetypes": [{"slug": "local-service", "title_template": "__NAME__ Service in {{city}}"}]},
    "workflows.runtime.json": {"workflows": []},
    "policy.rules.yaml": "rules:\n  - id: baseline_guardrail\n    description: Baseline compliance guardrail\n    severity: medium\n",
    "optimization_config.json": {
        "lead_scoring_weights": {"response_speed": 0.4, "engagement": 0.3, "intent": 0.3},
        "posting_optimization_enabled": True,
        "nurture_decay_factor": 0.7,
        "ads_budget_strategy": "conservative",
    },
    "entitlement_overrides.json": {"required_plan": "Growth", "addon_required": False},
}


def _title_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def _validate_slug(slug: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}[a-z0-9]", slug):
        raise SystemExit("slug must match ^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: scripts/create-vertical-pack.py <slug>")
        return 1

    slug = sys.argv[1].strip().lower()
    _validate_slug(slug)

    root = Path(__file__).resolve().parents[1] / "packages" / "verticals" / slug
    if root.exists():
        print(f"pack already exists: {slug}")
        return 1

    root.mkdir(parents=True, exist_ok=False)
    name = _title_from_slug(slug)

    for filename, payload in TEMPLATES.items():
        path = root / filename
        if filename.endswith(".yaml"):
            assert isinstance(payload, str)
            path.write_text(payload, encoding="utf-8")
            continue
        data = json.loads(json.dumps(payload).replace("__SLUG__", slug).replace("__NAME__", name))
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    print(f"created vertical pack scaffold: {slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
