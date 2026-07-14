from __future__ import annotations

import json
from pathlib import Path

from toolchain.install_update.core import UpdateEngine
from toolchain.install_update.platform import PlatformAdapter
from tests.install_update.rollback_legacy_support import INSTALLED_FIXTURE, PACKAGE_FIXTURE


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_r1_tc_001_legacy_fixture_contract() -> None:
    manifest = _read(INSTALLED_FIXTURE / "install_manifest.json")
    version_root = INSTALLED_FIXTURE / "versions/0.5.0"
    assert manifest["reason_version"] == "0.5.0"
    assert manifest["runtime_version"] == "0.5.0"
    assert manifest["install_foundation_version"] == "1.0"
    assert manifest["validation"]["status"] == "pass"
    assert all((version_root / item).exists() for item in ("reason", "runtime", "toolchain", "schemas", "standard_library", "metadata"))
    assert not (version_root / "canonical_fixtures/phase1r").exists()


def test_r1_tc_001_legacy_launcher_and_user_data_resources_exist() -> None:
    assert (INSTALLED_FIXTURE / "bin/reason").is_file()
    for relative in (
        "config/user.json",
        "projects/sample-project/project.rsn",
        "artifacts/sample-artifact.json",
        "cache/sample-cache",
    ):
        assert (INSTALLED_FIXTURE / relative).is_file()


def test_r1_tc_002_update_package_contract_and_checksums() -> None:
    manifest = _read(PACKAGE_FIXTURE / "manifest.json")
    assert manifest["package_version"] == "0.5.1"
    assert manifest["minimum_previous_version"] == "0.5.0"
    assert manifest["platform"] == "macos"
    assert manifest["architecture"] == "arm64"
    assert manifest["test_hooks"]["force_post_install_validation_failure"] is True
    fixtures = PACKAGE_FIXTURE / "payload/canonical_fixtures/phase1r"
    assert {path.name for path in fixtures.glob("*.rsn")} == {
        "tensor_namespace_probe.rsn",
        "tensor_integration_probe.rsn",
        "iterative_state_probe.rsn",
    }
    package = UpdateEngine(Path("/unused"), PlatformAdapter("macos", "arm64")).open_package(PACKAGE_FIXTURE)
    package.close()
