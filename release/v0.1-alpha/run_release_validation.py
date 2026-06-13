#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RELEASE_ROOT = Path(__file__).resolve().parent
MANIFEST = RELEASE_ROOT / "manifest.json"
GENERATED_REPORTS = [
    ROOT / "conformance" / "reports" / "conformance_results_v0.1.json",
    ROOT / "conformance" / "reports" / "Conformance_Report_v0.1.md",
    ROOT / "frontend" / "conformance" / "reports" / "ast_conformance_results_v0.1.json",
    ROOT
    / "frontend"
    / "parser_conformance"
    / "reports"
    / "parser_conformance_results_v0.1.json",
    ROOT
    / "frontend"
    / "compiler_conformance"
    / "reports"
    / "compiler_conformance_results_v0.1.json",
]

COMMANDS = [
    (
        "hybrid_runtime",
        ["cargo", "test", "--manifest-path", "HybridRuntime/Cargo.toml"],
    ),
    (
        "ast_validation",
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "ast_validation_tests",
            "-p",
            "test_*.py",
            "-v",
        ],
    ),
    ("platform_conformance", [sys.executable, "conformance/run_conformance.py"]),
    (
        "ast_conformance",
        [sys.executable, "frontend/conformance/run_conformance.py"],
    ),
    (
        "parser_conformance",
        [sys.executable, "frontend/parser_conformance/run_conformance.py"],
    ),
    (
        "compiler_conformance",
        [sys.executable, "frontend/compiler_conformance/run_conformance.py"],
    ),
]


def run(name: str, command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True
    )
    output = completed.stdout + completed.stderr
    cargo_count = sum(
        int(value) for value in re.findall(r"test result: ok\. (\d+) passed", output)
    )
    unittest_counts = [
        int(value) for value in re.findall(r"Ran (\d+) tests?", output)
    ]
    reported_command = [
        "python3" if item == sys.executable else item for item in command
    ]
    result = {
        "name": name,
        "status": "pass" if completed.returncode == 0 else "fail",
        "command": reported_command,
        "test_count": cargo_count or sum(unittest_counts),
    }
    if completed.returncode != 0:
        result["output"] = output.strip()
    return result


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if (ROOT / "VERSION").read_text(encoding="utf-8").strip() != manifest["release"]["version"]:
        failures.append("VERSION does not match release manifest")
    expected_interfaces = {
        "reason_ir": "reason-ir/0.1",
        "ast": "reasonscript-ast/0.1",
        "parser": "parser/0.1",
        "compiler": "compiler/0.1",
        "transaction": "transaction/0.1",
        "common_dto": "common-dto/0.1",
        "conformance_framework": "conformance-framework/0.1",
    }
    if manifest["interfaces"] != expected_interfaces:
        failures.append("fixed interface identifiers changed")
    for artifact in manifest["artifacts"]:
        if not (ROOT / artifact).is_file():
            failures.append(f"missing release artifact: {artifact}")
    return failures


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest_failures = validate_manifest(manifest)
    preserved_reports = {
        path: path.read_bytes() for path in GENERATED_REPORTS if path.exists()
    }
    try:
        results = [run(name, command) for name, command in COMMANDS]
    finally:
        for path, content in preserved_reports.items():
            path.write_bytes(content)
    by_name = {item["name"]: item for item in results}
    expected = manifest["release_gates"]
    gate_failures = list(manifest_failures)
    if by_name["hybrid_runtime"]["test_count"] != expected["hybrid_runtime_tests"]:
        gate_failures.append("HybridRuntime test count does not equal 121")
    if by_name["ast_validation"]["test_count"] != expected["ast_validation_tests"]:
        gate_failures.append("AST validation test count does not equal 12")
    if any(item["status"] != "pass" for item in results):
        gate_failures.append("one or more release validation commands failed")

    report = {
        "release_version": manifest["release"]["version"],
        "validated_on": date.today().isoformat(),
        "status": "pass" if not gate_failures else "fail",
        "failures": gate_failures,
        "results": results,
    }
    reports = RELEASE_ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "release_validation_results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for item in results:
        count = f" ({item['test_count']} tests)" if item["test_count"] else ""
        print(f"{item['name']}: {item['status'].upper()}{count}")
    print(f"release: {report['status'].upper()}")
    for failure in gate_failures:
        print(f"failure: {failure}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
