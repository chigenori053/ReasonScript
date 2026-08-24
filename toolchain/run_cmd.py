"""reason run — execute a compiled ReasonScript program."""

from __future__ import annotations

import json
from pathlib import Path

from .manifest import Manifest, ManifestError
from .workspace import (
    PackageGraphService,
    WorkspaceError,
    diagnostic_from_workspace_error,
)


def run(
    project_root: Path,
    package: str | None = None,
    *,
    entry: str | None = None,
    include_trace: bool = False,
    filesystem_read: bool = False,
    filesystem_write: bool = False,
) -> int:
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
        return _run_package(
            node.path,
            workspace_package=node.name,
            entry=entry,
            include_trace=include_trace,
            filesystem_read=filesystem_read,
            filesystem_write=filesystem_write,
        )

    if package is not None and package != workspace.default_package.name:
        _print_workspace_error(WorkspaceError(f"unknown package: {package}"))
        return 1
    return _run_package(
        workspace.default_package.path,
        workspace_package=workspace.default_package.name,
        entry=entry,
        include_trace=include_trace,
        filesystem_read=filesystem_read,
        filesystem_write=filesystem_write,
    )


def _run_package(
    project_root: Path,
    *,
    workspace_package: str | None = None,
    entry: str | None = None,
    include_trace: bool = False,
    filesystem_read: bool = False,
    filesystem_write: bool = False,
) -> int:
    try:
        manifest = Manifest.load(project_root)
    except ManifestError as e:
        print(f"Error:\n\n{e}")
        return 1

    ir_dir = project_root / "target" / "ir"
    if not ir_dir.is_dir() or not any(ir_dir.glob("*.json")):
        print("Error:\n\nNoBuildArtifacts\n\nRun 'reason build' first.")
        return 1

    src_dir = project_root / "src"
    sources = sorted(src_dir.rglob("*.rsn")) if src_dir.exists() else []
    if not sources:
        print("Error:\n\nNoSourceFiles\n\nsrc/ contains no .rsn files.")
        return 1

    computation_path = project_root / "target" / "computation_ir" / "package.json"
    if not computation_path.is_file():
        support_path = project_root / "target" / "runtime" / "runtime_support.json"
        try:
            support = json.loads(support_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            support = {}
        reason = (
            "computation_ir_lowering_unsupported"
            if support.get("rust_executable") is False
            else "built_computation_ir_missing"
        )
        print(
            json.dumps(
                {
                    "status": "failure",
                    "diagnostics": [{
                        "code": "RTH-IR-001",
                        "severity": "error",
                        "category": "runtime.native",
                        "message": "native computation IR is unavailable; run 'reason build' after resolving unsupported language constructs",
                        "reason": reason,
                    }],
                },
                indent=2,
            )
        )
        return 2
    try:
        computation_ir = json.loads(computation_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "failure", "diagnostics": [{
            "code": "RTH-IR-002",
            "severity": "error",
            "category": "runtime.native",
            "message": f"built computation IR is invalid: {error}",
        }]}, indent=2))
        return 2

    from toolchain.runtime_dispatch import RustDispatchError, execute_rust_ir

    try:
        runtime_result = execute_rust_ir(
            computation_ir,
            project_root,
            filesystem_read,
            filesystem_write,
            backend=manifest.backend,
            include_trace=include_trace,
        )
    except RustDispatchError as error:
        print(json.dumps({"status": "failure", "diagnostics": [error.to_diagnostic()]}, indent=2))
        return 2

    calculations = runtime_result["calculations"]
    if entry is not None:
        entry_name = entry.rsplit("::", 1)[-1].rsplit(".", 1)[-1]
        if entry_name not in calculations:
            print(f"Error:\n\nUnknownEntry\n\nNo calculation named: {entry}")
            return 1
        runtime_result["result"] = calculations[entry_name]

    result = {
        "status": "success",
        "goal_reached": bool(calculations),
        "backend": manifest.backend,
        "package": workspace_package or manifest.name,
        "runtime_result": runtime_result,
        "execution_mode": "integrated-rust",
        "runtime_dispatch": {
            "attempted": "rust_computation_vm",
            "selected": "rust_computation_vm",
        },
    }
    if entry is not None:
        result["entry"] = entry
    if include_trace:
        result["trace"] = (
            runtime_result["tensor_trace"]
            + runtime_result["loop_trace"]
            + runtime_result["vision_trace"]
            + runtime_result.get("reasoning_trace", [])
        )
    print(json.dumps(result, indent=2))
    return 0


def _print_workspace_error(error: WorkspaceError) -> None:
    diagnostic = diagnostic_from_workspace_error(error)
    print(f"Error:\n\n{diagnostic.code}\n\n{diagnostic.message}")
