"""reason build — compile source files to AST, IR, and metadata."""

from __future__ import annotations

import json
from pathlib import Path

from .manifest import Manifest, ManifestError
from .pipeline import PipelineError, compile_package_sources
from .source_selection import SourceSelectionError, package_sources
from .workspace import (
    PackageGraphService,
    WorkspaceError,
    diagnostic_from_workspace_error,
)

_CACHE_KEY_FILE = ".reason_build_cache"
_BUILD_FORMAT_VERSION = "runtime-consolidation-phase2-uera8-optimizer"


def _cache_key(
    project_root: Path,
    dependency_roots: tuple[Path, ...] = (),
    *,
    project_sources: tuple[Path, ...] = (),
) -> str:
    import hashlib

    h = hashlib.sha256()
    h.update(_BUILD_FORMAT_VERSION.encode("utf-8"))
    for root in (project_root, *dependency_roots):
        manifest_path = root / "reason.toml"
        if manifest_path.exists():
            h.update(str(manifest_path).encode("utf-8"))
            h.update(manifest_path.read_bytes())
        sources = project_sources if root == project_root and project_sources else tuple(
            sorted((root / "src").rglob("*.rsn"))
        )
        for src in sources:
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

    try:
        sources = package_sources(project_root, manifest)
    except SourceSelectionError as error:
        print(f"Error:\n\n{error.code}\n\n{error}")
        return 1
    if not sources:
        print("Error:\n\nNoSourceFiles\n\nNo .rsn files found in src/.")
        return 1

    target = project_root / "target"
    current_key = _cache_key(
        project_root,
        dependency_roots,
        project_sources=tuple(sources),
    )
    if _load_cache(target) == current_key:
        print("Nothing to build (up to date).")
        return 0

    ast_dir = target / "ast"
    ir_dir = target / "ir"
    meta_dir = target / "metadata"
    computation_ir_dir = target / "computation_ir"
    for d in (ast_dir, ir_dir, meta_dir, computation_ir_dir, target / "runtime"):
        d.mkdir(parents=True, exist_ok=True)

    try:
        result = compile_package_sources(
            [(src_path.read_text(encoding="utf-8"), src_path) for src_path in sources]
        )
    except PipelineError as e:
        print(f"Error:\n\n{e.code}: {e.message}")
        return 1

    expected_ir_files: set[str] = set()
    expected_meta_files: set[str] = set()
    for ir in result.reason_irs:
        module_name = (
            ir.get("module")
            or ir.get("metadata", {}).get("module")
            or "module"
        )
        ir_name = f"{module_name}.json"
        meta_name = f"{module_name}.json"
        expected_ir_files.add(ir_name)
        expected_meta_files.add(meta_name)
        (ir_dir / ir_name).write_text(
            json.dumps(ir, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (meta_dir / meta_name).write_text(
            json.dumps(result.metadata_for(ir), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # Do not let removed modules survive as stale executable artifacts.
    for stale in ir_dir.glob("*.json"):
        if stale.name not in expected_ir_files:
            stale.unlink()
    for stale in meta_dir.glob("*.json"):
        if stale.name not in expected_meta_files:
            stale.unlink()

    ast_payload = {
        "package": manifest.name,
        "sources": [str(src_path.relative_to(project_root)) for src_path in sources],
    }
    for stale in ast_dir.glob("*.json"):
        stale.unlink()
    (ast_dir / "package.json").write_text(
        json.dumps(ast_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    from frontend.computation_ir import LoweringError, lower_program, validate_program
    from frontend.computation_ir.optimizer import optimize_program

    computation_path = computation_ir_dir / "package.json"
    support_path = target / "runtime" / "runtime_support.json"
    try:
        computation_ir = optimize_program(lower_program(result.surface_ast))
        validation_errors = validate_program(computation_ir)
        if validation_errors:
            raise LoweringError("IR-LOWER-010", "; ".join(validation_errors))
    except LoweringError as error:
        computation_path.unlink(missing_ok=True)
        runtime_support = {
            "schema": "reasonscript-runtime-build-support/1.0",
            "rust_executable": False,
            "diagnostic": {"code": error.code, "message": str(error)},
        }
        support_path.write_text(
            json.dumps(runtime_support, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        # A successful build is always runnable by `reason run`.
        print(f"Error:\n\n{error.code}: {error}")
        return 1
    else:
        computation_path.write_text(
            json.dumps(computation_ir, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        runtime_support = {
            "schema": "reasonscript-runtime-build-support/1.0",
            "rust_executable": True,
            "computation_ir": "target/computation_ir/package.json",
        }
    support_path.write_text(
        json.dumps(runtime_support, indent=2, ensure_ascii=False), encoding="utf-8"
    )

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
