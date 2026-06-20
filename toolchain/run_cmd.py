"""reason run — execute a compiled ReasonScript program."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .manifest import Manifest, ManifestError
from .workspace import PackageGraphService, WorkspaceError, diagnostic_from_workspace_error


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
        try:
            node = workspace.graph.package(package) if package is not None else workspace.default_package
        except WorkspaceError as error:
            _print_workspace_error(error)
            return 1
        return _run_package(node.path, workspace_package=node.name)

    if package is not None and package != workspace.default_package.name:
        _print_workspace_error(WorkspaceError(f"unknown package: {package}"))
        return 1
    return _run_package(workspace.default_package.path, workspace_package=workspace.default_package.name)


def _run_package(project_root: Path, *, workspace_package: str | None = None) -> int:
    try:
        manifest = Manifest.load(project_root)
    except ManifestError as e:
        print(f"Error:\n\n{e}")
        return 1

    ir_dir = project_root / "target" / "ir"
    if not ir_dir.exists() or not any(ir_dir.glob("*.json")):
        print("Error:\n\nNoBuildArtifacts\n\nRun 'reason build' first.")
        return 1

    sys.path.insert(0, str(project_root.parent))
    try:
        from frontend.runtime_integration import (
            execute_runtime_operations_with_registry,
            runtime_real_registry,
            hybrid_runtime_registry,
        )
    except ImportError as e:
        print(f"Error:\n\nRuntimeImportError\n\n{e}")
        return 2

    if manifest.backend == "HybridRuntime":
        registry = hybrid_runtime_registry()
    else:
        registry = runtime_real_registry()

    ir_files = sorted(ir_dir.glob("*.json"))
    errors: list[str] = []
    goal_reached = False

    for ir_path in ir_files:
        reason_ir = json.loads(ir_path.read_text(encoding="utf-8"))
        runtime_ops = reason_ir.get("metadata", {}).get("runtime_operations") or []
        if not runtime_ops:
            goal_reached = True
            continue
        try:
            report = execute_runtime_operations_with_registry(reason_ir, registry)
        except Exception as e:
            errors.append(f"{ir_path.name}: {e}")
            continue
        if not report.diagnostics:
            goal_reached = True

    if errors:
        for e in errors:
            print(f"Error:\n\nRuntimeError\n\n{e}")
        return 2

    result = {
        "status": "success",
        "goal_reached": goal_reached,
        "backend": manifest.backend,
        "package": workspace_package or manifest.name,
    }
    print(json.dumps(result, indent=2))
    return 0


def _print_workspace_error(error: WorkspaceError) -> None:
    diagnostic = diagnostic_from_workspace_error(error)
    print(f"Error:\n\n{diagnostic.code}\n\n{diagnostic.message}")
