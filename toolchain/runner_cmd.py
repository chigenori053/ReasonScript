"""reason test — discover and execute ReasonScript test suites."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .manifest import Manifest, ManifestError
from .pipeline import (
    PipelineError,
    compile_package_sources,
    compile_source,
    _package_program,
)
from .workspace import (
    PackageGraphService,
    WorkspaceError,
    diagnostic_from_workspace_error,
)
from frontend.language_surface import parse, validate
from frontend.computation_ir import lower_program, validate_program, interpret_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import execute_program, IntegratedRuntimeError


def run(
    project_root: Path,
    package: str | None = None,
    *,
    compile_only: bool = False,
    json_output: bool = False,
    junit_path: Path | None = None,
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
        package_names = (package,) if package is not None else workspace.graph.build_order
        failures = 0
        all_results = []
        for package_name in package_names:
            try:
                node = workspace.graph.package(package_name)
            except WorkspaceError as error:
                _print_workspace_error(error)
                return 1
            rc, res = _run_package(node.path, compile_only=compile_only, silent=json_output)
            all_results.append(res)
            if rc != 0:
                failures += 1
        if json_output:
            combined = {
                "ok": failures == 0,
                "packages": all_results,
            }
            print(json.dumps(combined, indent=2))
        else:
            print(f"Workspace tests completed. {len(package_names)} package(s) tested.")
        return 3 if failures else 0

    if package is not None and package != workspace.default_package.name:
        _print_workspace_error(WorkspaceError(f"unknown package: {package}"))
        return 1

    rc, res = _run_package(workspace.default_package.path, compile_only=compile_only, silent=json_output)
    if json_output:
        print(json.dumps(res, indent=2))
    if junit_path:
        _write_junit(junit_path, res)
    return rc


def _run_package(project_root: Path, *, compile_only: bool = False, silent: bool = False) -> tuple[int, dict[str, Any]]:
    try:
        Manifest.load(project_root)
    except ManifestError as e:
        if not silent:
            print(f"Error:\n\n{e}")
        return 1, {"ok": False, "error": str(e)}

    tests_dir = project_root / "tests"
    if not tests_dir.exists():
        if not silent:
            print("No tests/ directory found.")
        return 0, {"ok": True, "passed": [], "failed": [], "total": 0}

    test_files = sorted(tests_dir.rglob("*.rsn"))
    if not test_files:
        if not silent:
            print("No test files found.")
        return 0, {"ok": True, "passed": [], "failed": [], "total": 0}

    passed: list[str] = []
    failed: list[dict[str, Any]] = []
    source_files = (
        sorted((project_root / "src").rglob("*.rsn"))
        if (project_root / "src").is_dir()
        else []
    )
    package_sources = [
        (path.read_text(encoding="utf-8"), path) for path in source_files
    ]
    rust_binary = find_binary()

    for test_path in test_files:
        name = test_path.stem
        test_source = test_path.read_text(encoding="utf-8")
        has_imports = any(
            line.lstrip().startswith("import ")
            for line in test_source.splitlines()
        )

        # 1. Compilation check
        try:
            if has_imports and package_sources:
                compile_package_sources(
                    [*package_sources, (test_source, test_path)]
                )
            else:
                compile_source(test_source, test_path)
        except Exception as e:
            failed.append({"name": name, "kind": "COMPILE_ERROR", "message": str(e)})
            continue

        if compile_only:
            passed.append(name)
            continue

        # 2. Execution check
        try:
            if has_imports and package_sources:
                program = _package_program([*package_sources, (test_source, test_path)])
            else:
                program = parse(test_source)
                validate(program)
            ir = lower_program(program)
            ir_errors = validate_program(ir)
            if ir_errors:
                failed.append({"name": name, "kind": "IR_VALIDATION_ERROR", "message": "; ".join(ir_errors)})
                continue

            if rust_binary is not None:
                rust_res = run_ir(ir, binary=rust_binary)
                if not rust_res.ok:
                    kind = "ASSERTION_FAILURE" if rust_res.error_code == "TEST-ASSERT-001" else "RUNTIME_ERROR"
                    failed.append({"name": name, "kind": kind, "message": f"{rust_res.error_code}: {rust_res.error_message}"})
                    continue
            else:
                interpret_program(ir)
                execute_program(program)

            passed.append(name)
        except IntegratedRuntimeError as e:
            kind = "ASSERTION_FAILURE" if e.code == "TEST-ASSERT-001" else "RUNTIME_ERROR"
            failed.append({"name": name, "kind": kind, "message": f"{e.code}: {e}"})
        except Exception as e:
            failed.append({"name": name, "kind": "RUNTIME_ERROR", "message": str(e)})

    if not silent:
        for name in passed:
            print(f"PASS  {name}")
        for f in failed:
            print(f"FAIL  {f['name']} ({f['kind']})")
            print(f"      {f['message']}")

        print()
        print(f"{len(passed)} passed")
        print(f"{len(failed)} failed")

    result_dict = {
        "ok": len(failed) == 0,
        "passed": passed,
        "failed": failed,
        "total": len(passed) + len(failed),
    }
    return (3 if failed else 0), result_dict


def _write_junit(path: Path, result: dict[str, Any]) -> None:
    passed = result.get("passed", [])
    failed = result.get("failed", [])
    total = len(passed) + len(failed)
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', f'<testsuite name="reason-tests" tests="{total}" failures="{len(failed)}">']
    for p in passed:
        xml.append(f'  <testcase name="{p}"/>')
    for f in failed:
        xml.append(f'  <testcase name="{f["name"]}">')
        xml.append(f'    <failure message="{f["message"]}" type="{f["kind"]}"/>')
        xml.append('  </testcase>')
    xml.append('</testsuite>')
    path.write_text("\n".join(xml), encoding="utf-8")


def _print_workspace_error(error: WorkspaceError) -> None:
    diagnostic = diagnostic_from_workspace_error(error)
    print(f"Error:\n\n{diagnostic.code}\n\n{diagnostic.message}")
