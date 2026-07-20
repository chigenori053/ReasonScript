"""Shared helpers for building provenance-bearing synthetic update packages."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from toolchain.install_update.package_provenance import (
    VALIDATION_PROFILE_DECLARATION_SCHEMA,
    VALIDATION_PROFILE_ID,
    build_manifest,
    payload_file_records,
    sha256_file,
    write_manifest,
)

DEFAULT_COMMIT = "ab12cd34" * 5
STALE_COMMIT = "ef56ab78" * 5


def write_validation_profile(payload: Path, version: str) -> Path:
    profile = payload / "metadata/validation_profile.json"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(json.dumps({
        "schema_version": VALIDATION_PROFILE_DECLARATION_SCHEMA,
        "reason_version": version,
        "install_foundation_version": "1.1",
        "runtime_version": version,
        "commands": ["--version", "doctor", "install-info", "install-validate"],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return profile


def attach_provenance(
    package_root: Path,
    *,
    version: str,
    platform: str = "macos",
    architecture: str = "arm64",
    source_commit: str = DEFAULT_COMMIT,
    package_class: str = "release",
    dirty: bool = False,
    builder_version: str = "1.0.0",
    mutate: Callable[[dict[str, Any]], None] | None = None,
    skip_sidecar_refresh: bool = False,
) -> dict[str, Any]:
    """Write a canonical provenance manifest for a synthetic package directory.

    ``mutate`` edits the manifest before serialization (tamper simulation with a
    consistent sidecar); ``skip_sidecar_refresh`` leaves a stale sidecar behind
    to simulate post-build manifest tampering.
    """
    files = payload_file_records(package_root)
    profile_path = package_root / "payload/metadata/validation_profile.json"
    git_info = {
        "source_commit": {"sha": source_commit, "short_sha": source_commit[:7]},
        "branch": "release/test",
        "source_tree": {"dirty": dirty, "tracked_changes": dirty,
                        "untracked_files": False, "submodule_changes": False},
    }
    builder = {"name": "build_update_package.py", "version": builder_version,
               "implementation_sha256": "0" * 64, "runtime": "python", "runtime_version": "3.14.0"}
    profile = {
        "profile_id": VALIDATION_PROFILE_ID,
        "profile_version": version,
        "schema_version": VALIDATION_PROFILE_DECLARATION_SCHEMA,
        "profile_sha256": sha256_file(profile_path),
        "profile_path": "payload/metadata/validation_profile.json",
    }
    manifest = build_manifest(
        expected_version=version, package_class=package_class,
        target_platform=platform, target_architecture=architecture,
        archive_format="directory", git_info=git_info, builder=builder,
        validation_profile=profile, file_records=files,
        timestamp_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    if mutate is not None and skip_sidecar_refresh:
        write_manifest(package_root, manifest)
        mutate(manifest)
        manifest_path = package_root / "metadata/update_package_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                                 encoding="utf-8")
        return manifest
    if mutate is not None:
        mutate(manifest)
    write_manifest(package_root, manifest)
    return manifest
