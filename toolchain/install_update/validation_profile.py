"""Release-local, read-only validation capability profiles."""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any

PROFILE_SCHEMA = "reasonscript-validation-profile/1.0"
DECLARATION_SCHEMA = "reasonscript-validation-profile-declaration/1.0"
PROFILE_SOURCES = {"release_metadata", "release_manifest", "legacy_fallback", "minimum_baseline", "test_fixture"}
CAPABILITY_STATUSES = {"available", "unavailable", "not_declared", "invalid", "unsupported"}
REQUIRED_LEVELS = {"required", "optional", "informational"}
STANDARD_BASELINE = {
    "version": "required",
    "doctor": "required",
    "install_info": "required",
    "install_validate": "required",
    "cli_entry_point": "required",
    "runtime_import": "required",
    "parser_import": "optional",
    "schema_inventory": "required",
    "standard_library": "required",
}
STANDARD_FEATURES = (
    "data_analysis_smoke",
    "loop_smoke",
    "phase1r_validate",
    "phase8_golden",
    "project_validate",
    "reasoning_runtime",
    "tensor_smoke",
    "update_validate",
    "visualization_smoke",
)
LEGACY_COMMANDS = {"--version", "doctor", "install-info", "install-validate"}
MINIMUM_BASELINE = {"version", "cli_entry_point", "runtime_import", "schema_inventory", "standard_library"}


class ValidationProfileResolutionError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ValidationProfileDiagnostic:
    code: str
    severity: str
    category: str = "validation_profile"
    message: str = ""
    capability_id: str | None = None
    reason_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class FixtureCapability:
    id: str
    relative_path: str | None
    declared: bool
    status: str
    path_type: str | None = None
    required: bool = False
    required_files: tuple[str, ...] = ()
    missing_files: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["required_files"] = list(self.required_files)
        value["missing_files"] = list(self.missing_files)
        return value


@dataclass(frozen=True)
class ComponentCapability:
    id: str
    relative_path: str | None
    required: bool
    declared: bool
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SchemaCapability:
    id: str
    relative_path: str | None
    required: bool
    declared: bool
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationCapability:
    id: str
    category: str
    required_level: str
    declared: bool
    status: str
    command: str | None = None
    command_available: bool = False
    required_fixtures: tuple[str, ...] = ()
    fixtures_available: bool = False
    required_components: tuple[str, ...] = ()
    components_available: bool = False
    required_schemas: tuple[str, ...] = ()
    schemas_available: bool = False
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in CAPABILITY_STATUSES or self.required_level not in REQUIRED_LEVELS:
            raise ValueError("invalid validation capability state")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key in ("required_fixtures", "required_components", "required_schemas", "reasons"):
            value[key] = list(value[key])
        return value


