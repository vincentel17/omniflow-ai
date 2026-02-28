from __future__ import annotations

from app.services.verticals import pack_feature_flags, validate_pack


def test_phase15_manifest_validation_for_known_pack() -> None:
    valid, errors = validate_pack("generic")
    assert valid is True
    assert errors == []


def test_phase15_manifest_validation_fails_for_unknown_pack() -> None:
    valid, errors = validate_pack("does-not-exist")
    assert valid is False
    assert any("Unknown vertical pack" in error for error in errors)


def test_phase15_pack_config_loading_features() -> None:
    features = pack_feature_flags("real-estate")
    assert features["pipelines"] is True
    assert features["optimization"] is True
