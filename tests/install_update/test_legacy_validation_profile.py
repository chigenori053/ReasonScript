from __future__ import annotations

from pathlib import Path

import pytest

from toolchain.install_update.validation_profile import ValidationProfileResolutionError, resolve_validation_profile
from tests.install_update.validation_profile_test_support import materialize_profiles


def _inventory(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))


def test_r2_tc_002_legacy_0_5_0_fallback_does_not_probe_phase1r(tmp_path) -> None:
    legacy, _ = materialize_profiles(tmp_path)
    before = _inventory(legacy)
    profile = resolve_validation_profile(legacy, expected_version="0.5.0")
    assert profile.profile_source == "legacy_fallback"
    assert all(item.status == "available" for item in profile.baseline.values() if item.declared and item.required_level == "required")
    assert profile.features["phase1r_validate"].status == "not_declared"
    assert profile.fixtures["phase1r"].status == "not_declared"
    assert not (legacy / "canonical_fixtures/phase1r").exists()
    assert _inventory(legacy) == before
    assert profile.diagnostics[0].code == "VP-LEGACY-001"


def test_r2_tc_011_unknown_release_uses_minimum_baseline(tmp_path) -> None:
    release = tmp_path / "unknown"
    release.mkdir()
    (release / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    profile = resolve_validation_profile(release)
    assert profile.profile_source == "minimum_baseline"
    assert {item.code for item in profile.diagnostics} == {"VP-RES-004", "VP-LEGACY-002"}
    assert all(item.status == "not_declared" for item in profile.features.values())


def test_r2_tc_012_expected_version_mismatch_is_typed(tmp_path) -> None:
    legacy, _ = materialize_profiles(tmp_path)
    with pytest.raises(ValidationProfileResolutionError) as caught:
        resolve_validation_profile(legacy, expected_version="0.5.1")
    assert caught.value.code == "VP-RES-003"


def test_missing_release_root_is_a_typed_input_error(tmp_path) -> None:
    with pytest.raises(ValidationProfileResolutionError) as caught:
        resolve_validation_profile(tmp_path / "missing")
    assert caught.value.code == "VP-RES-001"
