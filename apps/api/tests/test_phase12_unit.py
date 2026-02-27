from __future__ import annotations

from app.services.org_settings import normalize_settings
from packages.security import classify_field, detect_pii, redact_mapping


def test_phase12_detect_pii_for_email_and_phone_patterns() -> None:
    pii = detect_pii("Contact me at alice@example.com or +1 (415) 555-0199")
    assert pii["contains_email"] is True
    assert pii["contains_phone"] is True


def test_phase12_detect_pii_for_health_terms() -> None:
    pii = detect_pii("Patient diagnosis pending")
    assert pii["contains_health"] is True


def test_phase12_redaction_scrubs_secret_and_contact_data() -> None:
    payload = {
        "access_token": "abcd1234secret",
        "email": "alice@example.com",
        "phone": "+1 415-555-0199",
        "nested": {"refresh_token": "refresh-secret-value"},
    }
    redacted = redact_mapping(payload)

    assert redacted["access_token"] == "[redacted-secret]"
    assert redacted["nested"]["refresh_token"] == "[redacted-secret]"
    assert "example.com" not in str(redacted)
    assert "555-0199" not in str(redacted)


def test_phase12_field_classification_health_and_secret() -> None:
    assert classify_field("medical_note", "Patient diagnosis pending") == "health_related"
    assert classify_field("refresh_token", "abc") == "system_secret"


def test_phase12_org_settings_accepts_compliance_mode() -> None:
    normalized = normalize_settings({"compliance_mode": "real_estate"})
    assert normalized["compliance_mode"] == "real_estate"


def test_phase12_org_settings_defaults_to_none_on_invalid_mode() -> None:
    normalized = normalize_settings({"compliance_mode": "invalid"})
    assert normalized["compliance_mode"] == "none"
