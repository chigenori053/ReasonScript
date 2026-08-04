from __future__ import annotations

import pytest

from tests.install_update.rollback_legacy_support import run_reproduction


@pytest.fixture()
def observation(tmp_path):
    return run_reproduction(tmp_path)


def test_r1_tc_003_update_reaches_activation(observation) -> None:
    update = observation["update"]
    assert update["package_validation"] == "passed"
    assert update["staging_result"] == "passed"
    assert update["version_installation_result"] == "passed"
    assert update["activation_reached"] is True


def test_r1_tc_004_post_install_failure_is_forced_and_starts_rollback(observation) -> None:
    assert observation["update"]["post_install_validation_failed"] is True
    assert observation["update"]["failure_phase"] == "validating_active"
    assert observation["update"]["failure_reason"] == "fixture_manifest_flag"
    assert observation["rollback"]["started"] is True


def test_r1_tc_005_active_pointer_is_restored(observation) -> None:
    rollback = observation["rollback"]
    assert rollback["pointer_restored"] is True
    assert rollback["restored_version"] == "0.5.0"
    assert observation["after_rollback"]["active_version"] == "0.5.0"
    assert observation["after_rollback"]["previous_version"] == "0.5.1"


def test_r1_tc_006_restored_fixed_launcher_reports_0_5_0(observation) -> None:
    assert observation["rollback"]["launcher_resolved"] is True
    assert observation["rollback"]["launcher_reported_version"] == "0.5.0"


def test_r1_tc_007_legacy_phase1r_lookup_mismatch_is_reproduced(observation) -> None:
    rollback = observation["rollback"]
    assert rollback["phase1r_fixture_lookup_attempted"] is True
    assert rollback["phase1r_fixture_exists"] is False
    assert rollback["phase1r_fixture_path"] == "<install-root>/versions/0.5.0/canonical_fixtures/phase1r"


def test_r1_tc_008_current_ins_upd_012_misclassification_is_reproduced(observation) -> None:
    assert observation["current_behavior"] == {
        "top_level_status": "failed",
        "diagnostic_code": "INS-UPD-012",
        "exit_code": 10,
    }
    assert observation["diagnostic"]["message_classification"] == "rollback_failure"


def test_r1_tc_009_operational_recovery_and_user_data_are_independent(observation) -> None:
    after = observation["after_rollback"]
    assert observation["environment"]["operational_recovery_confirmed"] is True
    assert after["doctor_status"] == "passed"
    assert after["install_info_status"] == "passed"
    assert after["install_validate_status"] == "passed"
    assert after["required_components_present"] is True
    assert after["failed_version_directory_exists"] is True
    assert after["user_data_preserved"] is True
