from __future__ import annotations

from tests.install_update.validation_profile_test_support import materialize_profiles
from toolchain.install_update.validation_profile import resolve_validation_profile


def test_r2_tc_003_declared_0_5_1_profile_resolution(tmp_path) -> None:
    _, current = materialize_profiles(tmp_path)
    profile = resolve_validation_profile(current, expected_version="0.5.1")
    phase1r = profile.features["phase1r_validate"]
    fixture = profile.fixtures["phase1r"]
    assert profile.profile_source == "release_metadata"
    assert profile.reason_version == "0.5.1"
    assert phase1r.declared is True
    assert phase1r.command_available is True
    assert phase1r.status == "available"
    assert fixture.status == "available"
    assert fixture.missing_files == ()
    assert profile.summary.required_capabilities_ready is True


def test_resolution_does_not_execute_validation_commands(monkeypatch, tmp_path) -> None:
    _, current = materialize_profiles(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError("resolver must not execute subprocesses")
    monkeypatch.setattr("subprocess.run", forbidden)
    assert resolve_validation_profile(current).profile_source == "release_metadata"
