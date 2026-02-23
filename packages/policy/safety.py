from __future__ import annotations

import re
from dataclasses import dataclass


PROMPT_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(all|previous)\s+instructions", re.IGNORECASE),
    re.compile(r"(system|developer)\s+prompt", re.IGNORECASE),
    re.compile(r"act\s+as\s+", re.IGNORECASE),
)
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{20,}", re.IGNORECASE),
    re.compile(r"ghp_[A-Za-z0-9]{20,}", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[:=]\s*\S+", re.IGNORECASE),
)
SENSITIVE_PATTERNS = (
    re.compile(r"\bssn\b|\bsocial security\b", re.IGNORECASE),
    re.compile(r"\bcredit\s*card\b|\bcc\b", re.IGNORECASE),
)
MAX_BODY_LEN = 4000


@dataclass(frozen=True)
class SafetyFilterResult:
    sanitized_text: str
    flags: dict[str, bool]


def apply_inbound_safety_filters(text: str) -> SafetyFilterResult:
    working = text.strip()
    flags = {
        "prompt_injection": False,
        "sensitive": False,
        "token_masked": False,
        "needs_human_review": False,
        "policy_blocked": False,
        "truncated": False,
    }

    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(working):
            flags["prompt_injection"] = True
            flags["needs_human_review"] = True
            working = pattern.sub("[prompt-directive-removed]", working)

    for pattern in SECRET_PATTERNS:
        if pattern.search(working):
            flags["token_masked"] = True
            flags["needs_human_review"] = True
            working = pattern.sub("[secret-masked]", working)

    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(working):
            flags["sensitive"] = True
            flags["needs_human_review"] = True

    if len(working) > MAX_BODY_LEN:
        flags["truncated"] = True
        working = working[:MAX_BODY_LEN]

    return SafetyFilterResult(sanitized_text=working, flags=flags)
