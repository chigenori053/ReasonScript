"""Platform-independent update state machine and package validation."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from .package_provenance import manifest_paths
from .package_validator import (
    FRESHNESS_DEVELOPMENT,
    FRESHNESS_STALE,
    PROVENANCE_DIAGNOSTICS,
    ProvenanceReport,
    validate_package_provenance,
)
from .platform import PlatformAdapter, current_adapter

REPORT_SCHEMA = "reasonscript-update-report/1.0"
TRANSACTION_SCHEMA = "reasonscript-update-transaction/1.1"
MANIFEST_SCHEMA = "reasonscript-install-manifest/1.1"
CHECKSUM_SCHEMA = "reasonscript-package-checksums/1.0"
STATE_SCHEMA = "reasonscript-install-state/1.1"
FILES_SCHEMA = "reasonscript-installed-files/1.1"
HISTORY_SCHEMA = "reasonscript-update-history/1.0"

DIAGNOSTICS = {
    "INS-UPD-001": (3, "Existing installation not found."),
    "INS-UPD-002": (0, "Package version is not newer."),
    "INS-UPD-003": (4, "Package platform does not match the installed platform."),
    "INS-UPD-004": (4, "Package architecture does not match the installed architecture."),
    "INS-UPD-005": (5, "Package checksum verification failed."),
    "INS-UPD-006": (6, "Installation root is not writable."),
    "INS-UPD-007": (1, "Insufficient disk space."),
    "INS-UPD-008": (1, "Staging validation failed."),
    "INS-UPD-009": (7, "Activation failed."),
    "INS-UPD-010": (8, "Post-install validation failed."),
    "INS-UPD-011": (9, "Rollback completed."),
    "INS-UPD-012": (10, "Rollback failed."),
    "INS-UPD-013": (1, "Managed installed file was locally modified."),
    "INS-UPD-014": (4, "Unsupported update path."),
    "INS-UPD-015": (1, "Install state is invalid."),
    "INS-UPD-016": (4, "Component version mismatch."),
    "INS-UPD-017": (5, "Package manifest is invalid."),
    "INS-UPD-018": (7, "A running process prevents activation."),
    "INS-UPD-019": (7, "Launcher update failed."),
    "INS-UPD-020": (1, "Configuration migration failed."),
}

_PROVENANCE_EXIT_CODES = {
    "INS-PROV-001": 5, "INS-PROV-002": 5, "INS-PROV-003": 5, "INS-PROV-004": 5,
    "INS-PROV-005": 4, "INS-PROV-006": 4, "INS-PROV-007": 4, "INS-PROV-008": 4,
    "INS-PROV-009": 4, "INS-PROV-010": 5, "INS-PROV-011": 5, "INS-PROV-012": 5,
    "INS-PROV-013": 4, "INS-PROV-014": 4, "INS-PROV-015": 4, "INS-PROV-016": 4,
    "INS-PROV-017": 4, "INS-PROV-018": 5, "INS-PROV-019": 5, "INS-PROV-020": 4,
}
DIAGNOSTICS.update({code: (_PROVENANCE_EXIT_CODES[code], message)
                    for code, message in PROVENANCE_DIAGNOSTICS.items()})


class UpdateError(Exception):
    def __init__(self, code: str, *, phase: str, detail: str | None = None, **context: Any):
        exit_code, message = DIAGNOSTICS[code]
        super().__init__(detail or message)
        self.code = code
        self.exit_code = exit_code
        self.phase = phase
        self.message = detail or message
        self.context = context

    def diagnostic(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": "fatal" if self.code != "INS-UPD-011" else "warning",
            "category": "installation_update",
            "message": self.message,
            "phase": self.phase,
            **self.context,
        }


def _version_key(value: str) -> tuple[tuple[int, ...], int, str]:
    match = re.fullmatch(r"(\d+(?:\.\d+)*)(?:[-+]([0-9A-Za-z.-]+))?", value)
    if not match:
        raise ValueError(f"invalid version: {value}")
    numbers = tuple(int(part) for part in match.group(1).split("."))
    suffix = match.group(2)
    return numbers, 1 if suffix is None else 0, suffix or ""


def compare_versions(left: str, right: str) -> int:
    a, b = _version_key(left), _version_key(right)
    width = max(len(a[0]), len(b[0]))
    a_key = (a[0] + (0,) * (width - len(a[0])), a[1], a[2])
    b_key = (b[0] + (0,) * (width - len(b[0])), b[1], b[2])
    return (a_key > b_key) - (a_key < b_key)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_member(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return bool(normalized) and not path.is_absolute() and ".." not in path.parts and not re.match(r"^[A-Za-z]:", normalized)


@dataclass(frozen=True)
class Package:
    root: Path
    source: Path
    manifest: dict[str, Any]
    checksums: dict[str, Any]
    temporary: tempfile.TemporaryDirectory[str] | None = None

    def close(self) -> None:
        if self.temporary is not None:
            self.temporary.cleanup()


class UpdateEngine:
    def __init__(self, root: Path | None = None, adapter: PlatformAdapter | None = None,
                 validator: Callable[[Path], dict[str, str]] | None = None,
                 *, expected_commit: str | None = None, allow_development_package: bool = False,
                 allow_legacy_package: bool = False):
        self.adapter = adapter or current_adapter()
        self.root = (root or self.adapter.default_install_root()).expanduser().resolve()
        self.validator = validator or self._post_install_validation
        self.expected_commit = expected_commit
        self.allow_development_package = allow_development_package
        self.allow_legacy_package = allow_legacy_package
        self._provenance_report: ProvenanceReport | None = None
        self._validation_details: dict[str, Any] = {}

    @property
    def metadata(self) -> Path:
        return self.root / "metadata"

    def _read_json(self, path: Path, code: str = "INS-UPD-015") -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("document must be an object")
            return data
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise UpdateError(code, phase="validating_current", detail=f"Invalid {path.name}: {exc}") from exc

    def discover(self) -> dict[str, Any]:
        if not self.root.is_dir() or not self.adapter.launcher_path(self.root).is_file():
            raise UpdateError("INS-UPD-001", phase="detecting", install_root=str(self.root))
        state_path = self.metadata / "install_state.json"
        if not state_path.is_file():
            self._migrate_v1()
        state = self._read_json(state_path)
        current = self._read_json(self.metadata / "current.json")
        inventory = self._read_json(self.metadata / "installed_files.json")
        version = current.get("active_version")
        valid_state = (
            state.get("schema_version") == STATE_SCHEMA
            and state.get("installed_version") == version
            and state.get("runtime_version") == version
            and state.get("install_foundation_version") == "1.1"
            and state.get("platform") == self.adapter.name
            and state.get("architecture") == self.adapter.architecture
            and state.get("status") == "healthy"
            and current.get("schema_version") == "reasonscript-current-installation/1.0"
            and current.get("activation_status") == "active"
            and inventory.get("schema_version") == FILES_SCHEMA
            and inventory.get("version") == version
            and isinstance(inventory.get("files"), list)
        )
        if not valid_state:
            raise UpdateError("INS-UPD-015", phase="validating_current", detail="Install state and active version disagree.")
        if not (self.root / "versions" / str(version)).is_dir():
            raise UpdateError("INS-UPD-015", phase="validating_current", detail="Active version directory is missing.")
        history = self._read_json(self.metadata / "update_history.json")
        if history.get("schema_version") != HISTORY_SCHEMA or not isinstance(history.get("updates"), list):
            raise UpdateError("INS-UPD-015", phase="validating_current", detail="Update history is invalid.")
        return {"state": state, "current": current, "inventory": inventory, "history": history}

    def _migrate_v1(self) -> None:
        legacy_path = self.root / "install_manifest.json"
        if not legacy_path.is_file():
            raise UpdateError("INS-UPD-001", phase="detecting", install_root=str(self.root))
        legacy = self._read_json(legacy_path)
        version = legacy.get("reason_version")
        if legacy.get("schema_version") != "reasonscript-install-manifest/1.0" or not isinstance(version, str):
            raise UpdateError("INS-UPD-015", phase="validating_current", detail="Unsupported legacy install manifest.")
        self.adapter.prepare_install_root(self.root)
        now = legacy.get("installed_at") or _timestamp()
        platform_data = legacy.get("platform", {})
        legacy_platform = {"darwin": "macos", "win32": "windows"}.get(
            str(platform_data.get("os", "")).lower(), str(platform_data.get("os", "")).lower()
        )
        legacy_architecture = {"aarch64": "arm64", "amd64": "x86_64", "x64": "x86_64"}.get(
            str(platform_data.get("architecture", "")).lower(), str(platform_data.get("architecture", "")).lower()
        )
        if legacy_platform and legacy_platform != self.adapter.name:
            raise UpdateError("INS-UPD-015", phase="validating_current", detail="Legacy installation platform is incompatible.")
        if legacy_architecture and legacy_architecture != self.adapter.architecture:
            raise UpdateError("INS-UPD-015", phase="validating_current", detail="Legacy installation architecture is incompatible.")
        self.adapter.atomic_json_write(self.metadata / "install_state.json", {
            "schema_version": STATE_SCHEMA, "installed_version": version,
            "runtime_version": legacy.get("runtime_version", version), "install_foundation_version": "1.1",
            "platform": self.adapter.name, "architecture": self.adapter.architecture,
            "install_root": str(self.root), "installed_at": now, "updated_at": now,
            "update_count": 0, "status": "healthy",
        })
        self.adapter.atomic_json_write(self.metadata / "current.json", {
            "schema_version": "reasonscript-current-installation/1.0", "active_version": version,
            "previous_version": None, "activation_status": "active",
        })
        files = [{"path": item["path"], "sha256": item["sha256"], "managed": True,
                  "component": item.get("component", "legacy")}
                 for item in legacy.get("files", []) if isinstance(item, dict) and "path" in item and "sha256" in item]
        self.adapter.atomic_json_write(self.metadata / "installed_files.json", {
            "schema_version": FILES_SCHEMA, "version": version, "files": files,
        })
        self.adapter.atomic_json_write(self.metadata / "update_history.json", {
            "schema_version": HISTORY_SCHEMA, "updates": [],
        })
        shutil.copy2(legacy_path, self.metadata / "install_manifest.json")

    def _validate_inventory(self, inventory: dict[str, Any], force: bool) -> list[str]:
        modified = []
        for item in inventory.get("files", []):
            if not item.get("managed", True):
                continue
            path = self.root / item.get("path", "")
            if not path.is_file() or sha256(path) != item.get("sha256"):
                modified.append(item.get("path", ""))
        if modified and not force:
            raise UpdateError("INS-UPD-013", phase="validating_current", modified_files=sorted(modified))
        return sorted(modified)

    def open_package(self, source: Path) -> Package:
        source = source.expanduser().resolve()
        temporary: tempfile.TemporaryDirectory[str] | None = None
        if source.is_dir():
            root = source
        elif source.is_file():
            temporary = tempfile.TemporaryDirectory(prefix="reason-update-package-")
            root = Path(temporary.name)
            try:
                if zipfile.is_zipfile(source):
                    with zipfile.ZipFile(source) as archive:
                        for item in archive.infolist():
                            if not _safe_member(item.filename) or ((item.external_attr >> 16) & 0o170000) == 0o120000:
                                raise UpdateError("INS-UPD-017", phase="validating_package", detail="Unsafe package path or symlink.")
                        archive.extractall(root)
                elif tarfile.is_tarfile(source):
                    with tarfile.open(source) as archive:
                        for item in archive.getmembers():
                            if not _safe_member(item.name) or item.issym() or item.islnk() or not (item.isfile() or item.isdir()):
                                raise UpdateError("INS-UPD-017", phase="validating_package", detail="Unsafe package path or link.")
                        archive.extractall(root)
                else:
                    raise UpdateError("INS-UPD-017", phase="validating_package", detail="Unsupported package format.")
            except Exception:
                temporary.cleanup()
                raise
        else:
            raise UpdateError("INS-UPD-017", phase="validating_package", detail="Package does not exist.")
        # Accept an archive containing one top-level package directory.
        if not (root / "manifest.json").is_file():
            children = [path for path in root.iterdir() if path.is_dir()]
            if len(children) == 1 and (children[0] / "manifest.json").is_file():
                root = children[0]
        try:
            manifest = self._read_package_json(root / "manifest.json")
            checksums = self._read_package_json(root / "checksums.json")
            self._validate_package_documents(root, manifest, checksums)
            return Package(root, source, manifest, checksums, temporary)
        except Exception:
            if temporary is not None:
                temporary.cleanup()
            raise

    def _read_package_json(self, path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("document must be an object")
            return data
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise UpdateError("INS-UPD-017", phase="validating_package", detail=f"Invalid {path.name}: {exc}") from exc

    def _validate_package_documents(self, root: Path, manifest: dict[str, Any], checksums: dict[str, Any]) -> None:
        required = {"schema_version", "package_version", "runtime_version", "install_foundation_version",
                    "platform", "architecture", "package_type", "components"}
        if (manifest.get("schema_version") != MANIFEST_SCHEMA or not required <= manifest.keys()
                or manifest.get("install_foundation_version") != "1.1"
                or manifest.get("package_type") != "update_and_install"):
            raise UpdateError("INS-UPD-017", phase="validating_package", detail="Package manifest schema or fields are invalid.")
        if checksums.get("schema_version") != CHECKSUM_SCHEMA or checksums.get("algorithm") != "sha256":
            raise UpdateError("INS-UPD-017", phase="validating_package", detail="Checksum manifest schema is invalid.")
        entries = checksums.get("files")
        if not isinstance(entries, list) or not entries:
            raise UpdateError("INS-UPD-017", phase="validating_package", detail="Checksum inventory is empty.")
        paths: set[str] = set()
        for item in entries:
            relative = item.get("path") if isinstance(item, dict) else None
            if not isinstance(relative, str) or not _safe_member(relative) or relative in paths or not relative.startswith("payload/"):
                raise UpdateError("INS-UPD-017", phase="validating_package", detail="Checksum inventory contains an unsafe or duplicate path.")
            paths.add(relative)
            target = root / relative
            if not target.is_file() or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))) or sha256(target) != item["sha256"]:
                raise UpdateError("INS-UPD-005", phase="validating_package", package_file=relative)
        actual = {path.relative_to(root).as_posix() for path in (root / "payload").rglob("*") if path.is_file()}
        if actual != paths:
            raise UpdateError("INS-UPD-017", phase="validating_package", detail="Payload and checksum inventories differ.")
        components = manifest.get("components", [])
        component_names = [item.get("name") for item in components if isinstance(item, dict)]
        component_versions = {item.get("version") for item in components if isinstance(item, dict)}
        required_components = {"cli", "runtime-core", "toolchain", "schemas", "standard-library"}
        if (len(component_names) != len(set(component_names)) or not required_components <= set(component_names)
                or manifest.get("package_version") not in component_versions
                or manifest.get("runtime_version") != manifest.get("package_version")):
            raise UpdateError("INS-UPD-016", phase="validating_package")

    def plan(self, package: Package, force: bool = False) -> dict[str, Any]:
        installation = self.discover()
        state, inventory = installation["state"], installation["inventory"]
        modified = self._validate_inventory(inventory, force)
        installed_version = state["installed_version"]
        package_version = package.manifest["package_version"]
        comparison = compare_versions(package_version, installed_version)
        if comparison <= 0:
            return {
                "schema_version": REPORT_SCHEMA,
                "status": "already_up_to_date" if comparison == 0 else "downgrade_rejected",
                "installed_version": installed_version, "package_version": package_version,
                "compatible": comparison == 0, "action": "none",
                "diagnostics": [] if comparison == 0 else [UpdateError("INS-UPD-002", phase="planning").diagnostic()],
            }
        self._compatibility(state, package.manifest)
        minimum = package.manifest.get("minimum_previous_version")
        maximum = package.manifest.get("maximum_previous_version")
        if (minimum and compare_versions(installed_version, minimum) < 0) or (maximum and compare_versions(installed_version, maximum) > 0):
            raise UpdateError("INS-UPD-014", phase="planning")
        provenance = self._provenance_gate(package, expected_version=package_version)
        current_files = {item["path"].split(f"versions/{installed_version}/", 1)[-1]: item["sha256"] for item in inventory.get("files", [])}
        package_files = {item["path"].split("payload/", 1)[-1]: item["sha256"] for item in package.checksums["files"]}
        added = sorted(package_files.keys() - current_files.keys())
        changed = sorted(path for path in package_files.keys() & current_files.keys() if package_files[path] != current_files[path])
        removed = sorted(current_files.keys() - package_files.keys())
        return {
            "schema_version": REPORT_SCHEMA, "status": "update_available",
            "installed_version": installed_version, "package_version": package_version,
            "platform": state["platform"], "architecture": state["architecture"], "compatible": True, "action": "update",
            "plan": {"from_version": installed_version, "to_version": package_version,
                     "added_files": added, "changed_files": changed, "removed_managed_files": removed,
                     "preserved_files": ["config", "projects", "artifacts", "cache"],
                     "migration_actions": [], "estimated_disk_usage": sum((package.root / item["path"]).stat().st_size for item in package.checksums["files"]),
                     "rollback_target": installed_version, "activation_method": "atomic_current_metadata_switch",
                     "modified_managed_files": modified},
            "package_provenance": provenance["package"],
            "freshness": provenance["freshness"],
            "diagnostics": [],
        }

    def _provenance_gate(self, package: Package, *, expected_version: str) -> dict[str, Any]:
        """Validate provenance before any payload is staged or activated (UPD-PROV-001..014)."""
        archive_name = package.source.name if package.source.is_file() else None
        report = validate_package_provenance(
            package.root,
            platform=self.adapter.name,
            architecture=self.adapter.architecture,
            expected_version=expected_version,
            expected_commit=self.expected_commit,
            archive_name=archive_name,
            allow_development=self.allow_development_package,
        )
        self._provenance_report = report
        if report.manifest is None:
            if self.allow_legacy_package:
                return {"package": None, "freshness": {"status": "legacy"}}
            raise UpdateError("INS-PROV-020", phase="validating_provenance",
                              detail="Package has no provenance manifest; legacy packages are rejected.",
                              package_path=str(package.source))
        if not report.valid or report.freshness == FRESHNESS_STALE or (
                report.freshness == FRESHNESS_DEVELOPMENT and not self.allow_development_package):
            issue = next((item for item in report.issues if item.severity == "fatal"), None)
            code = issue.code if issue else "INS-PROV-018"
            context = {key: value for key, value in (issue.to_dict() if issue else {}).items()
                       if key in {"field", "expected", "actual"}}
            raise UpdateError(code, phase="validating_provenance",
                              detail=issue.message or PROVENANCE_DIAGNOSTICS.get(code) if issue else None,
                              package_path=str(package.source),
                              freshness=report.freshness, **context)
        return {"package": report.summary(), "freshness": {"status": report.freshness}}

    def _compatibility(self, state: dict[str, Any], manifest: dict[str, Any]) -> None:
        if manifest["platform"] != state["platform"]:
            raise UpdateError("INS-UPD-003", phase="validating_package", installed_platform=state["platform"], package_platform=manifest["platform"])
        if manifest["architecture"] != state["architecture"]:
            raise UpdateError("INS-UPD-004", phase="validating_package", installed_architecture=state["architecture"], package_architecture=manifest["architecture"])

    def check(self, source: Path, force: bool = False) -> dict[str, Any]:
        package = self.open_package(source)
        try:
            return self.plan(package, force)
        except UpdateError as exc:
            if exc.phase != "validating_provenance":
                raise
            report = self._provenance_report
            return {
                "schema_version": REPORT_SCHEMA, "status": "package_rejected", "action": "none",
                "package_provenance": report.summary() if report and report.manifest else None,
                "freshness": {"status": report.freshness if report and report.manifest else "unknown"},
                "diagnostics": [exc.diagnostic()],
            }
        finally:
            package.close()

    def update(self, source: Path, force: bool = False) -> tuple[dict[str, Any], int]:
        package = self.open_package(source)
        activated = False
        previous = None
        started = _timestamp()
        transaction_id = f"txn-{started.replace(':', '').replace('-', '')}-{os.getpid()}"
        try:
            plan = self.plan(package, force)
            if plan["status"] != "update_available":
                return plan, 0 if plan["status"] == "already_up_to_date" else 4
            previous, version = plan["installed_version"], plan["package_version"]
            if not self.adapter.validate_permissions(self.root):
                raise UpdateError("INS-UPD-006", phase="planning")
            required = plan["plan"]["estimated_disk_usage"] * 2
            if shutil.disk_usage(self.root).free < required:
                raise UpdateError("INS-UPD-007", phase="planning")
            staging = self.root / "staging" / version
            self.adapter.prepare_staging(staging)
            shutil.copytree(package.root / "payload", staging, dirs_exist_ok=True)
            self._validate_staging(staging, package)
            final = self.root / "versions" / version
            if final.exists():
                shutil.rmtree(final)
            staging.replace(final)
            if self.adapter.detect_running_process_conflict():
                raise UpdateError("INS-UPD-018", phase="activating")
            try:
                self.adapter.activate_version(self.root, version, previous)
                activated = True
            except OSError as exc:
                raise UpdateError("INS-UPD-009", phase="activating", detail=str(exc)) from exc
            self._validation_details = {}
            validation = self.validator(final)
            if any(value != "passed" for value in validation.values()):
                raise UpdateError(
                    "INS-UPD-010",
                    phase="validating_active",
                    validation=validation,
                    validation_details=dict(self._validation_details),
                )
            self._complete(package, plan, validation, started, transaction_id)
            self._write_transaction(transaction_id, previous, version, "activated", started)
            return self._completed_report(package, plan, validation), 0
        except UpdateError as exc:
            if activated and previous:
                self._write_transaction(transaction_id, previous, package.manifest.get("package_version"),
                                        "rolled_back", started, error=exc)
                return self._automatic_rollback(previous, package.manifest.get("package_version"), exc, started)
            status = "rejected" if exc.phase == "validating_provenance" else "failed"
            self._write_transaction(transaction_id, previous, package.manifest.get("package_version"),
                                    status, started, error=exc)
            return self._failure_report(exc, package.source), exc.exit_code
        finally:
            shutil.rmtree(self.root / "staging" / str(package.manifest.get("package_version", "unknown")), ignore_errors=True)
            package.close()

    def _validate_staging(self, staging: Path, package: Package) -> None:
        for item in package.checksums["files"]:
            relative = item["path"].split("payload/", 1)[-1]
            path = staging / relative
            if not path.is_file() or sha256(path) != item["sha256"]:
                raise UpdateError("INS-UPD-008", phase="validating_staging", staged_file=relative)
        required = {"reason", "VERSION", "bin/reason-runtime", "runtime", "toolchain", "schemas", "standard_library", "metadata"}
        if not all((staging / item).exists() for item in required):
            raise UpdateError("INS-UPD-008", phase="validating_staging", detail="Required release components are missing.")
        if (staging / "VERSION").read_text(encoding="utf-8").strip() != package.manifest["package_version"]:
            raise UpdateError("INS-UPD-016", phase="validating_staging")
        self._restore_executable_permissions(staging)
        self._validate_native_staging(staging, package)

    def _restore_executable_permissions(self, staging: Path) -> None:
        """Restore executable intent lost by portable ZIP extraction."""
        report = self._provenance_report
        records = (
            report.manifest.get("integrity", {}).get("files", [])
            if report and report.manifest else []
        )
        executable_paths = [
            item.get("path") for item in records
            if isinstance(item, dict) and item.get("executable") is True
        ]
        if not executable_paths:
            executable_paths = ["payload/reason", "payload/bin/reason-runtime"]
        staging_root = staging.resolve()
        for packaged_path in executable_paths:
            if not isinstance(packaged_path, str) or not packaged_path.startswith("payload/"):
                raise UpdateError(
                    "INS-UPD-008",
                    phase="validating_staging",
                    detail="Executable provenance contains an unsafe payload path.",
                    staged_file=packaged_path,
                )
            relative = packaged_path.removeprefix("payload/")
            if not relative or not _safe_member(relative):
                raise UpdateError(
                    "INS-UPD-008",
                    phase="validating_staging",
                    detail="Executable provenance contains an unsafe payload path.",
                    staged_file=packaged_path,
                )
            target = (staging / relative).resolve()
            if staging_root not in target.parents or not target.is_file():
                raise UpdateError(
                    "INS-UPD-008",
                    phase="validating_staging",
                    detail="A provenance-declared executable is missing from staging.",
                    staged_file=relative,
                )
            try:
                self.adapter.ensure_executable(target)
            except OSError as exc:
                raise UpdateError(
                    "INS-UPD-008",
                    phase="validating_staging",
                    detail=f"Could not restore executable permission: {exc}",
                    staged_file=relative,
                ) from exc

    def _validate_native_staging(self, staging: Path, package: Package) -> None:
        components = {
            item.get("name") for item in package.manifest.get("components", [])
            if isinstance(item, dict)
        }
        suffix = ".exe" if self.adapter.name == "windows" else ""
        probes = []
        if "vision-runtime-v0.1" in components:
            probes.append((
                "vision-runtime-v0.1",
                staging / "bin" / f"reason-vision{suffix}",
                "profile",
                "reasonscript-vision-runtime/0.1",
            ))
        if "semantic-visualization-runtime-v0.1" in components:
            probes.append((
                "semantic-visualization-runtime-v0.1",
                staging / "bin" / f"reason-visualization{suffix}",
                "profile",
                "reasonscript-semantic-visualization-runtime/0.1",
            ))
        if "reasonunit-runtime-v1.0" in components:
            probes.append((
                "reasonunit-runtime-v1.0",
                staging / "bin" / f"reasonunit-runtime-native{suffix}",
                "native_execution_provenance",
                "reasonscript-reasonunit-native-runtime/1.0",
            ))
        for component, binary, provenance_field, expected_provenance in probes:
            if not binary.is_file() or (self.adapter.name != "windows" and not os.access(binary, os.X_OK)):
                raise UpdateError(
                    "INS-UPD-008",
                    phase="validating_staging",
                    detail=f"{component} executable is missing or not executable.",
                    component=component,
                    staged_file=str(binary.relative_to(staging)),
                )
            try:
                proc = subprocess.run(
                    [str(binary), "verify-native"],
                    cwd=tempfile.gettempdir(),
                    text=True,
                    capture_output=True,
                )
                payload = json.loads(proc.stdout)
            except (OSError, json.JSONDecodeError) as exc:
                raise UpdateError(
                    "INS-UPD-008",
                    phase="validating_staging",
                    detail=f"{component} native preflight could not run: {exc}",
                    component=component,
                    staged_file=str(binary.relative_to(staging)),
                ) from exc
            if (
                proc.returncode != 0
                or payload.get("ok") is not True
                or payload.get("unsafe_blocks") != 0
                or payload.get(provenance_field) != expected_provenance
            ):
                raise UpdateError(
                    "INS-UPD-008",
                    phase="validating_staging",
                    detail=f"{component} native preflight failed.",
                    component=component,
                    staged_file=str(binary.relative_to(staging)),
                    exit_status=proc.returncode,
                    stderr=proc.stderr.strip()[-2000:],
                )

    def _post_install_validation(self, root: Path) -> dict[str, str]:
        cli = root / "reason"
        expected_version = (root / "VERSION").read_text(encoding="utf-8").strip()
        env = os.environ.copy()
        env.update({"REASONSCRIPT_HOME": str(self.root), "PYTHONPATH": ""})
        commands = {
            "version": [sys.executable, str(cli), "--version", "--json"],
            "doctor": [sys.executable, str(cli), "doctor", "--json"],
            "install_info": [sys.executable, str(cli), "install-info", "--json"],
            "install_validate": [sys.executable, str(cli), "install-validate", "--json"],
        }
        result = {}
        self._validation_details = {}
        for name, command in commands.items():
            try:
                proc = subprocess.run(command, cwd=tempfile.gettempdir(), env=env, text=True, capture_output=True)
            except OSError as exc:
                result[name] = "failed"
                self._validation_details[name] = {"error": str(exc)}
                continue
            try:
                payload = json.loads(proc.stdout)
            except json.JSONDecodeError:
                payload = {}
            code_ok = proc.returncode in ({0, 1} if name == "doctor" else {0})
            version_ok = payload.get("reason_version", expected_version) == expected_version
            status_ok = payload.get("status") not in {"fail", "failed", "unusable"}
            result[name] = "passed" if code_ok and version_ok and status_ok else "failed"
            checks = payload.get("checks", [])
            if not isinstance(checks, list):
                checks = []
            failed_checks = [
                item.get("id") or item.get("check")
                for item in checks
                if isinstance(item, dict) and item.get("status") in {"fail", "failed"}
            ]
            diagnostics = payload.get("diagnostics", [])
            if not isinstance(diagnostics, list):
                diagnostics = []
            self._validation_details[name] = {
                "exit_status": proc.returncode,
                "reported_status": payload.get("status"),
                "reason_version": payload.get("reason_version"),
                "failed_checks": [item for item in failed_checks if item],
                "diagnostic_codes": [
                    item.get("code") for item in diagnostics
                    if isinstance(item, dict) and item.get("code")
                ],
                "stdout": proc.stdout.strip()[-2000:] if not payload else "",
                "stderr": proc.stderr.strip()[-2000:],
            }
        # Run Phase 1R and project probes in an isolated user-owned temporary workspace.
        with tempfile.TemporaryDirectory(prefix="reason-update-smoke-") as directory:
            work = Path(directory)
            fixtures = work / "tests/fixtures"
            shutil.copytree(root / "canonical_fixtures/phase1r", fixtures)
            scalar_source = work / "scalar_smoke.rsn"
            shutil.copy2(root / "examples/scalar_arithmetic.rsn", scalar_source)
            scalar = subprocess.run([sys.executable, str(cli), "run", str(scalar_source), "--json"],
                                    cwd=work, env=env, text=True, capture_output=True)
            phase1r = subprocess.run([sys.executable, str(cli), "phase1r-validate", "--json"], cwd=work, env=env, text=True, capture_output=True)
            project = subprocess.run([sys.executable, str(cli), "project-validate", str(fixtures / "standalone_project"), "--json"],
                                     cwd=work, env=env, text=True, capture_output=True)
        phase1r_ok = phase1r.returncode == 0
        result.update({"scalar_smoke": "passed" if scalar.returncode == 0 else "failed", "tensor_smoke": "passed" if phase1r_ok else "failed",
                       "loop_smoke": "passed" if phase1r_ok else "failed",
                       "project_validation": "passed" if project.returncode == 0 else "failed"})
        for name, proc in (
            ("scalar_smoke", scalar),
            ("tensor_smoke", phase1r),
            ("loop_smoke", phase1r),
            ("project_validation", project),
        ):
            self._validation_details[name] = {
                "exit_status": proc.returncode,
                "stderr": proc.stderr.strip()[-2000:],
            }
        return result

    def _write_transaction(self, transaction_id: str, from_version: str | None, to_version: str | None,
                           activation_status: str, started: str, error: UpdateError | None = None) -> None:
        """Persist a provenance-bearing transaction Artifact (spec section 18). Best effort."""
        try:
            report = self._provenance_report
            payload: dict[str, Any] = {
                "schema_version": TRANSACTION_SCHEMA, "transaction_id": transaction_id,
                "from_version": from_version, "to_version": to_version,
                "started_at": started, "completed_at": _timestamp(),
                "package_provenance": report.summary() if report and report.manifest else None,
                "freshness": {"status": report.freshness if report and report.manifest else "unknown"},
                "checks": ([{"code": code, "status": status} for code, status in sorted(report.checks.items())]
                           if report else []),
                "activation_status": activation_status,
                "diagnostics": [error.diagnostic()] if error else [],
            }
            self.adapter.atomic_json_write(self.metadata / "transactions" / f"{transaction_id}.json", payload)
        except OSError:
            pass

    def _persist_installed_provenance(self, package: Package, version: str, transaction_id: str, started: str) -> None:
        """Keep the package provenance manifest inside the installed version (spec section 17)."""
        manifest_path, sidecar_path = manifest_paths(package.root)
        if not manifest_path.is_file():
            return
        destination = self.root / "versions" / version / "metadata"
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest_path, destination / manifest_path.name)
        if sidecar_path.is_file():
            shutil.copy2(sidecar_path, destination / sidecar_path.name)
        report = self._provenance_report
        self.adapter.atomic_json_write(destination / "installation_record.json", {
            "schema_version": "reasonscript-installation-record/1.0",
            "installed_version": version, "installed_at": _timestamp(), "started_at": started,
            "transaction_id": transaction_id, "package_source": str(package.source),
            "freshness": {"status": report.freshness if report and report.manifest else "unknown"},
        })

    def _complete(self, package: Package, plan: dict[str, Any], validation: dict[str, str], started: str,
                  transaction_id: str = "") -> None:
        self._persist_installed_provenance(package, plan["package_version"], transaction_id, started)
        state = self._read_json(self.metadata / "install_state.json")
        now = _timestamp()
        backup = self.root / "backup" / plan["installed_version"] / "metadata"
        backup.mkdir(parents=True, exist_ok=True)
        for name in ("install_state.json", "installed_files.json", "install_manifest.json"):
            source = self.metadata / name
            if source.is_file():
                shutil.copy2(source, backup / name)
        if (self.root / "install_manifest.json").is_file():
            shutil.copy2(self.root / "install_manifest.json", backup / "legacy_install_manifest.json")
        state.update({"installed_version": plan["package_version"], "runtime_version": package.manifest["runtime_version"],
                      "install_foundation_version": "1.1", "updated_at": now,
                      "update_count": int(state.get("update_count", 0)) + 1, "status": "healthy"})
        inventory = {"schema_version": FILES_SCHEMA, "version": plan["package_version"], "files": [
            {"path": f"versions/{plan['package_version']}/{item['path'].split('payload/', 1)[-1]}",
             "sha256": item["sha256"], "managed": True, "component": _component_for(item["path"])}
            for item in sorted(package.checksums["files"], key=lambda value: value["path"])
        ]}
        history = self._read_json(self.metadata / "update_history.json")
        history.setdefault("updates", []).append({"from_version": plan["installed_version"], "to_version": plan["package_version"],
            "status": "success", "started_at": started, "completed_at": now, "rollback_performed": False})
        installed_manifest = dict(package.manifest)
        installed_manifest.update({"install_root": str(self.root), "reason_version": package.manifest["package_version"],
                                   "installed_at": state.get("installed_at"), "updated_at": now})
        self.adapter.atomic_json_write(self.metadata / "install_state.json", state)
        self.adapter.atomic_json_write(self.metadata / "installed_files.json", inventory)
        self.adapter.atomic_json_write(self.metadata / "update_history.json", history)
        self.adapter.atomic_json_write(self.metadata / "install_manifest.json", installed_manifest)
        # Compatibility manifest remains readable by install-info and uninstall.
        legacy = self._read_json(self.root / "install_manifest.json")
        existing_components = {item.get("id"): dict(item) for item in legacy.get("components", []) if item.get("id")}
        for component in package.manifest.get("components", []):
            name = component.get("name")
            previous_component = existing_components.get(name, {"id": name, "required": True, "status": "installed"})
            previous_component.update({"version": component.get("version"), "status": "installed"})
            existing_components[name] = previous_component
        legacy.update({"reason_version": plan["package_version"], "runtime_version": package.manifest["runtime_version"],
                       "files": inventory["files"], "components": [existing_components[name] for name in sorted(existing_components)]})
        self.adapter.atomic_json_write(self.root / "install_manifest.json", legacy)

    def rollback(self) -> tuple[dict[str, Any], int]:
        installation = self.discover()
        current = installation["current"]
        previous, active = current.get("previous_version"), current.get("active_version")
        if not previous or not (self.root / "versions" / previous).is_dir():
            error = UpdateError("INS-UPD-012", phase="rolling_back", detail="No previous version is available.")
            return self._failure_report(error, None), error.exit_code
        return self._automatic_rollback(previous, active, UpdateError("INS-UPD-011", phase="rolling_back"), _timestamp(), explicit=True)

    def _automatic_rollback(self, previous: str, attempted: str | None, cause: UpdateError, started: str,
                            explicit: bool = False) -> tuple[dict[str, Any], int]:
        try:
            self.adapter.restore_version(self.root, previous, attempted)
            self._validation_details = {}
            validation = self.validator(self.root / "versions" / previous)
            healthy = all(value == "passed" for value in validation.values())
            if not healthy:
                raise OSError("restored version validation failed")
            history = self._read_json(self.metadata / "update_history.json")
            history.setdefault("updates", []).append({"from_version": previous if explicit else previous,
                "to_version": attempted, "status": "rolled_back", "started_at": started,
                "completed_at": _timestamp(), "rollback_performed": True, "reason_code": cause.code})
            self.adapter.atomic_json_write(self.metadata / "update_history.json", history)
            backup = self.root / "backup" / previous / "metadata"
            if explicit and (backup / "install_state.json").is_file():
                for name in ("install_state.json", "installed_files.json", "install_manifest.json"):
                    if (backup / name).is_file():
                        shutil.copy2(backup / name, self.metadata / name)
                if (backup / "legacy_install_manifest.json").is_file():
                    shutil.copy2(backup / "legacy_install_manifest.json", self.root / "install_manifest.json")
            else:
                state = self._read_json(self.metadata / "install_state.json")
                state.update({"installed_version": previous, "runtime_version": previous, "updated_at": _timestamp(), "status": "healthy"})
                self.adapter.atomic_json_write(self.metadata / "install_state.json", state)
            report = {"schema_version": REPORT_SCHEMA, "status": "rolled_back", "attempted_version": attempted,
                      "restored_version": previous, "reason_code": cause.code, "previous_installation_healthy": True,
                      "post_install_validation": cause.context.get("validation"),
                      "validation_details": cause.context.get("validation_details"),
                      "rollback": {"performed": True, "status": "passed"}, "diagnostics": [
                          {**UpdateError("INS-UPD-011", phase="rolling_back").diagnostic(), "cause": cause.code}]}
            return report, 0 if explicit else 9
        except Exception as exc:
            error = UpdateError("INS-UPD-012", phase="rolling_back", detail=f"Rollback failed: {exc}",
                                recovery_hint=f"Run the launcher from {self.root / 'versions' / previous / 'reason'} directly.")
            return self._failure_report(error, None), error.exit_code

    def validate_active(self) -> tuple[dict[str, Any], int]:
        installation = self.discover()
        version = installation["current"]["active_version"]
        self._validation_details = {}
        validation = self.validator(self.root / "versions" / version)
        passed = all(value == "passed" for value in validation.values())
        return {"schema_version": REPORT_SCHEMA, "status": "validated" if passed else "validation_failed",
                "installed_version": version, "post_install_validation": validation,
                "validation_details": dict(self._validation_details), "diagnostics": []}, 0 if passed else 8

    def _completed_report(self, package: Package, plan: dict[str, Any], validation: dict[str, str]) -> dict[str, Any]:
        return {"schema_version": REPORT_SCHEMA, "status": "completed", "platform": self.adapter.name,
                "architecture": self.adapter.architecture, "install_root": str(self.root),
                "from_version": plan["installed_version"], "to_version": plan["package_version"],
                "package": {"path": str(package.source), "checksum_valid": True, "manifest_valid": True},
                "staging": {"status": "passed"}, "activation": {"status": "passed", "atomic": True},
                "preservation": {"config_preserved": True, "projects_untouched": True, "artifacts_untouched": True},
                "managed_file_overrides": plan["plan"]["modified_managed_files"],
                "post_install_validation": validation, "validation_details": dict(self._validation_details),
                "rollback": {"performed": False}, "diagnostics": []}

    def _failure_report(self, error: UpdateError, package: Path | None) -> dict[str, Any]:
        return {"schema_version": REPORT_SCHEMA, "status": "failed", "platform": self.adapter.name,
                "architecture": self.adapter.architecture, "install_root": str(self.root),
                "package": {"path": str(package)} if package else None, "diagnostics": [error.diagnostic()]}


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _component_for(path: str) -> str:
    parts = PurePosixPath(path).parts
    return parts[1] if len(parts) > 1 else "package"
