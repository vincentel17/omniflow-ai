from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RiskTier(str, Enum):
    TIER_0 = "TIER_0"
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"
    TIER_4 = "TIER_4"


@dataclass(frozen=True)
class ValidationResult:
    allowed: bool
    reasons: list[str]


class PolicyEngine:
    def __init__(self, pack_slug: str, rules: dict[str, Any]) -> None:
        self.pack_slug = pack_slug
        self.rules = rules

    def validate_content(self, content: str, context: dict[str, Any] | None = None) -> ValidationResult:
        del context
        prohibited_words = self.rules.get("content", {}).get("prohibited_words", [])
        lower_content = content.lower()
        hits = [word for word in prohibited_words if word.lower() in lower_content]
        if hits:
            return ValidationResult(allowed=False, reasons=[f"prohibited_content:{word}" for word in hits])
        return ValidationResult(allowed=True, reasons=[])

    def validate_action(self, action: str, context: dict[str, Any] | None = None) -> ValidationResult:
        del context
        blocked_actions = self.rules.get("actions", {}).get("blocked", [])
        if action in blocked_actions:
            return ValidationResult(allowed=False, reasons=[f"blocked_action:{action}"])
        return ValidationResult(allowed=True, reasons=[])

    def risk_tier(self, action: str, context: dict[str, Any] | None = None) -> RiskTier:
        del context
        override = self.rules.get("risk", {}).get("overrides", {}).get(action)
        if override is not None:
            return RiskTier(override)
        return RiskTier.TIER_1
