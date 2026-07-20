"""Provenance metadata collection and canonical package manifest generation.

Implements the manifest foundation of the Update Package Provenance and
Freshness Verification Specification v0.1 (schema
``reasonscript-update-package-manifest/1.0``).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PROVENANCE_MANIFEST_SCHEMA = "reasonscript-update-package-manifest/1.0"
PROVENANCE_MANIFEST_NAME = "update_package_manifest.json"
PROVENANCE_MANIFEST_HASH_NAME = "update_package_manifest.sha256"
PROVENANCE_METADATA_DIR = "metadata"
VALIDATION_PROFILE_ID = "reasonscript-validation-profile"
VALIDATION_PROFILE_DECLARATION_SCHEMA = "reasonscript-validation-profile-declaration/1.0"
BUILDER_NAME = "build_update_package.py"
BUILDER_VERSION = "1.0.0"
PACKAGE_CLASSES = ("release", "development")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ProvenanceBuildError(Exception):
    """Raised when provenance information cannot be collected for a build."""


def canonical_json(payload: dict[str, Any]) -> str:
    """Serialize a manifest deterministically (UTF-8, sorted keys, LF)."""
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_manifest_sha256(manifest: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json(manifest).encode("utf-8"))


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


def git_provenance(root: Path) -> dict[str, Any]:
    """Collect commit, branch, and dirty-state information from ``root``.

    Raises ProvenanceBuildError when ``root`` is not a Git work tree or the
    HEAD commit cannot be resolved (BLD-PROV-001/002).
    """
    inside = _git(root, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        raise ProvenanceBuildError("Source tree is not a Git work tree; release provenance requires Git.")
    head = _git(root, "rev-parse", "HEAD")
    if head.returncode != 0 or not COMMIT_PATTERN.match(head.stdout.strip()):
        raise ProvenanceBuildError("HEAD commit cannot be resolved for provenance recording.")
    sha = head.stdout.strip()
    branch_result = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "HEAD"
    status = _git(root, "status", "--porcelain")
    if status.returncode != 0:
        raise ProvenanceBuildError("Source tree status cannot be inspected for dirty detection.")
    tracked_changes = False
    untracked_files = False
    for line in status.stdout.splitlines():
        if not line.strip():
            continue
        if line.startswith("??"):
            untracked_files = True
        else:
            tracked_changes = True
    submodules = _git(root, "submodule", "status", "--recursive")
    submodule_changes = submodules.returncode == 0 and any(
        line[:1] in {"+", "-", "U"} for line in submodules.stdout.splitlines() if line.strip()
    )
    return {
        "source_commit": {"sha": sha, "short_sha": sha[:7]},
        "branch": branch,
        "source_tree": {
            "dirty": tracked_changes or untracked_files or submodule_changes,
            "tracked_changes": tracked_changes,
            "untracked_files": untracked_files,
            "submodule_changes": submodule_changes,
        },
    }


def builder_metadata(script_path: Path) -> dict[str, Any]:
    """Describe the builder implementation (BLD-PROV-006)."""
    if not script_path.is_file():
        raise ProvenanceBuildError(f"Builder implementation cannot be hashed: {script_path}")
    return {
        "name": BUILDER_NAME,
        "version": BUILDER_VERSION,
        "implementation_sha256": sha256_file(script_path),
        "runtime": "python",
        "runtime_version": "{}.{}.{}".format(*sys.version_info[:3]),
    }


def payload_file_records(package_root: Path) -> list[dict[str, Any]]:
    """Hash every payload file (BLD-PROV-007). Paths are ``payload/``-relative."""
    payload = package_root / "payload"
    if not payload.is_dir():
        raise ProvenanceBuildError("Package payload directory is missing.")
    records = []
    for path in sorted(payload.rglob("*")):
        if path.is_symlink():
            raise ProvenanceBuildError(f"Symbolic links are not allowed in the payload: {path}")
        if not path.is_file():
            continue
        relative = f"payload/{path.relative_to(payload).as_posix()}"
        records.append({
            "path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "executable": bool(path.stat().st_mode & 0o111),
        })
    records.sort(key=lambda item: item["path"])
    return records


def payload_hash(records: list[dict[str, Any]]) -> str:
    """Hash the payload inventory in canonical path order (spec 8.4)."""
    ordered = sorted(records, key=lambda item: item["path"])
    lines = "".join(f"{item['path']}\n{item['sha256']}\n" for item in ordered)
    return sha256_bytes(lines.encode("utf-8"))


def validation_profile_metadata(package_root: Path, expected_version: str) -> dict[str, Any]:
    """Record the packaged validation profile declaration (BLD-PROV-005)."""
    profile_path = package_root / "payload/metadata/validation_profile.json"
    if not profile_path.is_file():
        raise ProvenanceBuildError("Packaged validation profile declaration is missing.")
    try:
        declaration = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProvenanceBuildError(f"Packaged validation profile cannot be parsed: {exc}") from exc
    if declaration.get("schema_version") != VALIDATION_PROFILE_DECLARATION_SCHEMA:
        raise ProvenanceBuildError("Packaged validation profile declaration schema is unsupported.")
    if declaration.get("reason_version") != expected_version:
        raise ProvenanceBuildError(
            f"Validation profile targets {declaration.get('reason_version')!r}, expected {expected_version!r}."
        )
    return {
        "profile_id": VALIDATION_PROFILE_ID,
        "profile_version": str(declaration.get("reason_version")),
        "schema_version": VALIDATION_PROFILE_DECLARATION_SCHEMA,
        "profile_sha256": sha256_file(profile_path),
        "profile_path": "payload/metadata/validation_profile.json",
    }


def build_manifest(
    *,
    expected_version: str,
    package_class: str,
    target_platform: str,
    target_architecture: str,
    archive_format: str,
    git_info: dict[str, Any],
    builder: dict[str, Any],
    validation_profile: dict[str, Any],
    file_records: list[dict[str, Any]],
    timestamp_utc: str,
    repository_name: str = "ReasonScript",
    expected_commit: str | None = None,
    source_date_epoch: int | None = None,
) -> dict[str, Any]:
    if package_class not in PACKAGE_CLASSES:
        raise ProvenanceBuildError(f"Unsupported package class: {package_class}")
    build_section: dict[str, Any] = {"timestamp_utc": timestamp_utc}
    if source_date_epoch is not None:
        build_section["source_date_epoch"] = int(source_date_epoch)
    release_section: dict[str, Any] = {"expected_version": expected_version}
    release_section["expected_commit"] = expected_commit or git_info["source_commit"]["sha"]
    return {
        "schema_version": PROVENANCE_MANIFEST_SCHEMA,
        "package_id": f"reasonscript-{expected_version}-{target_platform}-{target_architecture}",
        "package_class": package_class,
        "release": release_section,
        "repository": {"name": repository_name, "branch": git_info.get("branch", "HEAD")},
        "source_commit": dict(git_info["source_commit"]),
        "source_tree": dict(git_info["source_tree"]),
        "build": build_section,
        "builder": dict(builder),
        "validation_profile": dict(validation_profile),
        "target": {
            "os": target_platform,
            "architecture": target_architecture,
            "archive_format": archive_format,
        },
        "integrity": {
            "hash_algorithm": "sha256",
            "payload_sha256": payload_hash(file_records),
            "files": file_records,
        },
    }


def write_manifest(package_root: Path, manifest: dict[str, Any]) -> tuple[Path, Path]:
    """Write the canonical manifest and its sidecar hash into the package."""
    metadata_dir = package_root / PROVENANCE_METADATA_DIR
    metadata_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = metadata_dir / PROVENANCE_MANIFEST_NAME
    sidecar_path = metadata_dir / PROVENANCE_MANIFEST_HASH_NAME
    serialized = canonical_json(manifest)
    manifest_path.write_text(serialized, encoding="utf-8")
    sidecar_path.write_text(sha256_bytes(serialized.encode("utf-8")) + "\n", encoding="utf-8")
    return manifest_path, sidecar_path


def manifest_paths(package_root: Path) -> tuple[Path, Path]:
    metadata_dir = package_root / PROVENANCE_METADATA_DIR
    return metadata_dir / PROVENANCE_MANIFEST_NAME, metadata_dir / PROVENANCE_MANIFEST_HASH_NAME
