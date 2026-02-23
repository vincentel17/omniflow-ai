from __future__ import annotations

from packages.policy import PolicyEngine

from .verticals import load_pack_file


def load_policy_engine(pack_slug: str) -> PolicyEngine:
    rules = load_pack_file(pack_slug, "policy.rules.yaml")
    return PolicyEngine(pack_slug=pack_slug, rules=rules)
