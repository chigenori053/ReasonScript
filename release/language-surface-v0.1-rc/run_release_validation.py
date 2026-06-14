#!/usr/bin/env python3
"""Run the Language Surface Core v0.1 RC release gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUITES = (
    "language_surface_ast_mapping_tests",
    "expression_pattern_tests",
    "statement_tests",
    "calculation_integration_tests",
    "language_surface_core_conformance_tests",
)


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    for suite in SUITES:
        run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                suite,
                "-p",
                "test_*.py",
                "-t",
                ".",
            ]
        )
    run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            ".",
            "-p",
            "test_*.py",
            "-t",
            ".",
        ]
    )
    run(["cargo", "test", "--manifest-path", "HybridRuntime/Cargo.toml"])
    print("Language Surface Core v0.1 RC release gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
