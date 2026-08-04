from __future__ import annotations

import json

from tests.install_update.rollback_legacy_support import (
    ARTIFACT_OBSERVATION,
    EXPECTED_OBSERVATION,
    run_reproduction,
    stable_json,
)


def test_r1_tc_010_reproduction_is_deterministic(tmp_path) -> None:
    first = run_reproduction(tmp_path / "first")
    second = run_reproduction(tmp_path / "second")
    assert stable_json(first) == stable_json(second)


def test_canonical_observation_matches_fixture_and_artifact(tmp_path) -> None:
    actual = run_reproduction(tmp_path)
    expected = json.loads(EXPECTED_OBSERVATION.read_text(encoding="utf-8"))
    artifact = json.loads(ARTIFACT_OBSERVATION.read_text(encoding="utf-8"))
    assert actual == expected == artifact


def test_observation_separates_recovery_from_validation_failure(tmp_path) -> None:
    observation = run_reproduction(tmp_path)
    assert observation["rollback"]["pointer_restored"] is True
    assert observation["rollback"]["validation_failed"] is True
    assert observation["current_behavior"]["top_level_status"] == "failed"
    assert observation["environment"]["operational_recovery_confirmed"] is True
    assert observation["environment"]["temporary_install_root"] is True
    assert observation["environment"]["network_used"] is False
