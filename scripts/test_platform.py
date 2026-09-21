#!/usr/bin/env python3
"""ReasonScript Test Platform command runner.

This script provides the stable local and CI entry point required by
reasonscript-test-platform/1.1 while delegating to the repository's existing
Rust, Python, and frontend test suites.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import test_environment  # noqa: E402  (one place for every environment decision)

PYTEST_GROUPS = {
    "unit": [
        "ast_validation_tests",
        "binding_lowering_tests",
        "calculation_semantics_tests",
        "computation_model_tests",
        "computation_ir_tests",
        "decision_transition_tests",
        "dependency_graph_tests",
        "execution_plan_tests",
        "expression_lowering_tests",
        "expression_pattern_tests",
        "frontend/parser_conformance",
        "frontend/compiler_conformance",
        "language_spec_validation_tests",
        "language_surface_ast_mapping_tests",
        "language_surface_core_conformance_tests",
        "namespace_import_resolution_tests",
        "operational_semantics_tests",
        "output_policy_tests",
        "result_state_tests",
        "runtime_completeness_tests",
        "runtime_io_tests",
        "statement_tests",
        "tensor_standard_functions_tests",
        "type_specification_tests",
        "tests",
    ],
    "integration": [
        "agent_layer_phase1_tests",
        "calculation_integration_tests",
        "code_viewer_phase1_tests",
        "computation_ir_tests/test_native_causal_bridge.py",
        "computation_ir_tests/test_native_state_causality.py",
        "execution_architecture_phase1_tests",
        "execution_architecture_phase2_tests",
        "ide_phase1_tests",
        "lsp_phase1_tests",
        "planning_sdk_phase1_tests",
        "platform_phase7_tests",
        "platform_phase8_tests",
        "playground_integration_tests",
        "runtime_integration_phase1_tests",
        "runtime_integration_phase2_tests",
        "runtime_integration_phase3_tests",
        "runtime_integration_phase4_tests",
        "sdk_phase1_tests",
        "toolchain_phase1_tests",
        "toolchain_phase2_tests",
        "vscode_extension_phase1_tests",
        "vscode_extension_phase1_3_tests",
        "vscode_extension_phase1_4_tests",
        "world_sdk_phase1_tests",
    ],
    "regression": [
        "language_surface_release_tests",
        "runtime_semantics_validation_tests",
        "tests",
    ],
    "golden": ["tests/golden"],
    "compatibility": [
        "tests/compatibility",
        "conformance/schema_conformance_tests",
    ],
    "playground": [
        "tests/playground",
        "playground_integration_tests",
    ],
}

# Targets that run the environment-dependent test groups.
PREFLIGHT_TARGETS = ("test", "release-check", "integration")

RUST_CRATES = [
    "HybridRuntime",
    "RuntimeReal",
    "Test",
    "TestPlayground",
    "apps/reasonscript-ide/src-tauri",
    "ReasonRuntime",
    "ClusterRuntime",
    "VisualizationRuntime",
]

RUST_TEST_CRATES = [
    "apps/reasonscript-ide/src-tauri",
    "ReasonRuntime",
]

NPM_PROJECTS = [
    "apps/reasonscript-ide/ui",
]


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str]
    cwd: Path = ROOT
    optional: bool = False
    env: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Requirement:
    """A dependency of the test plan: always required, or only under CI."""

    name: str
    ready: bool
    detail: str
    local_note: str  # what a local run does without it
    required_locally: bool = False


def preflight_requirements() -> list[Requirement]:
    extension = test_environment.vscode_extension_dir(ROOT)
    return [
        Requirement("Python", sys.version_info >= (3, 10), sys.version.split()[0], "", required_locally=True),
        Requirement("Rust", _has("cargo"), "cargo", "Rust tests are skipped"),
        Requirement("Node", _has("node"), "node", "VS Code extension tests are skipped"),
        Requirement("npm", _has("npm"), "npm", "VS Code extension tests are skipped"),
        Requirement(
            "VSCode deps",
            test_environment.has_vscode_dependencies(ROOT),
            f"{extension.name}/node_modules",
            f"VS Code extension tests are skipped; run `npm ci --prefix {extension.name}`",
        ),
    ]


def preflight(*, ci: bool | None = None, out=None) -> int:
    """Report what the test plan depends on; under CI a missing dependency fails before any test."""
    ci = test_environment.is_ci() if ci is None else ci
    out = out or sys.stdout
    failed = False
    print(f"Test environment preflight ({'CI' if ci else 'local'} mode)", file=out)
    for requirement in preflight_requirements():
        if requirement.ready:
            status = "READY"
        elif ci or requirement.required_locally:
            status, failed = "MISSING (required)" if not ci else "MISSING (required in CI)", True
        else:
            status = f"MISSING (local optional: {requirement.local_note})"
        print(f"  {requirement.name:<12} {status}", file=out)
    print("  Runtime host BUILT BY THE PLAN (cargo build --bin reason-runtime-host)", file=out)
    if failed:
        print("Preflight FAILED: declared dependencies are missing; install them before the test plan.", file=out)
    return 1 if failed else 0


def main() -> int:
    raw_args = sys.argv[1:]
    quick = "--quick" in raw_args
    raw_args = [arg for arg in raw_args if arg != "--quick"]
    parser = argparse.ArgumentParser(description="Run ReasonScript Test Platform tasks.")
    parser.add_argument(
        "target",
        choices=[
            "fmt",
            "lint",
            "test",
            "unit",
            "integration",
            "regression",
            "golden",
            "compatibility",
            "playground",
            "build",
            "release-check",
            "preflight",
        ],
    )
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(raw_args)

    if args.target == "preflight":
        return preflight()
    if args.target in PREFLIGHT_TARGETS and preflight():
        return 1
    steps = _steps_for(args.target, quick=quick, passthrough=args.pytest_args)
    return _run_steps(steps)


def _steps_for(target: str, *, quick: bool, passthrough: list[str]) -> list[Step]:
    if target == "fmt":
        return _fmt_steps()
    if target == "lint":
        return _lint_steps()
    if target == "build":
        return _build_steps()
    if target == "test":
        return (
            _rust_test_steps()
            + _pytest_steps_for_groups(
                ("unit", "integration", "regression", "golden", "compatibility", "playground"),
                passthrough,
            )
        )
    if target == "release-check":
        return _build_steps() + _steps_for("test", quick=quick, passthrough=passthrough)
    if target == "integration":
        return _native_runtime_host_build_steps() + _pytest_steps(target, passthrough)
    if target in PYTEST_GROUPS:
        return _pytest_steps(target, passthrough)
    raise AssertionError(f"unknown target: {target}")


def _pytest_steps(group: str, passthrough: list[str]) -> list[Step]:
    return _pytest_steps_for_groups((group,), passthrough)


def _pytest_steps_for_groups(groups: tuple[str, ...], passthrough: list[str]) -> list[Step]:
    """Build one complete pytest plan without running nested suites twice."""
    candidates = list(dict.fromkeys(
        path
        for group in groups
        for path in PYTEST_GROUPS[group]
        if (ROOT / path).exists()
    ))
    paths = [
        path
        for path in candidates
        if not any(
            other != path and Path(other) in Path(path).parents
            for other in candidates
        )
    ]
    if not paths:
        return []
    return [
        Step(
            f"pytest:{'+'.join(groups)}",
            [sys.executable, "-m", "pytest", *paths, *passthrough],
            env=_pytest_report_env(full_plan=not passthrough and "unit" in groups and "integration" in groups),
        )
    ]


def _pytest_report_env(*, full_plan: bool) -> dict[str, str]:
    """Skip classification and the CI skip guard (`scripts/test_report.py`) for pytest steps."""
    addopts = " ".join(part for part in (os.environ.get("PYTEST_ADDOPTS", ""), "-p scripts.test_report") if part)
    env = {"PYTEST_ADDOPTS": addopts}
    if full_plan:
        env["REASONSCRIPT_REQUIRE_MANDATORY"] = "1"
    return env


def _rust_test_steps() -> list[Step]:
    steps: list[Step] = []
    if _has("cargo"):
        for crate in RUST_TEST_CRATES:
            if (ROOT / crate / "Cargo.toml").exists():
                if crate == "ReasonRuntime":
                    steps.extend(_native_runtime_host_build_steps())
                steps.append(Step(f"cargo:test:{crate}", ["cargo", "test"], ROOT / crate))
    return steps


def _native_runtime_host_build_steps() -> list[Step]:
    runtime = ROOT / "ReasonRuntime"
    if not _has("cargo") or not (runtime / "Cargo.toml").exists():
        return []
    return [
        Step(
            "cargo:build:ReasonRuntime:reason-runtime-host",
            ["cargo", "build", "--bin", "reason-runtime-host"],
            runtime,
        )
    ]


def _fmt_steps(*, check_only: bool = False) -> list[Step]:
    steps: list[Step] = []
    if _has("cargo"):
        for crate in RUST_CRATES:
            if (ROOT / crate / "Cargo.toml").exists():
                command = ["cargo", "fmt"]
                if check_only:
                    command.append("--check")
                steps.append(Step(f"rustfmt:{crate}", command, ROOT / crate))
    if _has("black"):
        command = ["black", "."]
        if check_only:
            command.append("--check")
        steps.append(Step("black", command))
    return steps


def _lint_steps() -> list[Step]:
    steps: list[Step] = []
    if _has("cargo"):
        for crate in RUST_CRATES:
            if (ROOT / crate / "Cargo.toml").exists():
                steps.append(
                    Step(
                        f"clippy:{crate}",
                        [
                            "cargo",
                            "clippy",
                            "--all-targets",
                            "--",
                            "-A",
                            "warnings",
                            "-A",
                            "clippy::overly_complex_bool_expr",
                        ],
                        ROOT / crate,
                    )
                )
    if _has("ruff"):
        steps.append(Step("ruff", ["ruff", "check", "."]))
    if _has("mypy"):
        steps.append(Step("mypy", ["mypy", "frontend", "toolchain", "sdk"], optional=True))
    if _has("npm"):
        for project in NPM_PROJECTS:
            package_json = ROOT / project / "package.json"
            if not package_json.exists():
                continue
            if _has_npm_script(package_json, "lint"):
                steps.extend(_npm_install_steps(project))
                steps.append(
                    Step(
                        f"npm:lint:{project}",
                        ["npm", "run", "lint", "--", "--max-warnings=0"],
                        package_json.parent,
                    )
                )
            elif _has_npm_script(package_json, "build") and project == "apps/reasonscript-ide/ui":
                steps.extend(_npm_install_steps(project))
                steps.append(
                    Step(
                        f"npm:typecheck:{project}",
                        ["npm", "run", "build"],
                        package_json.parent,
                    )
                )
    return steps


def _build_steps() -> list[Step]:
    steps: list[Step] = []
    if _has("cargo"):
        for crate in RUST_CRATES:
            if (ROOT / crate / "Cargo.toml").exists():
                steps.append(Step(f"cargo:build:{crate}", ["cargo", "build"], ROOT / crate))
    if _has("npm"):
        for project in NPM_PROJECTS:
            package_json = ROOT / project / "package.json"
            if package_json.exists() and _has_npm_script(package_json, "build"):
                steps.extend(_npm_install_steps(project))
                steps.append(
                    Step(
                        f"npm:build:{project}",
                        ["npm", "run", "build"],
                        package_json.parent,
                    )
                )
    return steps


def _run_steps(steps: list[Step]) -> int:
    if not steps:
        print("No matching test-platform steps were found.")
        return 0
    base_env = os.environ.copy()
    base_env.setdefault("PYTHONPATH", str(ROOT))
    for step in steps:
        print(f"==> {step.name}: {' '.join(step.command)}", flush=True)
        result = subprocess.run(step.command, cwd=step.cwd, env={**base_env, **step.env})
        if result.returncode != 0:
            if step.optional:
                print(f"Optional step failed: {step.name}", file=sys.stderr)
                continue
            return result.returncode
    return 0


def _has(executable: str) -> bool:
    return shutil.which(executable) is not None


def _has_npm_script(package_json: Path, script: str) -> bool:
    with package_json.open("r", encoding="utf-8") as f:
        data = json.load(f)
    scripts = data.get("scripts", {})
    return isinstance(scripts, dict) and script in scripts


def _npm_install_steps(project: str) -> list[Step]:
    project_dir = ROOT / project
    if (project_dir / "package-lock.json").exists():
        return [Step(f"npm:ci:{project}", ["npm", "ci"], project_dir)]
    return [Step(f"npm:install:{project}", ["npm", "install"], project_dir)]


if __name__ == "__main__":
    raise SystemExit(main())
