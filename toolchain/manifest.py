"""reason.toml manifest loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

SUPPORTED_BACKENDS = {"RuntimeReal", "HybridRuntime"}


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Manifest:
    name: str
    version: str
    language_core: str
    platform: str
    backend: str
    source_entry: str | None = None
    # `None` means "use the Rust VM's own built-in default"
    # (`DEFAULT_MAX_CALL_DEPTH`) -- the default value itself is not
    # duplicated here, only whether the project overrides it (Phase 4,
    # "制御された再帰": max_call_depth as part of the compiler/runtime
    # contract, the same way `backend` already is).
    max_call_depth: int | None = None
    dependencies: dict[str, object] = field(default_factory=dict)

    @staticmethod
    def load(project_root: Path) -> Manifest:
        path = project_root / "reason.toml"
        if not path.exists():
            raise ManifestError(f"reason.toml not found in {project_root}")
        with path.open("rb") as f:
            data = tomllib.load(f)
        try:
            package = data["package"]
            compiler = data.get("compiler", {})
            runtime = data.get("runtime", {})
            backend = runtime.get("backend", "RuntimeReal")
            max_call_depth = runtime.get("max_call_depth")
        except KeyError as e:
            raise ManifestError(f"reason.toml missing field: {e}") from e
        if backend not in SUPPORTED_BACKENDS:
            raise ManifestError(
                f"Unknown runtime backend '{backend}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_BACKENDS))}"
            )
        source = data.get("source", {})
        if source is None:
            source = {}
        if not isinstance(source, dict):
            raise ManifestError("source must be a table")
        source_entry = source.get("entry")
        if source_entry is not None and (
            not isinstance(source_entry, str) or not source_entry.strip()
        ):
            raise ManifestError("source.entry must be a non-empty string")
        known_sections = {
            "package", "project", "source", "artifacts", "compiler",
            "runtime", "dependencies", "capabilities",
        }
        unknown = set(data.keys()) - known_sections
        if unknown:
            import warnings
            warnings.warn(f"Unknown sections in reason.toml: {', '.join(sorted(unknown))}", UserWarning)
        if max_call_depth is not None and (
            isinstance(max_call_depth, bool)
            or not isinstance(max_call_depth, int)
            or max_call_depth < 1
        ):
            raise ManifestError("runtime.max_call_depth must be a positive integer")
        return Manifest(
            name=package["name"],
            version=package["version"],
            language_core=compiler.get("language_core", "0.7"),
            platform=compiler.get("platform", "0.2"),
            backend=backend,
            source_entry=source_entry,
            max_call_depth=max_call_depth,
            dependencies=dict(data.get("dependencies", {})),
        )
