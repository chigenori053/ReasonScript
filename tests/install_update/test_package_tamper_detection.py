"""Tamper detection tests (PROV-TC-006..013, PROV-TC-016, spec section 24)."""
from __future__ import annotations

import json
from pathlib import Path

from toolchain.install_update.package_validator import validate_package_provenance

from tests.install_update.provenance_test_support import STALE_COMMIT, attach_provenance
from tests.install_update.test_update_core import _write, package


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def test_manifest_tamper_without_sidecar_refresh_is_detected(tmp_path: Path) -> None:
    """PROV-TC-012: editing the manifest while keeping the old sidecar hash fails."""
    candidate = package(tmp_path)
    manifest_path = candidate / "metadata/update_package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_commit"]["sha"] = STALE_COMMIT
    manifest["source_commit"]["short_sha"] = STALE_COMMIT[:7]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    report = validate_package_provenance(candidate)
    assert not report.valid
    assert "INS-PROV-003" in _codes(report)
    assert report.freshness == "invalid"


def test_missing_manifest_is_detected(tmp_path: Path) -> None:
    """PROV-TC-013: a package without the provenance manifest reports INS-PROV-001."""
    candidate = package(tmp_path)
    (candidate / "metadata/update_package_manifest.json").unlink()
    report = validate_package_provenance(candidate)
    assert report.manifest is None
    assert "INS-PROV-001" in _codes(report)
    assert report.freshness == "invalid"


def test_payload_file_tamper_is_detected(tmp_path: Path) -> None:
    """PROV-TC-011: modifying a payload file breaks the file and payload hashes."""
    candidate = package(tmp_path)
    (candidate / "payload/reason").write_text("tampered", encoding="utf-8")
    report = validate_package_provenance(candidate)
    assert not report.valid
    assert "INS-PROV-012" in _codes(report)


def test_unrecorded_payload_file_is_detected(tmp_path: Path) -> None:
    candidate = package(tmp_path)
    _write(candidate / "payload/injected.py", "print('x')\n")
    report = validate_package_provenance(candidate)
    assert not report.valid
    assert "INS-PROV-012" in _codes(report)


def test_expected_version_mismatch_is_detected(tmp_path: Path) -> None:
    """PROV-TC-007: manifest version 0.5.2 against payload/CLI version 0.5.1."""
    candidate = package(tmp_path)

    def bump(manifest: dict) -> None:
        manifest["release"]["expected_version"] = "0.5.2"

    attach_provenance(candidate, version="0.5.1", mutate=bump)
    report = validate_package_provenance(candidate, expected_version="0.5.1")
    assert not report.valid
    assert {"INS-PROV-007", "INS-PROV-016"} & _codes(report)


def test_validation_profile_tamper_is_detected(tmp_path: Path) -> None:
    """PROV-TC-008: a profile hash mismatch is rejected."""
    candidate = package(tmp_path)

    def corrupt(manifest: dict) -> None:
        manifest["validation_profile"]["profile_sha256"] = "f" * 64

    attach_provenance(candidate, version="0.5.1", mutate=corrupt)
    report = validate_package_provenance(candidate)
    assert not report.valid
    assert "INS-PROV-008" in _codes(report)


def test_unsupported_builder_version_is_detected(tmp_path: Path) -> None:
    """PROV-TC-009: builder versions outside the supported range are rejected."""
    candidate = package(tmp_path)
    attach_provenance(candidate, version="0.5.1", builder_version="99.0.0")
    report = validate_package_provenance(candidate)
    assert not report.valid
    assert "INS-PROV-009" in _codes(report)


def test_platform_target_mismatch_is_detected(tmp_path: Path) -> None:
    """PROV-TC-016: a linux/x86_64 package is rejected on macos/arm64."""
    candidate = package(tmp_path, platform="linux", architecture="x86_64")
    report = validate_package_provenance(candidate, platform="macos", architecture="arm64")
    assert not report.valid
    assert "INS-PROV-013" in _codes(report)


def test_incomplete_provenance_metadata_is_detected(tmp_path: Path) -> None:
    candidate = package(tmp_path)

    def drop(manifest: dict) -> None:
        del manifest["builder"]

    attach_provenance(candidate, version="0.5.1", mutate=drop)
    report = validate_package_provenance(candidate)
    assert not report.valid
    assert "INS-PROV-020" in _codes(report)
    assert report.freshness == "invalid"
