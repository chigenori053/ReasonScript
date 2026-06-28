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
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PYTEST_GROUPS = {
    "unit": [
        "ast_validation_tests",
        "binding_lowering_tests",
        "calculation_semantics_tests",
        "computation_model_tests",
        "frontend/parser_conformance",
        "frontend/compiler_conformance",
        "language_surface_ast_mapping_tests",
        "tests",
    ],
    "integration": [
        "calculation_integration_tests",
        "execution_architecture_phase1_tests",
        "execution_architecture_phase2_tests",
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

RUST_CRATES = [
    "HybridRuntime",
    "RuntimeReal",
    "RuntimeComplex",
    "Test",
    "TestPlayground",
    "apps/reasonscript-ide/src-tauri",
]

RUST_TEST_CRATES = [
    "apps/reasonscript-ide/src-tauri",
]

NPM_PROJECTS = [
    "playground/frontend",
    "apps/reasonscript-ide/ui",
]


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str]
    cwd: Path = ROOT
    optional: bool = False


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
        ],
    )
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(raw_args)

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
            + _pytest_steps("unit", passthrough)
            + _pytest_steps("integration", passthrough)
            + _pytest_steps("golden", passthrough)
            + _pytest_steps("compatibility", passthrough)
            + _pytest_steps("playground", passthrough)
        )
    if target == "release-check":
        return (
            _build_steps()
            + _steps_for("test", quick=quick, passthrough=passthrough)
            + _pytest_steps("regression", passthrough)
        )
    if target in PYTEST_GROUPS:
        return _pytest_steps(target, passthrough)
    raise AssertionError(f"unknown target: {target}")


def _pytest_steps(group: str, passthrough: list[str]) -> list[Step]:
    paths = [path for path in PYTEST_GROUPS[group] if (ROOT / path).exists()]
    return [
        Step(f"pytest:{group}:{path}", [sys.executable, "-m", "pytest", path, *passthrough])
        for path in paths
    ]


def _rust_test_steps() -> list[Step]:
    steps: list[Step] = []
    if _has("cargo"):
        for crate in RUST_TEST_CRATES:
            if (ROOT / crate / "Cargo.toml").exists():
                steps.append(Step(f"cargo:test:{crate}", ["cargo", "test"], ROOT / crate))
    return steps


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
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(ROOT))
    for step in steps:
        print(f"==> {step.name}: {' '.join(step.command)}", flush=True)
        result = subprocess.run(step.command, cwd=step.cwd, env=env)
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
