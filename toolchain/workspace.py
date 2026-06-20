"""Toolchain Phase 2 workspace and package graph services."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

from frontend.runtime_integration import (
    DiagnosticSeverity,
    DiagnosticSource,
    PlatformDiagnostic,
)

from .manifest import Manifest, ManifestError


PACKAGE_GRAPH_SCHEMA = "reasonscript-package-graph/0.1"
TOOLCHAIN_SCHEMA = "reasonscript-toolchain/0.2"
_EXACT_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


class WorkspaceError(ValueError):
    code = "WorkspaceError"


class WorkspaceManifestError(WorkspaceError):
    code = "WorkspaceManifestError"


class DuplicatePackageError(WorkspaceError):
    code = "DuplicatePackage"


class MissingPackageError(WorkspaceError):
    code = "MissingPackage"


class UnknownPackageError(WorkspaceError):
    code = "UnknownPackage"


class InvalidVersionError(WorkspaceError):
    code = "InvalidVersion"


class DependencyCycleError(WorkspaceError):
    code = "DependencyCycle"


@dataclass(frozen=True)
class WorkspaceManifest:
    root: Path
    members: tuple[str, ...]
    default_package: str | None = None

    @staticmethod
    def load(root: Path) -> "WorkspaceManifest":
        path = root / "reason.workspace.toml"
        if not path.exists():
            raise WorkspaceManifestError(f"reason.workspace.toml not found in {root}")
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        workspace = data.get("workspace")
        if not isinstance(workspace, dict):
            raise WorkspaceManifestError("reason.workspace.toml missing [workspace]")
        members = workspace.get("members")
        if not isinstance(members, list) or not all(isinstance(item, str) for item in members):
            raise WorkspaceManifestError("workspace.members must be an array of package paths")
        default_package = workspace.get("default_package")
        if default_package is not None and not isinstance(default_package, str):
            raise WorkspaceManifestError("workspace.default_package must be a package name")
        return WorkspaceManifest(root, tuple(members), default_package)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": TOOLCHAIN_SCHEMA,
            "root": str(self.root),
            "members": list(self.members),
            "default_package": self.default_package,
        }


@dataclass(frozen=True)
class PackageNode:
    name: str
    version: str
    path: Path
    manifest: Manifest

    @property
    def identity(self) -> str:
        return f"{self.name}@{self.version}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "identity": self.identity,
            "path": str(self.path),
            "dependencies": self.manifest.dependencies,
        }


@dataclass(frozen=True)
class DependencyEdge:
    package: str
    dependency: str
    requirement: str
    kind: str = "workspace"

    def to_dict(self) -> dict[str, Any]:
        return {
            "package": self.package,
            "dependency": self.dependency,
            "requirement": self.requirement,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class PackageGraph:
    packages: tuple[PackageNode, ...]
    dependencies: tuple[DependencyEdge, ...]
    build_order: tuple[str, ...]
    diagnostics: tuple[PlatformDiagnostic, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def package(self, name: str) -> PackageNode:
        for package in self.packages:
            if package.name == name:
                return package
        raise UnknownPackageError(f"unknown package: {name}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PACKAGE_GRAPH_SCHEMA,
            "packages": [package.to_dict() for package in self.packages],
            "dependencies": [edge.to_dict() for edge in self.dependencies],
            "build_order": list(self.build_order),
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class Workspace:
    root: Path
    manifest: WorkspaceManifest | None
    graph: PackageGraph

    @property
    def is_workspace(self) -> bool:
        return self.manifest is not None

    @property
    def default_package(self) -> PackageNode:
        if self.manifest is not None and self.manifest.default_package is not None:
            return self.graph.package(self.manifest.default_package)
        if len(self.graph.packages) == 1:
            return self.graph.packages[0]
        if self.graph.build_order:
            return self.graph.package(self.graph.build_order[-1])
        raise MissingPackageError("workspace has no default package")


class PackageGraphService:
    """Owns workspace discovery, dependency resolution, and build ordering."""

    def discover(self, start: str | Path) -> Workspace:
        root = discover_workspace_root(start)
        if (root / "reason.workspace.toml").is_file():
            manifest = WorkspaceManifest.load(root)
            graph = self.resolve_workspace(root, manifest)
            return Workspace(root, manifest, graph)
        graph = self.resolve_package(root)
        return Workspace(root, None, graph)

    def resolve_package(self, root: Path) -> PackageGraph:
        manifest = Manifest.load(root)
        package = PackageNode(manifest.name, manifest.version, root.resolve(), manifest)
        _validate_exact_version(package.version, f"{package.name} package version")
        return PackageGraph((package,), (), (package.name,), metadata={"workspace": False})

    def resolve_workspace(
        self,
        root: Path,
        workspace_manifest: WorkspaceManifest | None = None,
    ) -> PackageGraph:
        manifest = workspace_manifest or WorkspaceManifest.load(root)
        packages = self._load_member_packages(root, manifest)
        edges = self._resolve_edges(packages)
        order = self._topological_sort(packages, edges)
        return PackageGraph(
            tuple(sorted(packages, key=lambda item: item.name)),
            tuple(sorted(edges, key=lambda item: (item.package, item.dependency))),
            order,
            (),
            {"workspace": True, "root": str(root)},
        )

    def validate(self, start: str | Path) -> tuple[PlatformDiagnostic, ...]:
        try:
            self.discover(start)
        except WorkspaceError as error:
            return (diagnostic_from_workspace_error(error),)
        except ManifestError as error:
            return (
                PlatformDiagnostic(
                    "PackageManifest",
                    DiagnosticSeverity.ERROR,
                    str(error),
                    DiagnosticSource.TOOLCHAIN,
                ),
            )
        return ()

    def _load_member_packages(
        self,
        root: Path,
        workspace_manifest: WorkspaceManifest,
    ) -> list[PackageNode]:
        packages: list[PackageNode] = []
        seen_names: dict[str, Path] = {}
        seen_identities: dict[str, Path] = {}
        for member in workspace_manifest.members:
            package_root = (root / member).resolve()
            if not (package_root / "reason.toml").is_file():
                raise MissingPackageError(f"workspace member missing reason.toml: {member}")
            try:
                manifest = Manifest.load(package_root)
            except ManifestError as error:
                raise MissingPackageError(str(error)) from error
            package = PackageNode(manifest.name, manifest.version, package_root, manifest)
            _validate_exact_version(package.version, f"{package.name} package version")
            if package.name in seen_names:
                raise DuplicatePackageError(
                    f"duplicate package name: {package.name} at {package_root} and {seen_names[package.name]}"
                )
            if package.identity in seen_identities:
                raise DuplicatePackageError(f"duplicate package identity: {package.identity}")
            seen_names[package.name] = package_root
            seen_identities[package.identity] = package_root
            packages.append(package)
        if not packages:
            raise MissingPackageError("workspace has no members")
        return packages

    def _resolve_edges(self, packages: list[PackageNode]) -> list[DependencyEdge]:
        by_name = {package.name: package for package in packages}
        by_path = {package.path.resolve(): package for package in packages}
        edges: list[DependencyEdge] = []
        for package in packages:
            for dep_name, requirement in sorted(package.manifest.dependencies.items()):
                dependency, version, kind = _resolve_dependency(package, dep_name, requirement, by_name, by_path)
                if dependency.name != dep_name:
                    raise UnknownPackageError(
                        f"dependency key '{dep_name}' resolved to package '{dependency.name}'"
                    )
                if dependency.version != version:
                    raise InvalidVersionError(
                        f"{package.name} requires {dep_name}@{version}, found {dependency.version}"
                    )
                edges.append(DependencyEdge(package.name, dependency.name, version, kind))
        return edges

    def _topological_sort(
        self,
        packages: list[PackageNode],
        edges: list[DependencyEdge],
    ) -> tuple[str, ...]:
        names = sorted(package.name for package in packages)
        dependencies = {name: set() for name in names}
        dependents = {name: set() for name in names}
        for edge in edges:
            dependencies[edge.package].add(edge.dependency)
            dependents[edge.dependency].add(edge.package)
        ready = sorted(name for name in names if not dependencies[name])
        order: list[str] = []
        while ready:
            current = ready.pop(0)
            order.append(current)
            for dependent in sorted(dependents[current]):
                dependencies[dependent].discard(current)
                if not dependencies[dependent] and dependent not in order and dependent not in ready:
                    ready.append(dependent)
            ready.sort()
        if len(order) != len(names):
            remaining = sorted(name for name in names if name not in order)
            raise DependencyCycleError(f"dependency cycle detected: {' -> '.join(remaining)}")
        return tuple(order)


def discover_workspace_root(start: str | Path) -> Path:
    current = Path(start).resolve()
    if current.is_file():
        current = current.parent
    package_root: Path | None = None
    for path in (current, *current.parents):
        if (path / "reason.workspace.toml").is_file():
            return path
        if package_root is None and (path / "reason.toml").is_file():
            package_root = path
    return package_root or current


def load_package_graph(start: str | Path) -> PackageGraph:
    return PackageGraphService().discover(start).graph


def diagnostic_from_workspace_error(error: WorkspaceError) -> PlatformDiagnostic:
    return PlatformDiagnostic(
        error.code,
        DiagnosticSeverity.ERROR,
        str(error),
        DiagnosticSource.TOOLCHAIN,
        metadata={"toolchain_schema": TOOLCHAIN_SCHEMA},
    )


def _resolve_dependency(
    package: PackageNode,
    dep_name: str,
    requirement: object,
    by_name: dict[str, PackageNode],
    by_path: dict[Path, PackageNode],
) -> tuple[PackageNode, str, str]:
    if isinstance(requirement, str):
        _validate_exact_version(requirement, f"{package.name}.{dep_name}")
        dependency = by_name.get(dep_name)
        if dependency is None:
            raise UnknownPackageError(f"{package.name} depends on unknown package: {dep_name}")
        return dependency, requirement, "workspace"
    if isinstance(requirement, dict) and isinstance(requirement.get("path"), str):
        dependency_path = (package.path / str(requirement["path"])).resolve()
        dependency = by_path.get(dependency_path)
        if dependency is None:
            if not (dependency_path / "reason.toml").is_file():
                raise MissingPackageError(f"{package.name} depends on missing package path: {dependency_path}")
            manifest = Manifest.load(dependency_path)
            dependency = PackageNode(manifest.name, manifest.version, dependency_path, manifest)
        version = str(requirement.get("version", dependency.version))
        _validate_exact_version(version, f"{package.name}.{dep_name}")
        return dependency, version, "path"
    raise InvalidVersionError(f"{package.name}.{dep_name} must be an exact version or path dependency")


def _validate_exact_version(version: object, label: str) -> None:
    if not isinstance(version, str) or _EXACT_VERSION.fullmatch(version) is None:
        raise InvalidVersionError(f"{label} must use exact x.y.z version, got {version!r}")
