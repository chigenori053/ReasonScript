"""Agent Development Protocol validation and reporting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import json

from toolchain.artifacts import stable_json, validate_artifact_directory
from toolchain.diagnostics import diagnostic_from_parts, diagnostics_document
from toolchain.golden import run_corpus


PROTOCOL_SCHEMA = "reasonscript-agent-protocol/1.0"
REPORT_SCHEMA = "reasonscript-agent-report/1.0"
VALID_STATES = ("DRAFT", "IN_PROGRESS", "IMPLEMENTED", "VALIDATED", "COMPLETED", "REJECTED")
REQUIRED_COMMANDS = (
    "reason check",
    "reason analyze",
    "reason run",
    "reason artifacts",
    "reason validate-artifacts",
    "reason golden",
)
VALIDATION_RULES = (
    "AP-001",
    "AP-002",
    "AP-003",
    "AP-004",
    "AP-005",
    "AP-006",
    "AP-007",
    "AP-008",
    "AP-009",
    "AP-010",
)


def validate_repository(root: Path) -> dict[str, Any]:
    diagnostics = []
    if not _has_specification(root):
        diagnostics.append(_diagnostic("AP-001", "Missing specification", file="docs/specifications"))
    if not _has_validation(root):
        diagnostics.append(_diagnostic("AP-002", "Missing validation", file="tests"))
    if not _has_artifacts(root):
        diagnostics.append(_diagnostic("AP-003", "Missing artifacts", file="artifacts"))
    if not _golden_passes(root):
        diagnostics.append(_diagnostic("AP-004", "Golden failure", file="golden"))
    diagnostics.extend(_report_diagnostics(root / "agent_report.json"))
    if not _protocol_documented(root):
        diagnostics.append(_diagnostic("AP-007", "Protocol violation", file="AGENTS.md"))
    diagnostics.extend(_artifact_diagnostics(root))
    if not _has_compatibility_record(root):
        diagnostics.append(_diagnostic("AP-010", "Unrecorded compatibility change", file="docs/changelog"))
    document = diagnostics_document(diagnostics)
    return {
        "schema": PROTOCOL_SCHEMA,
        "ok": len(document["diagnostics"]) == 0,
        "rules": list(VALIDATION_RULES),
        "diagnostics": document["diagnostics"],
    }


def agent_report(
    *,
    task: str = "Phase 7.5",
    status: str = "VALIDATED",
    tests_passed: int = 0,
    artifacts_generated: bool = False,
    commands_executed: tuple[str, ...] = REQUIRED_COMMANDS,
) -> dict[str, Any]:
    normalized_status = status.upper()
    if normalized_status not in VALID_STATES:
        normalized_status = "REJECTED"
    return {
        "version": "1.0",
        "schema": REPORT_SCHEMA,
        "task": task,
        "status": normalized_status,
        "tests_passed": tests_passed,
        "artifacts_generated": artifacts_generated,
        "commands_executed": list(commands_executed),
    }


def write_agent_report(directory: Path, report: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "agent_report.json"
    path.write_text(stable_json(report), encoding="utf-8")
    return path


def render_json(value: dict[str, Any]) -> str:
    return stable_json(value)


def _has_specification(root: Path) -> bool:
    candidates = [
        root / "docs" / "specifications" / "ReasonScript_Agent_Development_Protocol_v1_0.md",
        root / "SPECIFICATIONS",
    ]
    return any(path.exists() for path in candidates)


def _has_validation(root: Path) -> bool:
    tests = root / "tests"
    return tests.is_dir() and any(tests.rglob("test*.py"))


def _has_artifacts(root: Path) -> bool:
    return (root / "golden").is_dir() and (root / "artifacts").is_dir()


def _golden_passes(root: Path) -> bool:
    golden = root / "golden"
    if not golden.is_dir():
        return False
    try:
        result = run_corpus(golden)
    except Exception:
        return False
    summary = result.get("summary")
    return isinstance(summary, dict) and summary.get("failed") == 0


def _report_diagnostics(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [_diagnostic("AP-006", "Incomplete completion report", file="agent_report.json")]
    diagnostics: list[dict[str, Any]] = []
    status = report.get("status")
    if status not in VALID_STATES:
        diagnostics.append(_diagnostic("AP-005", "Invalid task state", file="agent_report.json"))
    required = {"version", "task", "status", "tests_passed", "artifacts_generated"}
    if not required.issubset(report):
        diagnostics.append(_diagnostic("AP-006", "Incomplete completion report", file="agent_report.json"))
    commands = report.get("commands_executed")
    if isinstance(commands, list):
        missing = [command for command in REQUIRED_COMMANDS if command not in commands]
        if missing:
            diagnostics.append(_diagnostic("AP-009", "Required command skipped", file="agent_report.json"))
    return diagnostics


def _protocol_documented(root: Path) -> bool:
    agents = root / "AGENTS.md"
    if not agents.is_file():
        return False
    text = agents.read_text(encoding="utf-8")
    return all(
        fragment in text
        for fragment in (
            "Specification",
            "Implementation",
            "Validation",
            "Artifact verification",
            "Golden tests",
            "Completion report",
        )
    )


def _artifact_diagnostics(root: Path) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for base in (root / "artifacts", root / "golden"):
        if not base.is_dir():
            continue
        for manifest in sorted(base.glob("**/artifact_manifest.json")):
            document = validate_artifact_directory(manifest.parent)
            if document["diagnostics"]:
                diagnostics.append(_diagnostic("AP-008", "Manual artifact modification", file=str(manifest.parent)))
    return diagnostics


def _has_compatibility_record(root: Path) -> bool:
    return (root / "docs" / "changelog" / "phase7_5_agent_development_protocol.md").is_file()


def _diagnostic(code: str, message: str, *, file: str) -> dict[str, Any]:
    return diagnostic_from_parts(
        code=code,
        severity="ERROR",
        category="AgentProtocol",
        message=message,
        file=file,
        metadata={"rule": code},
    ).to_dict()
