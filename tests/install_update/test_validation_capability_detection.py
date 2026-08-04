from __future__ import annotations

import shutil

from tests.install_update.validation_profile_test_support import (
    materialize_profiles,
    read_declaration,
    write_declaration,
)
from toolchain.install_update.validation_profile import resolve_validation_profile


def _codes(profile) -> set[str]:
    return {item.code for item in profile.diagnostics}


def test_r2_tc_004_missing_optional_fixture_is_normalized(tmp_path) -> None:
    _, current = materialize_profiles(tmp_path)
    shutil.rmtree(current / "canonical_fixtures/phase1r")
    profile = resolve_validation_profile(current)
    assert profile.fixtures["phase1r"].status == "missing"
    assert profile.features["phase1r_validate"].status == "unavailable"
    assert "VP-CAP-002" in _codes(profile)


def test_r2_tc_005_incomplete_fixture_lists_missing_probe(tmp_path) -> None:
    _, current = materialize_profiles(tmp_path)
    (current / "canonical_fixtures/phase1r/tensor_namespace_probe.rsn").unlink()
    profile = resolve_validation_profile(current)
    assert profile.fixtures["phase1r"].status == "incomplete"
    assert profile.fixtures["phase1r"].missing_files == ("tensor_namespace_probe.rsn",)
    assert profile.features["phase1r_validate"].status == "unavailable"
    assert "VP-CAP-003" in _codes(profile)


def test_r2_tc_006_unregistered_command_is_unavailable(tmp_path) -> None:
    _, current = materialize_profiles(tmp_path)
    declaration = read_declaration(current)
    declaration["commands"].remove("phase1r-validate")
    write_declaration(current, declaration)
    profile = resolve_validation_profile(current)
    capability = profile.features["phase1r_validate"]
    assert capability.command_available is False
    assert capability.status == "unavailable"
    assert "VP-CAP-001" in _codes(profile)


def test_r2_tc_007_required_component_missing_changes_readiness(tmp_path) -> None:
    _, current = materialize_profiles(tmp_path)
    shutil.rmtree(current / "runtime")
    profile = resolve_validation_profile(current)
    assert profile.components["runtime-core"].status == "missing"
    assert profile.summary.required_capabilities_ready is False
    assert "VP-CAP-004" in _codes(profile)


def test_r2_tc_008_required_schema_missing_changes_readiness(tmp_path) -> None:
    _, current = materialize_profiles(tmp_path)
    (current / "schemas/base.json").unlink()
    profile = resolve_validation_profile(current)
    assert profile.schemas["base"].status == "missing"
    assert profile.summary.required_capabilities_ready is False
    assert "VP-CAP-005" in _codes(profile)


def test_undeclared_required_baseline_changes_readiness(tmp_path) -> None:
    _, current = materialize_profiles(tmp_path)
    declaration = read_declaration(current)
    del declaration["baseline"]["doctor"]
    write_declaration(current, declaration)
    profile = resolve_validation_profile(current)
    assert profile.baseline["doctor"].status == "not_declared"
    assert profile.summary.required_capabilities_ready is False
