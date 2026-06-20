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
    dependencies: dict[str, object] = field(default_factory=dict)

    @staticmethod
    def load(project_root: Path) -> "Manifest":
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
        except KeyError as e:
            raise ManifestError(f"reason.toml missing field: {e}") from e
        if backend not in SUPPORTED_BACKENDS:
            raise ManifestError(
                f"Unknown runtime backend '{backend}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_BACKENDS))}"
            )
        return Manifest(
            name=package["name"],
            version=package["version"],
            language_core=compiler.get("language_core", "0.7"),
            platform=compiler.get("platform", "0.2"),
            backend=backend,
            dependencies=dict(data.get("dependencies", {})),
        )
