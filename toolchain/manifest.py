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
            max_call_depth=max_call_depth,
            dependencies=dict(data.get("dependencies", {})),
        )
