#!/usr/bin/env python3
"""Run the ReasonScript Semantic Language v0.2 Core freeze gate."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RELEASE_ROOT = Path(__file__).resolve().parent
MANIFEST = RELEASE_ROOT / "manifest.json"

COMMANDS = (
    (
        "scv_1",
        [
            "cargo",
            "test",
            "--manifest-path",
            "RuntimeReal/Cargo.toml",
            "--test",
            "scv_1_structural_constraint_validation",
        ],
    ),
    (
        "reasoning_space",
        [
            "cargo",
            "test",
            "--manifest-path",
            "RuntimeReal/Cargo.toml",
            "--test",
            "reasoning_space_validation",
        ],
    ),
    (
        "ssv_1",
        [
            "cargo",
            "test",
            "--manifest-path",
            "RuntimeReal/Cargo.toml",
            "--test",
            "ssv_1_semantic_simulation_validation",
        ],
    ),
    (
        "kev_1",
        [
            "cargo",
            "test",
            "--manifest-path",
            "RuntimeReal/Cargo.toml",
            "--test",
            "kev_1_knowledge_emergence_validation",
        ],
    ),
    (
        "core",
        [
            "cargo",
            "test",
            "--manifest-path",
            "RuntimeReal/Cargo.toml",
            "--test",
            "semantic_language_v02_core_validation",
        ],
    ),
    (
        "runtime_regression",
        [
            "cargo",
            "test",
            "--manifest-path",
            "RuntimeReal/Cargo.toml",
            "--",
            "--skip",
            "vs2_scaling_benchmarks",
        ],
    ),
)


def run(name: str, command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    output = completed.stdout + completed.stderr
    count = sum(
        int(value) for value in re.findall(r"test result: ok\. (\d+) passed", output)
    )
    result: dict[str, Any] = {
        "name": name,
        "status": "pass" if completed.returncode == 0 else "fail",
        "command": command,
        "test_count": count,
    }
    if completed.returncode != 0:
        result["output"] = output.strip()
    return result


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    release = manifest["release"]
    if release["version"] != "reasonscript-semantic-language/0.2":
        failures.append("semantic language version changed")
    if release["status"] != "core_frozen":
        failures.append("release status is not core_frozen")
    if release["date"] != "2026-06-15":
        failures.append("freeze date changed")

    expected_concepts = [
        "SemanticUnit",
        "SemanticRelation",
        "SCV-1",
        "Reasoning Space",
        "SemanticPlan",
        "SemanticSimulation",
        "SimulationResult",
        "Knowledge",
    ]
    if manifest["frozen_concepts"] != expected_concepts:
        failures.append("frozen concept set changed")

    for field in (
        "normative_specification",
        "validation_report",
        "release_gate",
    ):
        if not (ROOT / manifest[field]).is_file():
            failures.append(f"missing release artifact: {manifest[field]}")
    for artifact in manifest["artifacts"]:
        if not (ROOT / artifact).is_file():
            failures.append(f"missing frozen artifact: {artifact}")
    return failures


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures = validate_manifest(manifest)
    results = [run(name, command) for name, command in COMMANDS]
    expected = manifest["release_gates"]
    expected_counts = {
        "scv_1": expected["scv_1_tests"],
        "reasoning_space": expected["reasoning_space_tests"],
        "ssv_1": expected["ssv_1_tests"],
        "kev_1": expected["kev_1_tests"],
        "core": expected["core_tests"],
        "runtime_regression": expected["runtime_regression_tests"],
    }

    for result in results:
        if result["status"] != "pass":
            failures.append(f"{result['name']} validation failed")
        if result["test_count"] != expected_counts[result["name"]]:
            failures.append(
                f"{result['name']} expected {expected_counts[result['name']]} "
                f"tests, found {result['test_count']}"
            )

    report = {
        "release_version": manifest["release"]["version"],
        "validated_on": date.today().isoformat(),
        "status": "pass" if not failures else "fail",
        "failures": failures,
        "results": results,
    }
    reports = RELEASE_ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "release_validation_results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    for result in results:
        print(
            f"{result['name']}: {result['status'].upper()} "
            f"({result['test_count']} tests)"
        )
    print(f"semantic-language-v0.2-core: {report['status'].upper()}")
    for failure in failures:
        print(f"failure: {failure}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
