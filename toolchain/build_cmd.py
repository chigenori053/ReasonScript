"""reason build — compile source files to AST, IR, and metadata."""

from __future__ import annotations

import json
from pathlib import Path

from .manifest import Manifest, ManifestError
from .pipeline import PipelineError, compile_source
from .workspace import PackageGraphService, WorkspaceError, diagnostic_from_workspace_error

_CACHE_KEY_FILE = ".reason_build_cache"


def _cache_key(project_root: Path, dependency_roots: tuple[Path, ...] = ()) -> str:
    import hashlib

    h = hashlib.sha256()
    for root in (project_root, *dependency_roots):
        manifest_path = root / "reason.toml"
        if manifest_path.exists():
            h.update(str(manifest_path).encode("utf-8"))
            h.update(manifest_path.read_bytes())
        for src in sorted((root / "src").rglob("*.rsn")):
            h.update(str(src).encode("utf-8"))
            h.update(src.read_bytes())
    return h.hexdigest()


def _load_cache(target: Path) -> str:
    p = target / _CACHE_KEY_FILE
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def _save_cache(target: Path, key: str) -> None:
    (target / _CACHE_KEY_FILE).write_text(key, encoding="utf-8")


def run(project_root: Path, package: str | None = None) -> int:
    try:
        workspace = PackageGraphService().discover(project_root)
    except WorkspaceError as error:
        _print_workspace_error(error)
        return 1
    except ManifestError as error:
        print(f"Error:\n\n{error}")
        return 1

    if workspace.is_workspace:
        graph = workspace.graph
        build_names = (package,) if package is not None else graph.build_order
        compiled = 0
        for package_name in build_names:
            try:
                node = graph.package(package_name)
            except WorkspaceError as error:
                _print_workspace_error(error)
                return 1
            rc = _run_package(node.path, dependency_roots=_dependency_roots(graph, package_name))
            if rc != 0:
                return rc
            compiled += 1
        print(f"Workspace build succeeded. {compiled} package(s) built.")
        return 0

    if package is not None and package != workspace.default_package.name:
        _print_workspace_error(WorkspaceError(f"unknown package: {package}"))
        return 1
    return _run_package(workspace.default_package.path)


def _run_package(project_root: Path, dependency_roots: tuple[Path, ...] = ()) -> int:
    try:
        manifest = Manifest.load(project_root)
    except ManifestError as e:
        print(f"Error:\n\n{e}")
        return 1

    src_dir = project_root / "src"
    if not src_dir.exists():
        print("Error:\n\nSourceDirectoryMissing\n\nsrc/ not found.")
        return 1

    sources = sorted(src_dir.rglob("*.rsn"))
    if not sources:
        print("Error:\n\nNoSourceFiles\n\nNo .rsn files found in src/.")
        return 1

    target = project_root / "target"
    current_key = _cache_key(project_root, dependency_roots)
    if _load_cache(target) == current_key:
        print("Nothing to build (up to date).")
        return 0

    ast_dir = target / "ast"
    ir_dir = target / "ir"
    meta_dir = target / "metadata"
    for d in (ast_dir, ir_dir, meta_dir, target / "runtime"):
        d.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    for src_path in sources:
        source = src_path.read_text(encoding="utf-8")
        try:
            result = compile_source(source, src_path)
        except PipelineError as e:
            errors.append(f"{src_path}: {e.code}: {e.message}")
            continue

        stem = src_path.stem
        for ir in result.reason_irs:
            module_name = ir.get("module") or stem
            (ir_dir / f"{module_name}.json").write_text(
                json.dumps(ir, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            meta = result.metadata_for(ir)
            (meta_dir / f"{module_name}.json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
            )

        ast_payload = {
            "package": manifest.name,
            "sources": [str(src_path.relative_to(project_root))],
        }
        (ast_dir / f"{stem}.json").write_text(
            json.dumps(ast_payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    if errors:
        for e in errors:
            print(f"Error:\n\n{e}")
        return 1

    _save_cache(target, current_key)
    print(f"Build succeeded. {len(sources)} file(s) compiled.")
    return 0


def _print_workspace_error(error: WorkspaceError) -> None:
    diagnostic = diagnostic_from_workspace_error(error)
    print(f"Error:\n\n{diagnostic.code}\n\n{diagnostic.message}")


def _dependency_roots(graph, package_name: str) -> tuple[Path, ...]:
    dependencies = {
        edge.package: {dep.dependency for dep in graph.dependencies if dep.package == edge.package}
        for edge in graph.dependencies
    }
    seen: set[str] = set()

    def visit(name: str) -> None:
        for dependency in sorted(dependencies.get(name, ())):
            if dependency not in seen:
                seen.add(dependency)
                visit(dependency)

    visit(package_name)
    return tuple(graph.package(name).path for name in sorted(seen))