@dataclass(frozen=True)
class ValidationProfileSummary:
    baseline_total: int
    baseline_available: int
    baseline_unavailable: int
    features_total: int
    features_available: int
    features_unavailable: int
    features_not_declared: int
    fixtures_total: int
    fixtures_available: int
    required_capabilities_ready: bool
    optional_capabilities_ready: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationProfile:
    schema_version: str
    reason_version: str
    install_foundation_version: str
    runtime_version: str
    profile_source: str
    release_root: str
    baseline: Mapping[str, ValidationCapability]
    features: Mapping[str, ValidationCapability]
    fixtures: Mapping[str, FixtureCapability]
    components: Mapping[str, ComponentCapability]
    schemas: Mapping[str, SchemaCapability]
    summary: ValidationProfileSummary
    diagnostics: tuple[ValidationProfileDiagnostic, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.schema_version != PROFILE_SCHEMA or self.profile_source not in PROFILE_SOURCES:
            raise ValueError("invalid validation profile")
        for name in ("baseline", "features", "fixtures", "components", "schemas"):
            value = getattr(self, name)
            object.__setattr__(self, name, MappingProxyType(dict(sorted(value.items()))))
        object.__setattr__(self, "diagnostics", tuple(sorted(self.diagnostics, key=_diagnostic_key)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "reason_version": self.reason_version,
            "install_foundation_version": self.install_foundation_version,
            "runtime_version": self.runtime_version,
            "profile_source": self.profile_source,
            "release_root": self.release_root,
            "baseline": {key: value.to_dict() for key, value in self.baseline.items()},
            "features": {key: value.to_dict() for key, value in self.features.items()},
            "fixtures": {key: value.to_dict() for key, value in self.fixtures.items()},
            "components": {key: value.to_dict() for key, value in self.components.items()},
            "schemas": {key: value.to_dict() for key, value in self.schemas.items()},
            "summary": self.summary.to_dict(),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def resolve_validation_profile(
    release_root: Path,
    expected_version: str | None = None,
    platform: Any | None = None,
) -> ValidationProfile:
    del platform  # Reserved for platform-specific capability contracts.
    root = release_root.expanduser().resolve()
    if not root.is_dir():
        raise ValidationProfileResolutionError("VP-RES-001", "Release root does not exist.")
    version_file = root / "VERSION"
    if not version_file.is_file():
        raise ValidationProfileResolutionError("VP-RES-002", "Release VERSION cannot be read.")
    version = version_file.read_text(encoding="utf-8").strip()
    if expected_version is not None and version != expected_version:
        raise ValidationProfileResolutionError("VP-RES-003", "Expected version does not match the Release Unit.")
    declaration_path = root / "metadata/validation_profile.json"
    if declaration_path.is_file():
        declaration = _read_declaration(declaration_path)
        if declaration.get("reason_version") != version:
            raise ValidationProfileResolutionError("VP-RES-003", "Declaration version does not match the Release Unit.")
        return _resolve_declared(root, version, declaration)
    install_foundation, runtime_version = _release_versions(root, version)
    if version == "0.5.0" and install_foundation == "1.0":
        return _resolve_legacy(root, version, runtime_version)
    return _resolve_minimum(root, version, install_foundation, runtime_version)


def _read_declaration(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationProfileResolutionError("VP-DECL-001", "Validation profile declaration cannot be parsed.") from exc
    if not isinstance(value, dict) or value.get("schema_version") != DECLARATION_SCHEMA:
        raise ValidationProfileResolutionError("VP-DECL-002", "Unsupported validation profile declaration schema.")
    return value


def _release_versions(root: Path, version: str) -> tuple[str, str]:
    runtime = version
    release_manifest = root / "metadata/release_manifest.json"
    if release_manifest.is_file():
        try:
            runtime = str(json.loads(release_manifest.read_text(encoding="utf-8")).get("runtime_version", version))
        except (OSError, json.JSONDecodeError):
            pass
    candidates = [root / "install_manifest.json"]
    if root.parent.name == "versions":
        candidates.append(root.parent.parent / "install_manifest.json")
    for path in candidates:
        if path.is_file():
            try:
                manifest = json.loads(path.read_text(encoding="utf-8"))
                return str(manifest.get("install_foundation_version", "unknown")), runtime
            except (OSError, json.JSONDecodeError):
                continue
    return "unknown", runtime


def _resolve_legacy(root: Path, version: str, runtime_version: str) -> ValidationProfile:
    baseline: dict[str, ValidationCapability] = {}
    command_map = {
        "version": "--version",
        "doctor": "doctor",
        "install_info": "install-info",
        "install_validate": "install-validate",
    }
    for capability_id, required_level in STANDARD_BASELINE.items():
        declared = capability_id != "parser_import"
        baseline[capability_id] = _simple_capability(
            capability_id,
            "baseline",
            required_level,
            declared,
            command_map.get(capability_id),
            command_map.get(capability_id) in LEGACY_COMMANDS if command_map.get(capability_id) else declared,
        )
    features = {item: _simple_capability(item, "feature", "optional", False) for item in STANDARD_FEATURES}
    fixtures = {"phase1r": FixtureCapability("phase1r", None, False, "not_declared")}
    components = _legacy_components(root)
    diagnostics = (
        ValidationProfileDiagnostic(
            "VP-LEGACY-001",
            "info",
            message="A legacy validation profile was resolved for ReasonScript 0.5.0.",
            reason_version=version,
        ),
    )
    return _profile(version, "1.0", runtime_version, "legacy_fallback", baseline, features, fixtures, components, {}, diagnostics)


def _resolve_minimum(root: Path, version: str, install_foundation: str, runtime_version: str) -> ValidationProfile:
    resources = {
        "version": root / "VERSION",
        "cli_entry_point": root / "reason",
        "runtime_import": root / "runtime",
        "schema_inventory": root / "schemas",
        "standard_library": root / "standard_library",
    }
    baseline = {}
    for item, level in STANDARD_BASELINE.items():
        if item not in MINIMUM_BASELINE:
            baseline[item] = _simple_capability(item, "baseline", level, False)
            continue
        available = resources[item].exists()
        baseline[item] = ValidationCapability(
            item,
            "baseline",
            level,
            True,
            "available" if available else "unavailable",
            None,
            available,
            (),
            available,
            (),
            available,
            (),
            available,
            () if available else ("minimum_baseline_resource_missing",),
        )
    features = {item: _simple_capability(item, "feature", "optional", False) for item in STANDARD_FEATURES}
    diagnostics = (
        ValidationProfileDiagnostic("VP-RES-004", "warning", message="Install Foundation version could not be resolved."),
        ValidationProfileDiagnostic("VP-LEGACY-002", "warning", message="A minimum baseline validation profile was selected."),
    )
    return _profile(version, install_foundation, runtime_version, "minimum_baseline", baseline, features, {}, {}, {}, diagnostics)


def _resolve_declared(root: Path, version: str, declaration: dict[str, Any]) -> ValidationProfile:
    diagnostics: list[ValidationProfileDiagnostic] = []
    commands = {_normalize_command(str(item)) for item in declaration.get("commands", [])}
    fixtures = _resolve_fixtures(root, declaration.get("fixtures", {}), diagnostics)
    components = _resolve_components(root, declaration.get("components", {}), diagnostics)
    schemas = _resolve_schemas(root, declaration.get("schemas", {}), diagnostics)
    baseline = _resolve_capability_group(
        "baseline", declaration.get("baseline", {}), STANDARD_BASELINE, commands, fixtures, components, schemas, diagnostics
    )
    feature_defaults = {item: "optional" for item in STANDARD_FEATURES}
    features = _resolve_capability_group(
        "feature", declaration.get("features", {}), feature_defaults, commands, fixtures, components, schemas, diagnostics
    )
    return _profile(
        version,
        str(declaration.get("install_foundation_version", "unknown")),
        str(declaration.get("runtime_version", version)),
        "release_metadata",
        baseline,
        features,
        fixtures,
        components,
        schemas,
        tuple(diagnostics),
    )


def _resolve_capability_group(
    category: str,
    declarations: Any,
    defaults: Mapping[str, str],
    commands: set[str],
    fixtures: Mapping[str, FixtureCapability],
    components: Mapping[str, ComponentCapability],
    schemas: Mapping[str, SchemaCapability],
    diagnostics: list[ValidationProfileDiagnostic],
) -> dict[str, ValidationCapability]:
    declared_map = declarations if isinstance(declarations, dict) else {}
    result: dict[str, ValidationCapability] = {}
    for capability_id in sorted(set(defaults) | set(declared_map)):
        item = declared_map.get(capability_id)
        if not isinstance(item, dict):
            result[capability_id] = _simple_capability(capability_id, category, defaults.get(capability_id, "optional"), False)
            continue
        level = str(item.get("required_level", defaults.get(capability_id, "optional")))
        command = item.get("command")
        command_available = command is None or _normalize_command(str(command)) in commands
        fixture_ids = tuple(sorted(str(value) for value in item.get("fixtures", [])))
        component_ids = tuple(sorted(str(value) for value in item.get("components", [])))
        schema_ids = tuple(sorted(str(value) for value in item.get("schemas", [])))
        reasons: list[str] = []
        if not command_available:
            reasons.append("required_command_unavailable")
            diagnostics.append(_capability_diagnostic("VP-CAP-001", capability_id, "Declared command is unavailable.", level))
        for fixture_id in fixture_ids:
            status = fixtures.get(fixture_id, FixtureCapability(fixture_id, None, False, "not_declared")).status
            if status == "missing":
                reasons.append("required_fixture_missing")
            elif status == "incomplete":
                reasons.append("required_fixture_incomplete")
            elif status != "available":
                reasons.append("required_fixture_invalid")
        if any(components.get(item_id) is None or components[item_id].status != "available" for item_id in component_ids):
            reasons.append("required_component_missing")
        if any(schemas.get(item_id) is None or schemas[item_id].status != "available" for item_id in schema_ids):
            reasons.append("required_schema_missing")
        result[capability_id] = ValidationCapability(
            capability_id,
            category,
            level,
            True,
            "available" if not reasons else "unavailable",
            str(command) if command is not None else None,
            command_available,
            fixture_ids,
            not fixture_ids or not any(reason.startswith("required_fixture") for reason in reasons),
            component_ids,
            not component_ids or "required_component_missing" not in reasons,
            schema_ids,
            not schema_ids or "required_schema_missing" not in reasons,
            tuple(sorted(set(reasons))),
        )
    return result


def _resolve_fixtures(root: Path, declarations: Any, diagnostics: list[ValidationProfileDiagnostic]) -> dict[str, FixtureCapability]:
    result: dict[str, FixtureCapability] = {}
    for fixture_id, item in sorted((declarations if isinstance(declarations, dict) else {}).items()):
        relative = str(item.get("path", "")) if isinstance(item, dict) else ""
        path, path_error = _safe_resource_path(root, relative)
        path_type = str(item.get("path_type", "directory")) if isinstance(item, dict) else "directory"
        required_files = tuple(sorted(str(value) for value in item.get("required_files", []))) if isinstance(item, dict) else ()
        required = bool(item.get("required", False)) if isinstance(item, dict) else False
        if path_error:
            status = "invalid_type"
            diagnostics.append(_path_diagnostic(path_error, fixture_id))
            missing_files: tuple[str, ...] = ()
        elif path is None or not path.exists():
            status = "missing"
            missing_files = required_files
            diagnostics.append(_capability_diagnostic("VP-CAP-002", fixture_id, "Required fixture is missing.", "required" if required else "optional"))
        elif (path_type == "directory" and not path.is_dir()) or (path_type == "file" and not path.is_file()):
            status = "invalid_type"
            missing_files = ()
            diagnostics.append(_path_diagnostic("VP-PATH-002", fixture_id))
        else:
            missing_files = tuple(name for name in required_files if not (path / name).is_file()) if path_type == "directory" else ()
            status = "incomplete" if missing_files else "available"
            if missing_files:
                diagnostics.append(_capability_diagnostic("VP-CAP-003", fixture_id, "Required fixture is incomplete.", "required" if required else "optional"))
        result[fixture_id] = FixtureCapability(fixture_id, relative, True, status, path_type, required, required_files, missing_files)
    return result


def _resolve_components(root: Path, declarations: Any, diagnostics: list[ValidationProfileDiagnostic]) -> dict[str, ComponentCapability]:
    result: dict[str, ComponentCapability] = {}
    for component_id, item in sorted((declarations if isinstance(declarations, dict) else {}).items()):
        relative = str(item.get("path", "")) if isinstance(item, dict) else ""
        required = bool(item.get("required", False)) if isinstance(item, dict) else False
        path, error = _safe_resource_path(root, relative)
        status = "invalid_type" if error else "available" if path and path.exists() else "missing"
        if error:
            diagnostics.append(_path_diagnostic(error, component_id))
        elif status == "missing" and required:
            diagnostics.append(_capability_diagnostic("VP-CAP-004", component_id, "Required component is missing.", "required"))
        result[component_id] = ComponentCapability(component_id, relative, required, True, status)
    return result


def _resolve_schemas(root: Path, declarations: Any, diagnostics: list[ValidationProfileDiagnostic]) -> dict[str, SchemaCapability]:
    result: dict[str, SchemaCapability] = {}
    for schema_id, item in sorted((declarations if isinstance(declarations, dict) else {}).items()):
        relative = str(item.get("path", "")) if isinstance(item, dict) else ""
        required = bool(item.get("required", False)) if isinstance(item, dict) else False
        path, error = _safe_resource_path(root, relative)
        status = "invalid_type" if error or (path and path.exists() and not path.is_file()) else "available" if path and path.is_file() else "missing"
        if error:
            diagnostics.append(_path_diagnostic(error, schema_id))
        elif status == "missing" and required:
            diagnostics.append(_capability_diagnostic("VP-CAP-005", schema_id, "Required schema is missing.", "required"))
        result[schema_id] = SchemaCapability(schema_id, relative, required, True, status)
    return result


def _safe_resource_path(root: Path, relative: str) -> tuple[Path | None, str | None]:
    logical = PurePosixPath(relative.replace("\\", "/"))
    if not relative or logical.is_absolute() or ".." in logical.parts:
        return None, "VP-PATH-001"
    candidate = root.joinpath(*logical.parts)
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        current = candidate
        symlink_escape = False
        while current != root:
            symlink_escape = symlink_escape or current.is_symlink()
            current = current.parent
        return None, "VP-PATH-003" if symlink_escape else "VP-PATH-001"
    return candidate, None


def _legacy_components(root: Path) -> dict[str, ComponentCapability]:
    mapping = {
        "cli": "reason",
        "metadata": "metadata",
        "runtime-core": "runtime",
        "schemas": "schemas",
        "standard-library": "standard_library",
        "toolchain": "toolchain",
    }
    return {
        key: ComponentCapability(key, relative, True, True, "available" if (root / relative).exists() else "missing")
        for key, relative in sorted(mapping.items())
    }


def _simple_capability(
    capability_id: str,
    category: str,
    required_level: str,
    declared: bool,
    command: str | None = None,
    command_available: bool = False,
) -> ValidationCapability:
    return ValidationCapability(
        capability_id,
        category,
        required_level,
        declared,
        "available" if declared else "not_declared",
        command,
        command_available,
        (),
        declared,
        (),
        declared,
        (),
        declared,
        () if declared else ("capability_not_declared",),
    )


def _profile(
    version: str,
    install_foundation: str,
    runtime_version: str,
    source: str,
    baseline: Mapping[str, ValidationCapability],
    features: Mapping[str, ValidationCapability],
    fixtures: Mapping[str, FixtureCapability],
    components: Mapping[str, ComponentCapability],
    schemas: Mapping[str, SchemaCapability],
    diagnostics: tuple[ValidationProfileDiagnostic, ...],
) -> ValidationProfile:
    required_ready = all(item.status == "available" for item in baseline.values() if item.required_level == "required")
    required_ready = required_ready and all(item.status == "available" for item in components.values() if item.required)
    required_ready = required_ready and all(item.status == "available" for item in schemas.values() if item.required)
    required_ready = required_ready and all(item.status == "available" for item in fixtures.values() if item.required)
    optional = [item for item in (*baseline.values(), *features.values()) if item.declared and item.required_level == "optional"]
    summary = ValidationProfileSummary(
        len(baseline),
        sum(item.status == "available" for item in baseline.values()),
        sum(item.status in {"unavailable", "invalid", "unsupported"} for item in baseline.values()),
        len(features),
        sum(item.status == "available" for item in features.values()),
        sum(item.status in {"unavailable", "invalid", "unsupported"} for item in features.values()),
        sum(item.status == "not_declared" for item in features.values()),
        len(fixtures),
        sum(item.status == "available" for item in fixtures.values()),
        required_ready,
        all(item.status == "available" for item in optional),
    )
    return ValidationProfile(PROFILE_SCHEMA, version, install_foundation, runtime_version, source, "<release-root>", baseline, features, fixtures, components, schemas, summary, diagnostics)


def _normalize_command(command: str) -> str:
    aliases = {"phase1r validate": "phase1r-validate", "project validate": "project-validate"}
    return aliases.get(command.strip(), command.strip())


def _capability_diagnostic(code: str, capability_id: str, message: str, level: str) -> ValidationProfileDiagnostic:
    severity = "error" if level == "required" else "warning"
    return ValidationProfileDiagnostic(code, severity, message=message, capability_id=capability_id)


def _path_diagnostic(code: str, capability_id: str) -> ValidationProfileDiagnostic:
    messages = {
        "VP-PATH-001": "Declared path escapes the Release Unit.",
        "VP-PATH-002": "Declared resource has an invalid path type.",
        "VP-PATH-003": "Declared symlink escapes the Release Unit.",
    }
    return ValidationProfileDiagnostic(code, "fatal", message=messages[code], capability_id=capability_id)


def _diagnostic_key(item: ValidationProfileDiagnostic) -> tuple[str, str, str]:
    return item.code, item.capability_id or "", item.message
