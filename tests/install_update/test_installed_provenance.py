"""Installed metadata retention tests (PROV-TC-017, PROV-TC-018, spec sections 17-18)."""
from __future__ import annotations

import json
from pathlib import Path

from toolchain.install_foundation import _package_provenance_summary
from toolchain.install_update.package_provenance import canonical_manifest_sha256

from tests.install_update.provenance_test_support import DEFAULT_COMMIT
from tests.install_update.test_update_core import engine, installed, package


def _update(tmp_path: Path):
    root, adapter = installed(tmp_path)
    candidate = package(tmp_path)
    updater = engine(root, adapter)
    report, code = updater.update(candidate)
    assert code == 0 and report["status"] == "completed"
    return root, adapter, updater, candidate


def test_installed_version_retains_package_manifest(tmp_path: Path) -> None:
    """PROV-TC-017: provenance is preserved and readable after a successful update."""
    root, _, _, candidate = _update(tmp_path)
    metadata = root / "versions/0.5.1/metadata"
    installed_manifest = json.loads((metadata / "update_package_manifest.json").read_text(encoding="utf-8"))
    package_manifest = json.loads((candidate / "metadata/update_package_manifest.json").read_text(encoding="utf-8"))
    assert installed_manifest == package_manifest
    sidecar = (metadata / "update_package_manifest.sha256").read_text(encoding="utf-8").strip()
    assert sidecar == canonical_manifest_sha256(installed_manifest)
    record = json.loads((metadata / "installation_record.json").read_text(encoding="utf-8"))
    assert record["installed_version"] == "0.5.1"
    assert record["transaction_id"]


def test_install_info_exposes_active_provenance(tmp_path: Path) -> None:
    root, _, _, _ = _update(tmp_path)
    summary = _package_provenance_summary(root, "0.5.1")
    assert summary is not None
    assert summary["active_version"] == "0.5.1"
    assert summary["source_commit_sha"] == DEFAULT_COMMIT
    assert summary["package_class"] == "release"
    assert summary["source_tree_dirty"] is False
    assert summary["builder_version"] == "1.0.0"


def test_transaction_artifact_records_provenance(tmp_path: Path) -> None:
    root, _, _, _ = _update(tmp_path)
    transactions = sorted((root / "metadata/transactions").glob("*.json"))
    assert transactions
    record = json.loads(transactions[-1].read_text(encoding="utf-8"))
    assert record["schema_version"] == "reasonscript-update-transaction/1.1"
    assert record["activation_status"] == "activated"
    assert record["to_version"] == "0.5.1"
    assert record["package_provenance"]["source_commit_sha"] == DEFAULT_COMMIT
    assert {"code": "UPD-PROV-001", "status": "pass"} in record["checks"]


def test_failed_gate_writes_rejected_transaction(tmp_path: Path) -> None:
    root, adapter = installed(tmp_path)
    candidate = package(tmp_path)
    (candidate / "metadata/update_package_manifest.sha256").write_text("0" * 64 + "\n", encoding="utf-8")
    report, code = engine(root, adapter).update(candidate)
    assert code != 0 and report["status"] == "failed"
    transactions = sorted((root / "metadata/transactions").glob("*.json"))
    assert transactions
    record = json.loads(transactions[-1].read_text(encoding="utf-8"))
    assert record["activation_status"] == "rejected"
    assert record["diagnostics"][0]["code"] == "INS-PROV-003"


def test_rollback_preserves_both_version_provenances(tmp_path: Path) -> None:
    """PROV-TC-018: rollback keeps the 0.5.1 manifest and the transaction history."""
    root, _, updater, _ = _update(tmp_path)
    report, code = updater.rollback()
    assert code == 0 and report["status"] == "rolled_back"
    assert json.loads((root / "metadata/current.json").read_text())["active_version"] == "0.5.0"
    # The previous version's provenance remains available after rollback.
    assert (root / "versions/0.5.1/metadata/update_package_manifest.json").is_file()
    assert _package_provenance_summary(root, "0.5.1") is not None
    history = json.loads((root / "metadata/update_history.json").read_text(encoding="utf-8"))
    assert [item["status"] for item in history["updates"]] == ["success", "rolled_back"]
    transactions = sorted((root / "metadata/transactions").glob("*.json"))
    assert transactions
