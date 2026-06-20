"""reason test — discover and execute ReasonScript test suites."""

from __future__ import annotations

from pathlib import Path

from .manifest import Manifest, ManifestError
from .pipeline import PipelineError, compile_source
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
        package_names = (package,) if package is not None else workspace.graph.build_order
        failures = 0
        for package_name in package_names:
            try:
                node = workspace.graph.package(package_name)
            except WorkspaceError as error:
                _print_workspace_error(error)
                return 1
            rc = _run_package(node.path)
            if rc == 3:
                failures += 1
            elif rc != 0:
                return rc
        print(f"Workspace tests completed. {len(package_names)} package(s) tested.")
        return 3 if failures else 0

    if package is not None and package != workspace.default_package.name:
        _print_workspace_error(WorkspaceError(f"unknown package: {package}"))
        return 1
    return _run_package(workspace.default_package.path)


def _run_package(project_root: Path) -> int:
    try:
        Manifest.load(project_root)
    except ManifestError as e:
        print(f"Error:\n\n{e}")
        return 1

    tests_dir = project_root / "tests"
    if not tests_dir.exists():
        print("No tests/ directory found.")
        return 0

    test_files = sorted(tests_dir.rglob("*.rsn"))
    if not test_files:
        print("No test files found.")
        return 0

    passed: list[str] = []
    failed: list[tuple[str, str]] = []

    for test_path in test_files:
        name = test_path.stem
        source = test_path.read_text(encoding="utf-8")
        try:
            compile_source(source, test_path)
            passed.append(name)
        except PipelineError as e:
            failed.append((name, f"{e.code}: {e.message}"))

    for name in passed:
        print(f"PASS  {name}")
    for name, msg in failed:
        print(f"FAIL  {name}")
        print(f"      {msg}")

    print()
    print(f"{len(passed)} passed")
    print(f"{len(failed)} failed")

    return 3 if failed else 0


def _print_workspace_error(error: WorkspaceError) -> None:
    diagnostic = diagnostic_from_workspace_error(error)
    print(f"Error:\n\n{diagnostic.code}\n\n{diagnostic.message}")
