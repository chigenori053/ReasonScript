"""Update package provenance validation and freshness classification.

Implements the install-side gates (UPD-PROV-001..014), the INS-PROV
diagnostic vocabulary, and the fresh/stale/unknown/invalid/development
freshness classification defined by the Update Package Provenance and
Freshness Verification Specification v0.1.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .package_provenance import (
    COMMIT_PATTERN,
    PACKAGE_CLASSES,
    PROVENANCE_MANIFEST_SCHEMA,
    SHA256_PATTERN,
    canonical_manifest_sha256,
    manifest_paths,
    payload_hash,
    sha256_file,
)

SUPPORTED_BUILDER_NAMES = {"build_update_package.py"}
SUPPORTED_BUILDER_MAJOR_VERSIONS = {1}

FRESHNESS_FRESH = "fresh"
FRESHNESS_STALE = "stale"
FRESHNESS_UNKNOWN = "unknown"
FRESHNESS_INVALID = "invalid"
FRESHNESS_DEVELOPMENT = "development"

PROVENANCE_DIAGNOSTICS = {
    "INS-PROV-001": "Package provenance manifest is missing.",
    "INS-PROV-002": "Package provenance manifest schema is invalid.",
    "INS-PROV-003": "Package provenance manifest hash mismatch.",
    "INS-PROV-004": "Package source commit is missing.",
    "INS-PROV-005": "Package source commit does not match the expected release commit.",
    "INS-PROV-006": "Release package was built from a dirty source tree.",
    "INS-PROV-007": "Expected release version mismatch.",
    "INS-PROV-008": "Validation profile mismatch.",
    "INS-PROV-009": "Builder version is unsupported.",
    "INS-PROV-010": "Builder implementation hash mismatch.",
    "INS-PROV-011": "Payload hash mismatch.",
    "INS-PROV-012": "Package file hash mismatch.",
    "INS-PROV-013": "Package platform target mismatch.",
    "INS-PROV-014": "Package is classified as stale.",
    "INS-PROV-015": "Development package was rejected.",
    "INS-PROV-016": "Package CLI version mismatch.",
    "INS-PROV-017": "Archive filename does not match the package manifest.",
    "INS-PROV-018": "Package self-validation failed.",
    "INS-PROV-019": "Installed manifest mismatch.",
    "INS-PROV-020": "Provenance metadata is incomplete.",
}

_GATE_CHECKS = (
    "UPD-PROV-001",
    "UPD-PROV-002",
    "UPD-PROV-003",
    "UPD-PROV-004",
    "UPD-PROV-005",
    "UPD-PROV-006",
    "UPD-PROV-007",
    "UPD-PROV-008",
    "UPD-PROV-009",
    "UPD-PROV-010",
    "UPD-PROV-011",
    "UPD-PROV-012",
    "UPD-PROV-013",
)


@dataclass(frozen=True)
class ProvenanceIssue:
    code: str
    severity: str = "fatal"
    message: str = ""
    field: str | None = None
    expected: Any = None
    actual: Any = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "category": "package_provenance",
            "message": self.message or PROVENANCE_DIAGNOSTICS.get(self.code, ""),
        }
        for key, value in (("field", self.field), ("expected", self.expected), ("actual", self.actual)):
            if value is not None:
                payload[key] = value
        return payload


@dataclass
class ProvenanceReport:
    manifest: dict[str, Any] | None = None
    issues: list[ProvenanceIssue] = field(default_factory=list)
    checks: dict[str, str] = field(default_factory=dict)
    freshness: str = FRESHNESS_UNKNOWN

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "fatal" for issue in self.issues)

    def summary(self) -> dict[str, Any]:
        manifest = self.manifest or {}
        return {
            "package_id": manifest.get("package_id"),
            "package_class": manifest.get("package_class"),
            "expected_version": (manifest.get("release") or {}).get("expected_version"),
            "source_commit_sha": (manifest.get("source_commit") or {}).get("sha"),
            "build_timestamp_utc": (manifest.get("build") or {}).get("timestamp_utc"),
            "builder_version": (manifest.get("builder") or {}).get("version"),
            "validation_profile_version": (manifest.get("validation_profile") or {}).get("profile_version"),
            "dirty": (manifest.get("source_tree") or {}).get("dirty"),
            "manifest_sha256": canonical_manifest_sha256(manifest) if manifest else None,
            "payload_sha256": (manifest.get("integrity") or {}).get("payload_sha256"),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "freshness": {"status": self.freshness},
            "package": self.summary(),
            "checks": [{"code": code, "status": status} for code, status in sorted(self.checks.items())],
            "diagnostics": [issue.to_dict() for issue in self.issues],
        }


_REQUIRED_SECTIONS = {
    "schema_version": str,
    "package_id": str,
    "package_class": str,
    "release": dict,
    "source_commit": dict,
    "source_tree": dict,
    "build": dict,
    "builder": dict,
    "validation_profile": dict,
    "target": dict,
    "integrity": dict,
}


def read_provenance_manifest(package_root: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read the packaged provenance manifest and its recorded sidecar hash."""
    manifest_path, sidecar_path = manifest_paths(package_root)
    if not manifest_path.is_file():
        return None, None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, None
    sidecar = None
    if sidecar_path.is_file():
        sidecar = sidecar_path.read_text(encoding="utf-8").strip().split()[0] if sidecar_path.read_text(encoding="utf-8").strip() else None
    return manifest if isinstance(manifest, dict) else {}, sidecar


