"""reason run — execute a compiled ReasonScript program."""

from __future__ import annotations

import json
from pathlib import Path

from .manifest import Manifest, ManifestError
from .source_selection import SourceSelectionError, package_sources
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
    auto_build: bool = False,
    trace_config: dict | None = None,
    frozen: bool = False,
    inputs_path: str | None = None,
    dependency_roots: tuple[Path, ...] = (),
) -> int:
    try:
        workspace = PackageGraphService().discover(project_root)
    except WorkspaceError as error:
        _print_workspace_error(error)
        return 1
    except ManifestError as error:
        print(f"Error:\n\n{error}")
        return 1

    from .build_cmd import _dependency_roots

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
            auto_build=auto_build,
            trace_config=trace_config,
            frozen=frozen, inputs_path=inputs_path,
            dependency_roots=_dependency_roots(workspace.graph, node.name),
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
        auto_build=auto_build,
        trace_config=trace_config,
        frozen=frozen, inputs_path=inputs_path,
    )


def _run_package(
    project_root: Path,
    *,
    workspace_package: str | None = None,
    entry: str | None = None,
    include_trace: bool = False,
    filesystem_read: bool = False,
    filesystem_write: bool = False,
    auto_build: bool = False,
    trace_config: dict | None = None,
    frozen: bool = False,
    inputs_path: str | None = None,
    dependency_roots: tuple[Path, ...] = (),
) -> int:
    try:
        manifest = Manifest.load(project_root)
    except ManifestError as e:
        print(f"Error:\n\n{e}")
        return 1

    try:
        sources = [] if frozen else package_sources(project_root, manifest)
    except SourceSelectionError as error:
        print(f"Error:\n\n{error.code}\n\n{error}")
        return 1
    if not sources and not frozen:
        print("Error:\n\nNoSourceFiles\n\nsrc/ contains no .rsn files.")
        return 1

    ir_dir = project_root / "target" / "ir"
    computation_path = project_root / "target" / "computation_ir" / "package.json"
    if auto_build and not frozen:
        import contextlib
        import io
        from toolchain.build_cmd import run as build_package
        build_buffer = io.StringIO()
        with contextlib.redirect_stdout(build_buffer):
            build_code = build_package(project_root, package=workspace_package)
        if build_code != 0:
            print(build_buffer.getvalue(), end="")
            return 2

    if not ir_dir.is_dir() or not any(ir_dir.glob("*.json")):
        print("Error:\n\nNoBuildArtifacts\n\nRun 'reason build' first.")
        return 1

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
    from .compiled_ir import ArtifactError, load, read_json
    try:
        computation_ir = load(project_root, dependency_roots, frozen=frozen)
        inputs = read_json(Path(inputs_path).read_bytes()) if inputs_path is not None else None
        if inputs is not None and (not isinstance(inputs, dict) or entry is None):
            raise ArtifactError("RTH-INPUT-001", "--inputs requires a JSON object and --entry function")
    except (ArtifactError, OSError, ValueError) as error:
        print(json.dumps({"status": "failure", "diagnostics": [{
            "code": getattr(error, "code", "RTH-INPUT-001"), "severity": "error",
            "category": "runtime.native", "message": str(error),
        }]}))
        return 2

    from toolchain.runtime_dispatch import RustDispatchError, execute_rust_ir

    try:
        runtime_result = execute_rust_ir(
            computation_ir,
            project_root,
            filesystem_read,
            filesystem_write,
            backend=manifest.backend,
            **({"entry": entry, "inputs": inputs} if inputs is not None else {}),
            include_trace=include_trace,
            max_call_depth=manifest.max_call_depth,
            trace_config=trace_config,
            max_loop_iterations=manifest.max_loop_iterations,
        )
    except RustDispatchError as error:
        print(json.dumps({"status": "failure", "diagnostics": [error.to_diagnostic()]}, indent=2))
        return 2

    calculations = runtime_result["calculations"]
    selected_entry_name: str | None = None
    if inputs is not None:
        selected_entry_name = next(iter(calculations), None)
    elif entry is not None:
        entry_name = entry.rsplit("::", 1)[-1].rsplit(".", 1)[-1]
        if entry_name not in calculations:
            available = ("\n\nAvailable calculations:\n" + "\n".join(f"  - {name}" for name in sorted(calculations.keys()))) if calculations else ""
            print(f"Error:\n\nUnknownEntry\n\nNo calculation named: {entry}{available}")
            return 1
        selected_entry_name = entry_name
    elif calculations:
        # Deterministic entry resolution: single calculation or preferred Main/main
        if len(calculations) == 1:
            selected_entry_name = next(iter(calculations.keys()))
        elif "Main" in calculations:
            selected_entry_name = "Main"
        elif "main" in calculations:
            selected_entry_name = "main"
        else:
            available = "\n".join(f"  - {name}" for name in sorted(calculations.keys()))
            print(f"Error:\n\nAmbiguousEntry\n\nMultiple executable calculations found. Please specify an entry with 'reason run <entry>':\n{available}")
            return 1

    if selected_entry_name is not None:
        runtime_result["result"] = calculations[selected_entry_name]

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
        "entry": entry if entry is not None else selected_entry_name,
    }
    if include_trace:
        result["trace"] = (
            runtime_result["tensor_trace"]
            + runtime_result["loop_trace"]
            + runtime_result["vision_trace"]
            + runtime_result.get("reasoning_trace", [])
            + runtime_result.get("complex_trace", [])
        )
    print(json.dumps(result, indent=2))
    return 0


def _print_workspace_error(error: WorkspaceError) -> None:
    diagnostic = diagnostic_from_workspace_error(error)
    print(f"Error:\n\n{diagnostic.code}\n\n{diagnostic.message}")
