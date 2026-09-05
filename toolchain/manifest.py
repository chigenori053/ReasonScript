"""reason.toml manifest loading and validation."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

SUPPORTED_BACKENDS = {"RuntimeReal", "HybridRuntime"}

KNOWN_SECTIONS = {
    "package",
    "project",
    "source",
    "artifacts",
    "compiler",
    "runtime",
    "dependencies",
    "capabilities",
}

KNOWN_SECTION_KEYS = {
    "package": {"name", "version", "identifier"},
    "project": {"name", "version", "reason_version"},
    "source": {"entry"},
    "artifacts": {"directory"},
    "compiler": {"language_core", "platform"},
    "runtime": {"backend", "max_call_depth"},
}


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Manifest:
    name: str
    version: str
    language_core: str
    platform: str
    backend: str
    # `None` means "use the Rust VM's own built-in default"
    # (`DEFAULT_MAX_CALL_DEPTH`) -- the default value itself is not
    # duplicated here, only whether the project overrides it (Phase 4,
    # "制御された再帰": max_call_depth as part of the compiler/runtime
    # contract, the same way `backend` already is).
    max_call_depth: int | None = None
    dependencies: dict[str, object] = field(default_factory=dict)
    identifier: str | None = None
    project_name: str | None = None
    project_version: str | None = None
    reason_version: str | None = None
    source_entry: str = "src/main.rsn"
    artifacts_directory: str = "artifacts"
    capabilities: dict[str, object] = field(default_factory=dict)

    @staticmethod
    def load(project_root: Path) -> Manifest:
        path = project_root / "reason.toml"
        if not path.exists():
            raise ManifestError(f"reason.toml not found in {project_root}")
        with path.open("rb") as f:
            data = tomllib.load(f)

        if not isinstance(data, dict):
            raise ManifestError("reason.toml must contain a valid TOML document")

        # Unknown sections warning
        unknown_sections = sorted(set(data.keys()) - KNOWN_SECTIONS)
        if unknown_sections:
            warnings.warn(
                f"Unknown sections in reason.toml: {', '.join(unknown_sections)}",
                UserWarning,
            )

        # Unknown keys in known sections warning (deterministic order)
        for section, known_keys in sorted(KNOWN_SECTION_KEYS.items()):
            sec_data = data.get(section)
            if isinstance(sec_data, dict):
                unknown_keys = sorted(set(sec_data.keys()) - known_keys)
                if unknown_keys:
                    warnings.warn(
                        f"Unknown keys in reason.toml [{section}]: {', '.join(unknown_keys)}",
                        UserWarning,
                    )

        # Validate [package]
        if "package" not in data:
            raise ManifestError("reason.toml missing required section: [package]")
        package = data["package"]
        if not isinstance(package, dict):
            raise ManifestError("[package] must be a table")

        pkg_name = package.get("name")
        if not isinstance(pkg_name, str) or not pkg_name.strip():
            raise ManifestError("package.name must be a non-empty string")

        pkg_version = package.get("version")
        if not isinstance(pkg_version, str) or not pkg_version.strip():
            raise ManifestError("package.version must be a non-empty string")

        pkg_identifier = package.get("identifier")
        if pkg_identifier is not None and (
            not isinstance(pkg_identifier, str) or not pkg_identifier.strip()
        ):
            raise ManifestError("package.identifier must be a non-empty string")

        # Validate [project]
        project = data.get("project", {})
        if not isinstance(project, dict):
            raise ManifestError("[project] must be a table")
        proj_name = project.get("name", pkg_name)
        if proj_name is not None and (
            not isinstance(proj_name, str) or not proj_name.strip()
        ):
            raise ManifestError("project.name must be a non-empty string")
        proj_version = project.get("version", pkg_version)
        if proj_version is not None and (
            not isinstance(proj_version, str) or not proj_version.strip()
        ):
            raise ManifestError("project.version must be a non-empty string")
        proj_reason_version = project.get("reason_version")
        if proj_reason_version is not None and (
            not isinstance(proj_reason_version, str) or not proj_reason_version.strip()
        ):
            raise ManifestError("project.reason_version must be a non-empty string")

        # Validate [source]
        source = data.get("source", {})
        if not isinstance(source, dict):
            raise ManifestError("[source] must be a table")
        source_entry = source.get("entry", "src/main.rsn")
        if not isinstance(source_entry, str) or not source_entry.strip():
            raise ManifestError("source.entry must be a non-empty string")
        source_path = Path(source_entry)
        if source_path.is_absolute():
            raise ManifestError("source.entry cannot be an absolute path")
        resolved_source = (project_root / source_path).resolve()
        proj_root_resolved = project_root.resolve()
        if (
            resolved_source != proj_root_resolved
            and proj_root_resolved not in resolved_source.parents
        ):
            raise ManifestError("source.entry cannot escape project root")

        # Validate [artifacts]
        artifacts = data.get("artifacts", {})
        if not isinstance(artifacts, dict):
            raise ManifestError("[artifacts] must be a table")
        artifacts_directory = artifacts.get("directory", "artifacts")
        if not isinstance(artifacts_directory, str) or not artifacts_directory.strip():
            raise ManifestError("artifacts.directory must be a non-empty string")
        artifacts_path = Path(artifacts_directory)
        if artifacts_path.is_absolute():
            raise ManifestError("artifacts.directory cannot be an absolute path")
        resolved_artifacts = (project_root / artifacts_path).resolve()
        if (
            resolved_artifacts != proj_root_resolved
            and proj_root_resolved not in resolved_artifacts.parents
        ):
            raise ManifestError("artifacts.directory cannot escape project root")

        # Validate [compiler]
        compiler = data.get("compiler", {})
        if not isinstance(compiler, dict):
            raise ManifestError("[compiler] must be a table")
        language_core = compiler.get("language_core", "0.7")
        if not isinstance(language_core, str):
            raise ManifestError("compiler.language_core must be a string")
        platform = compiler.get("platform", "0.2")
        if not isinstance(platform, str):
            raise ManifestError("compiler.platform must be a string")

        # Validate [runtime]
        runtime = data.get("runtime", {})
        if not isinstance(runtime, dict):
            raise ManifestError("[runtime] must be a table")
        backend = runtime.get("backend", "RuntimeReal")
        if not isinstance(backend, str) or backend not in SUPPORTED_BACKENDS:
            raise ManifestError(
                f"Unknown runtime backend '{backend}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_BACKENDS))}"
            )
        max_call_depth = runtime.get("max_call_depth")
        if max_call_depth is not None and (
            isinstance(max_call_depth, bool)
            or not isinstance(max_call_depth, int)
            or max_call_depth < 1
        ):
            raise ManifestError("runtime.max_call_depth must be a positive integer")

        # Validate [dependencies] & [capabilities]
        dependencies = data.get("dependencies", {})
        if not isinstance(dependencies, dict):
            raise ManifestError("[dependencies] must be a table")
        capabilities = data.get("capabilities", {})
        if not isinstance(capabilities, dict):
            raise ManifestError("[capabilities] must be a table")

        return Manifest(
            name=pkg_name,
            version=pkg_version,
            language_core=language_core,
            platform=platform,
            backend=backend,
            max_call_depth=max_call_depth,
            dependencies=dict(dependencies),
            identifier=pkg_identifier,
            project_name=proj_name,
            project_version=proj_version,
            reason_version=proj_reason_version,
            source_entry=source_entry,
            artifacts_directory=artifacts_directory,
            capabilities=dict(capabilities),
        )

