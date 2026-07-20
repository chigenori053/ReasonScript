"""Freshness gate tests (PROV-TC-004, PROV-TC-014, PROV-TC-015, spec section 23)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from toolchain.install_update.core import UpdateEngine, UpdateError
from toolchain.install_update.package_validator import validate_package_provenance

from tests.install_update.provenance_test_support import DEFAULT_COMMIT, STALE_COMMIT, attach_provenance
from tests.install_update.test_update_core import PASS_VALIDATION, installed, package


def _engine(root: Path, adapter, **kwargs) -> UpdateEngine:
    return UpdateEngine(root, adapter, validator=lambda _: dict(PASS_VALIDATION), **kwargs)


def test_stale_archive_is_rejected_before_staging(tmp_path: Path) -> None:
    """PROV-TC-014 / PROV-TC-020: a stale dist archive never reaches activation."""
    root, adapter = installed(tmp_path)
    candidate = package(tmp_path)
    attach_provenance(candidate, version="0.5.1", source_commit=STALE_COMMIT)
    updater = _engine(root, adapter, expected_commit=DEFAULT_COMMIT)
    report, code = updater.update(candidate)
    assert code != 0
    assert report["status"] == "failed"
    diagnostic = report["diagnostics"][0]
    assert diagnostic["code"] in {"INS-PROV-005", "INS-PROV-014"}
    assert diagnostic["expected"] == DEFAULT_COMMIT
    assert diagnostic["actual"] == STALE_COMMIT
    # Rejected before staging/activation: no rollback needed, active version unchanged.
    assert not (root / "versions/0.5.1").exists()
    assert updater.discover()["current"]["active_version"] == "0.5.0"


def test_stale_check_reports_freshness_status(tmp_path: Path) -> None:
    root, adapter = installed(tmp_path)
    candidate = package(tmp_path)
    attach_provenance(candidate, version="0.5.1", source_commit=STALE_COMMIT)
    report = _engine(root, adapter, expected_commit=DEFAULT_COMMIT).check(candidate)
    assert report["status"] == "package_rejected"
    assert report["freshness"] == {"status": "stale"}
    assert report["package_provenance"]["source_commit_sha"] == STALE_COMMIT


def test_fresh_package_updates_successfully(tmp_path: Path) -> None:
    """PROV-TC-015: a package from the expected release commit is fresh and installs."""
    root, adapter = installed(tmp_path)
    candidate = package(tmp_path)
    updater = _engine(root, adapter, expected_commit=DEFAULT_COMMIT)
    plan = updater.check(candidate)
    assert plan["status"] == "update_available"
    assert plan["freshness"] == {"status": "fresh"}
    report, code = updater.update(candidate)
    assert code == 0 and report["status"] == "completed"


def test_development_package_requires_explicit_opt_in(tmp_path: Path) -> None:
    """PROV-TC-004: dirty development packages are rejected on the release path."""
    root, adapter = installed(tmp_path)
    candidate = package(tmp_path)
    attach_provenance(candidate, version="0.5.1", package_class="development", dirty=True)
    with pytest.raises(UpdateError) as rejected:
        _engine(root, adapter).plan(_engine(root, adapter).open_package(candidate))
    assert rejected.value.code == "INS-PROV-015"
    report, code = _engine(root, adapter, allow_development_package=True).update(candidate)
    assert code == 0 and report["status"] == "completed"


def test_dirty_release_package_is_rejected(tmp_path: Path) -> None:
    root, adapter = installed(tmp_path)
    candidate = package(tmp_path)
    attach_provenance(candidate, version="0.5.1", package_class="release", dirty=True)
    report, code = _engine(root, adapter).update(candidate)
    assert code != 0
    assert report["diagnostics"][0]["code"] == "INS-PROV-006"


def test_legacy_package_without_manifest_is_rejected(tmp_path: Path) -> None:
    """Spec section 23: packages without provenance metadata are rejected by default."""
    root, adapter = installed(tmp_path)
    candidate = package(tmp_path)
    shutil.rmtree(candidate / "metadata")
    report, code = _engine(root, adapter).update(candidate)
    assert code != 0
    assert report["diagnostics"][0]["code"] == "INS-PROV-020"
    legacy_report, legacy_code = _engine(root, adapter, allow_legacy_package=True).update(candidate)
    assert legacy_code == 0 and legacy_report["status"] == "completed"


def test_development_freshness_classification(tmp_path: Path) -> None:
    candidate = package(tmp_path)
    attach_provenance(candidate, version="0.5.1", package_class="development", dirty=True)
    report = validate_package_provenance(candidate, allow_development=True)
    assert report.valid and report.freshness == "development"
