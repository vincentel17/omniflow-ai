#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.verticals import validate_pack  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: scripts/validate-pack.py <slug>")
        return 1

    slug = sys.argv[1].strip()
    valid, errors = validate_pack(slug)
    if valid:
        print(f"pack '{slug}' is valid")
        return 0

    print(f"pack '{slug}' is invalid:")
    for error in errors:
        print(f"- {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
