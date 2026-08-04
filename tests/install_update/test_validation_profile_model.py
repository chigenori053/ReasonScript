from __future__ import annotations

import dataclasses
import json

import pytest

from tests.install_update.validation_profile_test_support import materialize_profiles
from toolchain.install_update.validation_profile import (
    PROFILE_SCHEMA,
    resolve_validation_profile,
)


def test_r2_tc_001_canonical_model_is_immutable_and_serializable(tmp_path) -> None:
    _, current = materialize_profiles(tmp_path)
    profile = resolve_validation_profile(current)
    assert profile.schema_version == PROFILE_SCHEMA
    assert json.loads(profile.canonical_json()) == profile.to_dict()
    assert profile.canonical_json().endswith("\n")
    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.reason_version = "changed"
    with pytest.raises(TypeError):
        profile.baseline["version"] = profile.baseline["version"]


def test_model_separates_baseline_features_declaration_and_availability(tmp_path) -> None:
    _, current = materialize_profiles(tmp_path)
    profile = resolve_validation_profile(current)
    assert profile.baseline["version"].category == "baseline"
    assert profile.features["phase1r_validate"].category == "feature"
    assert profile.features["phase1r_validate"].declared is True
    assert profile.features["phase1r_validate"].status == "available"
    assert profile.features["reasoning_runtime"].declared is False
    assert profile.features["reasoning_runtime"].status == "not_declared"
