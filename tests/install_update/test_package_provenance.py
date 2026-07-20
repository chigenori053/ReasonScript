"""Manifest foundation tests (PROV-TC-001, PROV-TC-005, PROV-TC-019)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from toolchain.install_update.package_provenance import (
    PROVENANCE_MANIFEST_SCHEMA,
    ProvenanceBuildError,
    canonical_json,
    canonical_manifest_sha256,
    git_provenance,
    payload_file_records,
    payload_hash,
    sha256_bytes,
)
from toolchain.install_update.package_validator import validate_package_provenance

from tests.install_update.provenance_test_support import DEFAULT_COMMIT, attach_provenance
from tests.install_update.test_update_core import engine, installed, package


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                   env={"PATH": "/usr/bin:/bin", "HOME": str(root),
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"})


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "file.txt").write_text("one\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "file.txt")
    _git(root, "commit", "-q", "-m", "initial")
    return root


def test_clean_tree_provenance_records_commit_and_clean_state(repo: Path) -> None:
    info = git_provenance(repo)
    assert len(info["source_commit"]["sha"]) == 40
    assert info["source_commit"]["short_sha"] == info["source_commit"]["sha"][:7]
    assert info["source_tree"] == {"dirty": False, "tracked_changes": False,
                                   "untracked_files": False, "submodule_changes": False}


def test_dirty_tracked_and_untracked_states_are_detected(repo: Path) -> None:
    (repo / "file.txt").write_text("two\n", encoding="utf-8")
    tracked = git_provenance(repo)["source_tree"]
    assert tracked["dirty"] and tracked["tracked_changes"] and not tracked["untracked_files"]
    _git(repo, "checkout", "--", "file.txt")
    (repo / "extra.txt").write_text("x\n", encoding="utf-8")
    untracked = git_provenance(repo)["source_tree"]
    assert untracked["dirty"] and untracked["untracked_files"] and not untracked["tracked_changes"]


def test_non_git_directory_is_rejected(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(ProvenanceBuildError):
        git_provenance(plain)


def test_manifest_is_canonical_and_deterministic(tmp_path: Path) -> None:
    candidate = package(tmp_path)
    manifest_path = candidate / "metadata/update_package_manifest.json"
    sidecar = candidate / "metadata/update_package_manifest.sha256"
    first = manifest_path.read_bytes()
    manifest = attach_provenance(candidate, version="0.5.1")
    assert manifest["schema_version"] == PROVENANCE_MANIFEST_SCHEMA
    # PROV-TC-019: identical inputs serialize byte-identically apart from the timestamp.
    second = manifest_path.read_bytes()
    strip = lambda data: b"\n".join(line for line in data.splitlines() if b"timestamp_utc" not in line)
    assert strip(first) == strip(second)
    assert sidecar.read_text(encoding="utf-8").strip() == sha256_bytes(second)
    assert canonical_manifest_sha256(manifest) == sha256_bytes(canonical_json(manifest).encode("utf-8"))
    assert b"\r" not in second and second.endswith(b"}\n")


def test_payload_records_are_sorted_and_hashed(tmp_path: Path) -> None:
    candidate = package(tmp_path)
    records = payload_file_records(candidate)
    assert records == sorted(records, key=lambda item: item["path"])
    assert all(item["path"].startswith("payload/") and len(item["sha256"]) == 64 for item in records)
    assert payload_hash(records) == payload_hash(list(reversed(records)))


def test_valid_package_validates_and_reports_provenance(tmp_path: Path) -> None:
    candidate = package(tmp_path)
    report = validate_package_provenance(candidate, platform="macos", architecture="arm64",
                                         expected_version="0.5.1")
    assert report.valid
    assert report.freshness == "unknown"
    assert report.summary()["source_commit_sha"] == DEFAULT_COMMIT
    assert all(status == "pass" for status in report.checks.values())


def test_fresh_package_matches_expected_commit(tmp_path: Path) -> None:
    candidate = package(tmp_path)
    report = validate_package_provenance(candidate, expected_commit=DEFAULT_COMMIT)
    assert report.valid and report.freshness == "fresh"


def test_update_check_reports_provenance_and_freshness(tmp_path: Path) -> None:
    root, adapter = installed(tmp_path)
    plan = engine(root, adapter).check(package(tmp_path))
    assert plan["status"] == "update_available"
    assert plan["freshness"] == {"status": "unknown"}
    provenance = plan["package_provenance"]
    assert provenance["expected_version"] == "0.5.1"
    assert provenance["source_commit_sha"] == DEFAULT_COMMIT
    assert provenance["dirty"] is False
    assert provenance["builder_version"] == "1.0.0"