def validate_package_provenance(
    package_root: Path,
    *,
    platform: str | None = None,
    architecture: str | None = None,
    expected_version: str | None = None,
    expected_commit: str | None = None,
    archive_name: str | None = None,
    allow_development: bool = False,
) -> ProvenanceReport:
    """Validate provenance for an extracted package rooted at ``package_root``."""
    report = ProvenanceReport(checks={code: "pass" for code in _GATE_CHECKS})

    def fail(check: str, issue: ProvenanceIssue) -> None:
        report.issues.append(issue)
        if issue.severity == "fatal":
            report.checks[check] = "fail"

    manifest, sidecar = read_provenance_manifest(package_root)
    if manifest is None:
        fail("UPD-PROV-001", ProvenanceIssue("INS-PROV-001"))
        report.freshness = FRESHNESS_INVALID
        return report
    report.manifest = manifest

    canonical_hash = canonical_manifest_sha256(manifest)
    if sidecar is None or not SHA256_PATTERN.match(sidecar):
        fail("UPD-PROV-003", ProvenanceIssue("INS-PROV-003", message="Manifest sidecar hash is missing or malformed."))
    elif sidecar != canonical_hash:
        fail("UPD-PROV-003", ProvenanceIssue("INS-PROV-003", expected=sidecar, actual=canonical_hash))

    schema_ok = manifest.get("schema_version") == PROVENANCE_MANIFEST_SCHEMA
    if not schema_ok:
        fail("UPD-PROV-002", ProvenanceIssue("INS-PROV-002", field="schema_version",
                                             expected=PROVENANCE_MANIFEST_SCHEMA, actual=manifest.get("schema_version")))
    missing = [name for name, kind in _REQUIRED_SECTIONS.items() if not isinstance(manifest.get(name), kind)]
    if missing:
        fail("UPD-PROV-002", ProvenanceIssue("INS-PROV-020", field=",".join(sorted(missing)),
                                             message="Provenance metadata is incomplete."))
        report.freshness = FRESHNESS_INVALID
        return report

    release = manifest["release"]
    source_commit = manifest["source_commit"]
    source_tree = manifest["source_tree"]
    builder = manifest["builder"]
    profile = manifest["validation_profile"]
    target = manifest["target"]
    integrity = manifest["integrity"]
    package_class = manifest.get("package_class")

    # UPD-PROV-004: package class.
    if package_class not in PACKAGE_CLASSES:
        fail("UPD-PROV-004", ProvenanceIssue("INS-PROV-002", field="package_class", actual=package_class))
    is_development = package_class == "development"
    if is_development and not allow_development:
        fail("UPD-PROV-004", ProvenanceIssue("INS-PROV-015", field="package_class", actual=package_class))

    # Source commit shape.
    sha = source_commit.get("sha")
    if not isinstance(sha, str) or not COMMIT_PATTERN.match(sha):
        fail("UPD-PROV-002", ProvenanceIssue("INS-PROV-004", field="source_commit.sha", actual=sha))
        sha = None

    # UPD-PROV-005: dirty flag policy.
    dirty = bool(source_tree.get("dirty"))
    if dirty and package_class == "release":
        fail("UPD-PROV-005", ProvenanceIssue("INS-PROV-006", field="source_tree.dirty", expected=False, actual=True))

    # UPD-PROV-006: expected release version.
    manifest_version = release.get("expected_version")
    if not isinstance(manifest_version, str) or not manifest_version:
        fail("UPD-PROV-006", ProvenanceIssue("INS-PROV-020", field="release.expected_version"))
        manifest_version = None
    if expected_version is not None and manifest_version is not None and manifest_version != expected_version:
        fail("UPD-PROV-006", ProvenanceIssue("INS-PROV-007", field="release.expected_version",
                                             expected=expected_version, actual=manifest_version))
    version_file = package_root / "payload/VERSION"
    if manifest_version is not None and version_file.is_file():
        payload_version = version_file.read_text(encoding="utf-8").strip()
        if payload_version != manifest_version:
            fail("UPD-PROV-012", ProvenanceIssue("INS-PROV-016", field="payload/VERSION",
                                                 expected=manifest_version, actual=payload_version))
    expected_id = None
    if manifest_version is not None:
        expected_id = f"reasonscript-{manifest_version}-{target.get('os')}-{target.get('architecture')}"
        if manifest.get("package_id") != expected_id:
            fail("UPD-PROV-006", ProvenanceIssue("INS-PROV-007", field="package_id",
                                                 expected=expected_id, actual=manifest.get("package_id")))
    if archive_name is not None and expected_id is not None and not archive_name.startswith(expected_id):
        fail("UPD-PROV-006", ProvenanceIssue("INS-PROV-017", field="archive_name",
                                             expected=expected_id, actual=archive_name))

    # UPD-PROV-007: platform target.
    if platform is not None and target.get("os") != platform:
        fail("UPD-PROV-007", ProvenanceIssue("INS-PROV-013", field="target.os",
                                             expected=platform, actual=target.get("os")))
    if architecture is not None and target.get("architecture") != architecture:
        fail("UPD-PROV-007", ProvenanceIssue("INS-PROV-013", field="target.architecture",
                                             expected=architecture, actual=target.get("architecture")))

    # UPD-PROV-008: validation profile.
    profile_path = package_root / str(profile.get("profile_path", "payload/metadata/validation_profile.json"))
    recorded_profile_hash = profile.get("profile_sha256")
    if not profile_path.is_file():
        fail("UPD-PROV-008", ProvenanceIssue("INS-PROV-008", field="validation_profile.profile_path",
                                             message="Packaged validation profile is missing."))
    elif not isinstance(recorded_profile_hash, str) or sha256_file(profile_path) != recorded_profile_hash:
        fail("UPD-PROV-008", ProvenanceIssue("INS-PROV-008", field="validation_profile.profile_sha256",
                                             expected=recorded_profile_hash,
                                             actual=sha256_file(profile_path) if profile_path.is_file() else None))
    if manifest_version is not None and profile.get("profile_version") != manifest_version:
        fail("UPD-PROV-008", ProvenanceIssue("INS-PROV-008", field="validation_profile.profile_version",
                                             expected=manifest_version, actual=profile.get("profile_version")))

    # UPD-PROV-009: builder compatibility.
    builder_version = str(builder.get("version", ""))
    major = builder_version.split(".", 1)[0]
    if (builder.get("name") not in SUPPORTED_BUILDER_NAMES
            or not major.isdigit() or int(major) not in SUPPORTED_BUILDER_MAJOR_VERSIONS):
        fail("UPD-PROV-009", ProvenanceIssue("INS-PROV-009", field="builder.version",
                                             actual=f"{builder.get('name')} {builder_version}"))
    if not isinstance(builder.get("implementation_sha256"), str) or not SHA256_PATTERN.match(str(builder.get("implementation_sha256"))):
        fail("UPD-PROV-009", ProvenanceIssue("INS-PROV-010", field="builder.implementation_sha256",
                                             actual=builder.get("implementation_sha256")))

    # UPD-PROV-010 / UPD-PROV-011: payload and file integrity.
    files = integrity.get("files")
    if integrity.get("hash_algorithm") != "sha256" or not isinstance(files, list) or not files:
        fail("UPD-PROV-010", ProvenanceIssue("INS-PROV-020", field="integrity",
                                             message="Integrity inventory is missing or malformed."))
    else:
        recorded_paths: set[str] = set()
        recomputed: list[dict[str, Any]] = []
        for item in files:
            path_value = item.get("path") if isinstance(item, dict) else None
            digest = item.get("sha256") if isinstance(item, dict) else None
            if (not isinstance(path_value, str) or not path_value.startswith("payload/")
                    or path_value in recorded_paths or not isinstance(digest, str) or not SHA256_PATTERN.match(digest)):
                fail("UPD-PROV-011", ProvenanceIssue("INS-PROV-012", field="integrity.files", actual=path_value,
                                                     message="Integrity inventory entry is unsafe or malformed."))
                continue
            recorded_paths.add(path_value)
            recomputed.append({"path": path_value, "sha256": digest})
            actual_path = package_root / path_value
            if not actual_path.is_file():
                fail("UPD-PROV-011", ProvenanceIssue("INS-PROV-012", field=path_value,
                                                     message="Manifest entry has no payload file."))
            elif sha256_file(actual_path) != digest:
                fail("UPD-PROV-011", ProvenanceIssue("INS-PROV-012", field=path_value, expected=digest,
                                                     actual=sha256_file(actual_path)))
        payload_root = package_root / "payload"
        if payload_root.is_dir():
            actual_paths = {f"payload/{path.relative_to(payload_root).as_posix()}"
                            for path in payload_root.rglob("*") if path.is_file()}
            for extra in sorted(actual_paths - recorded_paths):
                fail("UPD-PROV-011", ProvenanceIssue("INS-PROV-012", field=extra,
                                                     message="Payload file is not recorded in the manifest."))
        recorded_payload_hash = integrity.get("payload_sha256")
        if recorded_payload_hash != payload_hash(recomputed):
            fail("UPD-PROV-010", ProvenanceIssue("INS-PROV-011", expected=recorded_payload_hash,
                                                 actual=payload_hash(recomputed)))

    # Freshness classification (spec section 13/15).
    stale = False
    if expected_commit is not None and sha is not None and sha != expected_commit:
        report.issues.append(ProvenanceIssue("INS-PROV-005", field="source_commit.sha",
                                             expected=expected_commit, actual=sha))
        report.issues.append(ProvenanceIssue("INS-PROV-014", message="Package is classified as stale.",
                                             expected=expected_commit, actual=sha))
        report.checks["UPD-PROV-013"] = "fail"
        stale = True

    classification_codes = {"INS-PROV-005", "INS-PROV-014", "INS-PROV-015"}
    invalid = any(issue.severity == "fatal" and issue.code not in classification_codes for issue in report.issues)
    if invalid:
        report.freshness = FRESHNESS_INVALID
    elif stale:
        report.freshness = FRESHNESS_STALE
    elif is_development or dirty:
        report.freshness = FRESHNESS_DEVELOPMENT
    elif expected_commit is not None:
        report.freshness = FRESHNESS_FRESH
    else:
        report.freshness = FRESHNESS_UNKNOWN
    return report
