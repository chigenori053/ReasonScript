"""reason test — discover and execute ReasonScript test suites.

Phase 3 ("実行型テスト機構"): a test file that only *compiles* is no
longer reported as PASS -- every `calculation` in it is actually run
through the native Rust host (the same `execute_rust_program` path
`reason run` uses), and `assert`/`assert_eq` failures (`TEST-ASSERT-001`)
are reported as a distinct category from an unrelated runtime error or a
compile-time failure. The pre-Phase-3 compile-only behavior is still
available via `--compile-only`, for callers that only want a fast
syntax/type check over the test suite without executing it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as _xml_escape

from .manifest import Manifest, ManifestError
from .pipeline import PipelineError, compile_package_sources, compile_source
from .runtime_dispatch import RustDispatchError, execute_rust_program
from .workspace import (
    PackageGraphService,
    WorkspaceError,
    diagnostic_from_workspace_error,
)

# `RustDispatchError.code`s that mean "this test file couldn't even be
# turned into executable IR" -- from the test author's point of view this
# is a compile-time defect (an unsupported language construct), not
# something that went wrong while running otherwise-valid code.
_LOWERING_FAILURE_REASONS = {"computation_ir_lowering_unsupported"}

# `RustDispatchError.code`s that mean the whole run can't proceed at all
# (missing/unbuildable native host) -- reported once, not once per test.
_INFRASTRUCTURE_REASONS = {"rust_binary_missing"}


@dataclass
class TestOutcome:
    name: str
    package: str
    status: str  # "pass" | "compile_error" | "runtime_error" | "assertion_failure"
    code: str | None = None
    message: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == "pass"


def run(
    project_root: Path,
    package: str | None = None,
    *,
    compile_only: bool = False,
    output_format: str = "text",
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

    outcomes: list[TestOutcome] = []
    if workspace.is_workspace:
        package_names = (package,) if package is not None else workspace.graph.build_order
        for package_name in package_names:
            try:
                node = workspace.graph.package(package_name)
            except WorkspaceError as error:
                _print_workspace_error(error)
                return 1
            package_outcomes, rc = _collect_package(
                node.path,
                node.name,
                compile_only=compile_only,
                filesystem_read=filesystem_read,
                filesystem_write=filesystem_write,
            )
            if rc == 1:
                return rc
            outcomes.extend(package_outcomes)
        return _report(outcomes, output_format)

    if package is not None and package != workspace.default_package.name:
        _print_workspace_error(WorkspaceError(f"unknown package: {package}"))
        return 1
    package_outcomes, rc = _collect_package(
        workspace.default_package.path,
        workspace.default_package.name,
        compile_only=compile_only,
        filesystem_read=filesystem_read,
        filesystem_write=filesystem_write,
    )
    if rc == 1:
        return rc
    return _report(package_outcomes, output_format)


def _collect_package(
    project_root: Path,
    package_name: str,
    *,
    compile_only: bool,
    filesystem_read: bool,
    filesystem_write: bool,
) -> tuple[list[TestOutcome], int]:
    try:
        manifest = Manifest.load(project_root)
    except ManifestError as e:
        print(f"Error:\n\n{e}")
        return [], 1

    tests_dir = project_root / "tests"
    if not tests_dir.exists():
        print("No tests/ directory found.")
        return [], 0

    test_files = sorted(tests_dir.rglob("*.rsn"))
    if not test_files:
        print("No test files found.")
        return [], 0

    source_files = (
        sorted((project_root / "src").rglob("*.rsn"))
        if (project_root / "src").is_dir()
        else []
    )
    package_sources = [
        (path.read_text(encoding="utf-8"), path) for path in source_files
    ]

    outcomes: list[TestOutcome] = []
    for test_path in test_files:
        name = test_path.stem
        test_source = test_path.read_text(encoding="utf-8")
        try:
            if any(
                line.lstrip().startswith("import ")
                for line in test_source.splitlines()
            ):
                result = compile_package_sources(
                    [*package_sources, (test_source, test_path)]
                )
            else:
                result = compile_source(test_source, test_path)
        except PipelineError as e:
            outcomes.append(TestOutcome(
                name, package_name, "compile_error", e.code, e.message,
            ))
            continue

        if compile_only:
            outcomes.append(TestOutcome(name, package_name, "pass"))
            continue

        try:
            execute_rust_program(
                result.surface_ast,
                project_root,
                filesystem_read,
                filesystem_write,
                backend=manifest.backend,
                max_call_depth=manifest.max_call_depth,
            )
        except RustDispatchError as error:
            if error.reason in _INFRASTRUCTURE_REASONS:
                print(f"Error:\n\n{error.code}\n\n{error.message}")
                return [], 1
            if error.code == "TEST-ASSERT-001":
                outcomes.append(TestOutcome(
                    name, package_name, "assertion_failure", error.code, error.message,
                ))
            elif error.reason in _LOWERING_FAILURE_REASONS:
                outcomes.append(TestOutcome(
                    name, package_name, "compile_error", error.code, error.message,
                ))
            else:
                outcomes.append(TestOutcome(
                    name, package_name, "runtime_error", error.code, error.message,
                ))
            continue

        outcomes.append(TestOutcome(name, package_name, "pass"))

    return outcomes, 0


def _report(outcomes: list[TestOutcome], output_format: str) -> int:
    if output_format == "json":
        _report_json(outcomes)
    elif output_format == "junit":
        _report_junit(outcomes)
    else:
        _report_text(outcomes)
    return 3 if any(not outcome.passed for outcome in outcomes) else 0


def _report_text(outcomes: list[TestOutcome]) -> None:
    passed = [outcome for outcome in outcomes if outcome.passed]
    failed = [outcome for outcome in outcomes if not outcome.passed]
    for outcome in passed:
        print(f"PASS  {outcome.name}")
    for outcome in failed:
        print(f"FAIL  {outcome.name} [{outcome.status}]")
        print(f"      {outcome.code}: {outcome.message}")

    print()
    print(f"{len(passed)} passed")
    print(f"{len(failed)} failed")


def _outcome_dict(outcome: TestOutcome) -> dict[str, Any]:
    return {
        "name": outcome.name,
        "package": outcome.package,
        "status": outcome.status,
        "code": outcome.code,
        "message": outcome.message,
    }


def _report_json(outcomes: list[TestOutcome]) -> None:
    passed = sum(1 for outcome in outcomes if outcome.passed)
    failed = len(outcomes) - passed
    print(json.dumps(
        {
            "schema": "reasonscript-test-report/1.0",
            "tests": [_outcome_dict(outcome) for outcome in outcomes],
            "summary": {"passed": passed, "failed": failed, "total": len(outcomes)},
        },
        indent=2,
    ))


def _report_junit(outcomes: list[TestOutcome]) -> None:
    failed = sum(1 for outcome in outcomes if not outcome.passed)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<testsuite name="reason-test" tests="{len(outcomes)}" failures="{failed}">',
    ]
    for outcome in outcomes:
        package_attr = _xml_escape(outcome.package)
        name_attr = _xml_escape(outcome.name)
        if outcome.passed:
            lines.append(
                f'  <testcase classname="{package_attr}" name="{name_attr}"/>'
            )
            continue
        message = _xml_escape(f"{outcome.code}: {outcome.message}")
        lines.append(
            f'  <testcase classname="{package_attr}" name="{name_attr}">'
        )
        lines.append(
            f'    <failure message="{message}" type="{_xml_escape(outcome.status)}"/>'
        )
        lines.append('  </testcase>')
    lines.append('</testsuite>')
    print("\n".join(lines))


def _print_workspace_error(error: WorkspaceError) -> None:
    diagnostic = diagnostic_from_workspace_error(error)
    print(f"Error:\n\n{diagnostic.code}\n\n{diagnostic.message}")
