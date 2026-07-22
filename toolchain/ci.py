"""Canonical CI Stabilization pipeline for reasonscript-ci/1.0."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from toolchain.agent_protocol import PROTOCOL_SCHEMA, validate_repository
from toolchain.artifacts import ARTIFACT_SCHEMA, ARTIFACT_SCHEMAS, stable_json, unwrap_artifact, validate_artifact_directory
from toolchain.diagnostics import DIAGNOSTICS_SCHEMA, diagnostic_from_parts, diagnostics_document, validate_diagnostics_document
from toolchain.golden import GOLDEN_SCHEMA, run_corpus
from toolchain.phase8_golden_validation import CONTRACT_SCHEMA as PHASE8_GOLDEN_SCHEMA
from toolchain.phase8_golden_validation import validate_phase8_golden
from toolchain.reasoning_evaluation_report import CONTRACT_SCHEMA as REASONING_EVALUATION_SCHEMA
from toolchain.reasoning_model_contract import CONTRACT_SCHEMA as REASONING_MODEL_SCHEMA
from toolchain.reasoning_runtime import CONTRACT_SCHEMA as REASONING_RUNTIME_SCHEMA
from toolchain.workspace_foundation import WORKSPACE_SCHEMA, build_workspace_index
from playground.backend.reasoning_overview import CONTRACT_SCHEMA as REASONING_OVERVIEW_SCHEMA
from toolchain.version_validation import validate_version


CI_SCHEMA = "reasonscript-ci/1.0"
REPORT_SCHEMA = "reasonscript-ci-report/1.0"
SUMMARY_SCHEMA = "reasonscript-ci-summary/1.0"

PHASE_ORDER = (
    "checkout",
    "environment_setup",
    "workspace",
    "diagnostics",
    "artifacts",
    "golden",
    "agent_protocol",
    "compatibility",
    "tests",
)

VALIDATION_RULES = (
    "CI-001",
    "CI-002",
    "CI-003",
    "CI-004",
    "CI-005",
    "CI-006",
    "CI-007",
    "CI-008",
    "CI-009",
    "CI-010",
)

REQUIRED_WORKFLOW_FILES = (
    "test.yml",
    "ci.yml",
)

COMPATIBILITY_TARGETS = {
    "reasonscript-workspace/1.0": lambda: WORKSPACE_SCHEMA == "reasonscript-workspace/1.0",
    "reasonscript-diagnostics/1.0": lambda: DIAGNOSTICS_SCHEMA == "reasonscript-diagnostics/1.0",
    "reasonscript-artifacts/1.0": lambda: ARTIFACT_SCHEMA == "reasonscript-artifacts/1.0",
    "reasonscript-golden-tests/1.0": lambda: GOLDEN_SCHEMA == "reasonscript-golden-tests/1.0",
    "reasonscript-agent-protocol/1.0": lambda: PROTOCOL_SCHEMA == "reasonscript-agent-protocol/1.0",
    "reason-ir/0.5": lambda: ARTIFACT_SCHEMAS.get("reason_ir.json") == "reason-ir/0.5",
    "execution-plan/0.5": lambda: ARTIFACT_SCHEMAS.get("execution_plan.json") == "execution-plan/0.5",
    "simulation/0.5": lambda: ARTIFACT_SCHEMAS.get("simulation.json") == "simulation/0.5",
    "knowledge/0.5": lambda: ARTIFACT_SCHEMAS.get("knowledge.json") == "knowledge/0.5",
    "reasonscript-reasoning-model/1.0": lambda: REASONING_MODEL_SCHEMA == "reasonscript-reasoning-model/1.0",
    "reasonscript-reasoning-evaluation-report/1.0": lambda: REASONING_EVALUATION_SCHEMA == "reasonscript-reasoning-evaluation-report/1.0",
    "reasonscript-reasoning-runtime-prototype/1.0": lambda: REASONING_RUNTIME_SCHEMA == "reasonscript-reasoning-runtime-prototype/1.0",
    "reasonscript-playground-reasoning-overview/1.0": lambda: REASONING_OVERVIEW_SCHEMA == "reasonscript-playground-reasoning-overview/1.0",
    "reasonscript-phase8-golden-validation/1.0": lambda: PHASE8_GOLDEN_SCHEMA == "reasonscript-phase8-golden-validation/1.0",
    "reasonscript-vision-runtime/0.1": lambda: __import__("toolchain.vision_runtime_cmd", fromlist=["PROFILE"]).PROFILE == "reasonscript-vision-runtime/0.1",
    "reasonscript-vision-language-integration/0.1": lambda: __import__("frontend.vision.contracts", fromlist=["PROFILE"]).PROFILE == "reasonscript-vision-language-integration/0.1",
    "reasonscript-vision-install-distribution/0.1": lambda: __import__("toolchain.distribution_validation", fromlist=["VISION_DISTRIBUTION_PROFILE"]).VISION_DISTRIBUTION_PROFILE == "reasonscript-vision-install-distribution/0.1",
}

DEFAULT_TEST_COMMAND = (sys.executable, "-m", "pytest", "tests", "-q")


def run_pipeline(root: Path, *, run_tests: bool = True, test_command: tuple[str, ...] = DEFAULT_TEST_COMMAND) -> dict[str, Any]:
    phases: list[dict[str, Any]] = []
    diagnostics: list[Any] = []
    failed = False
    tests_passed = 0

    def execute(phase_id: str, checker) -> None:
        nonlocal failed
        if failed:
            phases.append({"id": phase_id, "status": "SKIPPED", "diagnostics": []})
            return
        ok, phase_diagnostics, metadata = checker()
        diagnostics.extend(phase_diagnostics)
        entry: dict[str, Any] = {
            "id": phase_id,
            "status": "PASS" if ok else "FAIL",
            "diagnostics": [item.to_dict() for item in phase_diagnostics],
        }
        if metadata:
            entry["metadata"] = metadata
        phases.append(entry)
        if not ok:
            failed = True

    execute("checkout", lambda: _check_checkout(root))
    execute("environment_setup", lambda: _check_environment_setup(root))
    execute("workspace", _check_workspace)
    execute("diagnostics", lambda: _check_diagnostics(root))
    execute("artifacts", lambda: _check_artifacts(root))
    execute("golden", lambda: _check_golden(root))
    execute("agent_protocol", lambda: _check_agent_protocol(root))
    execute("compatibility", _check_compatibility)

    def _tests_checker():
        nonlocal tests_passed
        ok, phase_diagnostics, metadata, count = _check_tests(root, run_tests=run_tests, test_command=test_command)
        tests_passed = count
        return ok, phase_diagnostics, metadata

    execute("tests", _tests_checker)

    document = diagnostics_document(diagnostics)
    ok = not failed
    return {
        "schema": CI_SCHEMA,
        "ok": ok,
        "rules": list(VALIDATION_RULES),
        "phases": phases,
        "diagnostics": document["diagnostics"],
        "tests_passed": tests_passed,
    }


def ci_report(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": "1.0",
        "schema": REPORT_SCHEMA,
        "status": "PASS" if result["ok"] else "FAIL",
        "phases": result["phases"],
        "diagnostics": result["diagnostics"],
    }


def ci_summary(result: dict[str, Any]) -> dict[str, Any]:
    phase_status = {phase["id"]: phase["status"] == "PASS" for phase in result["phases"]}
    return {
        "version": "1.0",
        "schema": SUMMARY_SCHEMA,
        "status": "PASS" if result["ok"] else "FAIL",
        "workspace": phase_status.get("workspace", False),
        "diagnostics": phase_status.get("diagnostics", False),
        "artifacts": phase_status.get("artifacts", False),
        "golden": phase_status.get("golden", False),
        "agent_protocol": phase_status.get("agent_protocol", False),
        "tests": result["tests_passed"],
    }


def write_ci_reports(directory: Path, result: dict[str, Any]) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    report_path = directory / "ci_report.json"
    summary_path = directory / "ci_summary.json"
    report_path.write_text(stable_json(ci_report(result)), encoding="utf-8")
    summary_path.write_text(stable_json(ci_summary(result)), encoding="utf-8")
    return {"report": report_path, "summary": summary_path}


def _check_checkout(root: Path) -> tuple[bool, list[Any], dict[str, Any] | None]:
    workflow_dir = root / ".github" / "workflows"
    has_workflow = workflow_dir.is_dir() and any((workflow_dir / name).is_file() for name in REQUIRED_WORKFLOW_FILES)
    if not root.is_dir():
        return False, [_ci_diag("CI-002", f"Repository root not found: {root}", file=str(root))], None
    if not has_workflow:
        return False, [_ci_diag("CI-001", "Missing workflow", file=".github/workflows")], None
    return True, [], {"root": str(root)}


def _check_environment_setup(root: Path) -> tuple[bool, list[Any], dict[str, Any] | None]:
    version = validate_version(root)
    ok = sys.version_info >= (3, 9) and version["status"] == "pass"
    metadata = {"python_version": sys.version.split()[0], "version_validation": version}
    if not ok:
        message = "Unsupported Python runtime" if sys.version_info < (3, 9) else "Release version metadata mismatch"
        return False, [_ci_diag("CI-002", message, file="environment")], metadata
    return True, [], metadata


def _check_workspace() -> tuple[bool, list[Any], dict[str, Any] | None]:
    with tempfile.TemporaryDirectory(prefix="reasonscript-ci-workspace-") as tmp:
        project = _write_canonical_workspace_project(Path(tmp))
        index = build_workspace_index(project)
    errors = [
        item for item in index.get("diagnostics", [])
        if isinstance(item, dict) and str(item.get("severity", "")).upper() == "ERROR"
    ]
    metadata = {"schema": index.get("schema"), "files": len(index.get("files", []))}
    if errors or index.get("schema") != WORKSPACE_SCHEMA:
        return False, [_ci_diag("CI-003", "Workspace validation failed", file="workspace")], metadata
    return True, [], metadata


def _write_canonical_workspace_project(root: Path) -> Path:
    root.joinpath("reason.toml").write_text(
        "\n".join([
            'name = "CIWorkspaceSample"',
            'version = "0.5.0"',
            'language = "0.5"',
            'workspace = "1.0"',
            'edition = "2026"',
            "",
        ]),
        encoding="utf-8",
    )
    src = root / "src"
    src.mkdir()
    src.joinpath("main.rsn").write_text(
        "\n".join([
            "module Main {",
            "  fn Value() -> int {",
            "    return 42",
            "  }",
            "  calculation Answer {",
            "    result = Value()",
            "  }",
            "}",
            "",
        ]),
        encoding="utf-8",
    )
    return root


def _check_diagnostics(root: Path) -> tuple[bool, list[Any], dict[str, Any] | None]:
    diagnostics: list[Any] = []
    checked = 0
    for base in (root / "artifacts", root / "golden"):
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("diagnostics.json")):
            checked += 1
            try:
                value = unwrap_artifact(_read_json(path))
            except ValueError:
                diagnostics.append(_ci_diag("CI-004", f"Malformed diagnostics document: {path}", file=str(path)))
                continue
            issues = validate_diagnostics_document(value)
            if issues:
                diagnostics.append(_ci_diag("CI-004", f"Diagnostics validation failed: {path}", file=str(path)))
    return not diagnostics, diagnostics, {"checked": checked}


def _check_artifacts(root: Path) -> tuple[bool, list[Any], dict[str, Any] | None]:
    diagnostics: list[Any] = []
    checked = 0
    for base in (root / "artifacts", root / "golden"):
        if not base.is_dir():
            continue
        for manifest in sorted(base.rglob("artifact_manifest.json")):
            checked += 1
            document = validate_artifact_directory(manifest.parent)
            if document["diagnostics"]:
                diagnostics.append(_ci_diag("CI-005", f"Artifact validation failed: {manifest.parent}", file=str(manifest.parent)))
    return not diagnostics, diagnostics, {"checked": checked}


def _check_golden(root: Path) -> tuple[bool, list[Any], dict[str, Any] | None]:
    golden_root = root / "golden"
    if not golden_root.is_dir():
        return False, [_ci_diag("CI-006", "Golden test failed", file="golden")], None
    result = run_corpus(golden_root)
    phase8 = validate_phase8_golden(root)
    summary = result["summary"]
    metadata = {
        **summary,
        "phase8_golden_validation": {
            "target": PHASE8_GOLDEN_SCHEMA,
            "status": phase8["status"],
            "scenarios": len(phase8["scenarios"]),
        },
    }
    if summary["failed"] or not phase8["ok"]:
        return False, [_ci_diag("CI-006", "Golden test failed", file="golden")], metadata
    return True, [], metadata


def _check_agent_protocol(root: Path) -> tuple[bool, list[Any], dict[str, Any] | None]:
    result = validate_repository(root)
    if not result["ok"]:
        return False, [_ci_diag("CI-007", "Agent protocol violation", file="AGENTS.md")], None
    return True, [], None


def _check_compatibility() -> tuple[bool, list[Any], dict[str, Any] | None]:
    failures = [target for target, check in COMPATIBILITY_TARGETS.items() if not check()]
    if failures:
        return False, [_ci_diag("CI-009", f"Compatibility failure: {', '.join(failures)}", file="docs/specifications")], None
    return True, [], {"targets": len(COMPATIBILITY_TARGETS)}


def _check_tests(root: Path, *, run_tests: bool, test_command: tuple[str, ...]) -> tuple[bool, list[Any], dict[str, Any] | None, int]:
    if not run_tests:
        return True, [], {"skipped": True}, 0
    try:
        completed = subprocess.run(test_command, cwd=root, text=True, capture_output=True, check=False)
    except OSError as error:
        return False, [_ci_diag("CI-008", f"Test failure: {error}", file="tests")], None, 0
    count = _parse_passed_count(completed.stdout)
    if completed.returncode != 0:
        return False, [_ci_diag("CI-008", "Test failure", file="tests")], {"tests_passed": count}, count
    return True, [], {"tests_passed": count}, count


def _parse_passed_count(output: str) -> int:
    match = re.search(r"(\d+) passed", output)
    return int(match.group(1)) if match else 0


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(str(error)) from error


def _ci_diag(code: str, message: str, *, file: str) -> Any:
    return diagnostic_from_parts(
        code=code,
        severity="ERROR",
        category="Compatibility" if code == "CI-009" else "CLI",
        message=message,
        file=file,
        metadata={"rule": code},
    )
