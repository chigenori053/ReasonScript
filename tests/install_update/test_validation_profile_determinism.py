from __future__ import annotations

import json

from conformance.schema_validator import SchemaValidator
from tests.install_update.validation_profile_test_support import (
    PHASE_R2_ARTIFACTS,
    REPOSITORY_ROOT,
    materialize_profiles,
)
from toolchain.install_update.validation_profile import resolve_validation_profile


def test_r2_tc_013_profiles_are_deterministic_and_canonical(tmp_path) -> None:
    legacy, current = materialize_profiles(tmp_path)
    first_legacy = resolve_validation_profile(legacy).canonical_json()
    second_legacy = resolve_validation_profile(legacy).canonical_json()
    first_current = resolve_validation_profile(current).canonical_json()
    second_current = resolve_validation_profile(current).canonical_json()
    assert first_legacy == second_legacy
    assert first_current == second_current
    assert "<release-root>" in first_legacy
    assert str(tmp_path) not in first_legacy + first_current


def test_canonical_artifacts_match_resolved_profiles(tmp_path) -> None:
    legacy, current = materialize_profiles(tmp_path)
    expected_legacy = json.loads((PHASE_R2_ARTIFACTS / "validation_profile_0_5_0.json").read_text(encoding="utf-8"))
    expected_current = json.loads((PHASE_R2_ARTIFACTS / "validation_profile_0_5_1.json").read_text(encoding="utf-8"))
    assert resolve_validation_profile(legacy).to_dict() == expected_legacy
    assert resolve_validation_profile(current).to_dict() == expected_current


def test_profile_and_declaration_schemas_validate_canonical_documents(tmp_path) -> None:
    _, current = materialize_profiles(tmp_path)
    validator = SchemaValidator(REPOSITORY_ROOT / "schemas")
    declaration = json.loads((current / "metadata/validation_profile.json").read_text(encoding="utf-8"))
    validator.validate_file(resolve_validation_profile(current).to_dict(), "validation_profile.schema.json")
    validator.validate_file(declaration, "validation_profile_declaration.schema.json")


def test_phase_r2_summary_artifact_contract() -> None:
    summary = json.loads((PHASE_R2_ARTIFACTS / "validation_profile_foundation_summary.json").read_text(encoding="utf-8"))
    assert summary["schema_version"] == "reasonscript-validation-profile-foundation-summary/1.0"
    assert summary["status"] == "validated"
    assert summary["diagnostics"] == []
