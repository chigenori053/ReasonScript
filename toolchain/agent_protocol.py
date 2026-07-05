"""Agent Development Protocol validation and reporting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from toolchain.artifacts import stable_json
from toolchain.diagnostics import diagnostic_from_parts, diagnostics_document


PROTOCOL_SCHEMA = "reasonscript-agent-protocol/1.0"
REPORT_SCHEMA = "reasonscript-agent-report/1.0"
VALID_STATES = ("DRAFT", "IN_PROGRESS", "IMPLEMENTED", "VALIDATED", "COMPLETED", "REJECTED")


def validate_repository(root: Path) -> dict[str, Any]:
    diagnostics = []
    if not _has_specification(root):
        diagnostics.append(_diagnostic("AP-001", "Missing specification", file="docs/specifications"))
    if not _has_validation(root):
        diagnostics.append(_diagnostic("AP-002", "Missing validation", file="tests"))
    if not _has_artifacts(root):
        diagnostics.append(_diagnostic("AP-003", "Missing artifacts", file="artifacts"))
    document = diagnostics_document(diagnostics)
    return {
        "schema": PROTOCOL_SCHEMA,
        "ok": len(document["diagnostics"]) == 0,
        "rules": ["AP-001", "AP-002", "AP-003"],
        "diagnostics": document["diagnostics"],
    }


def agent_report(
    *,
    task: str = "Phase 7.5",
    status: str = "VALIDATED",
    tests_passed: int = 0,
    artifacts_generated: bool = False,
) -> dict[str, Any]:
    normalized_status = status.upper()
    if normalized_status not in VALID_STATES:
        normalized_status = "REJECTED"
    return {
        "schema": REPORT_SCHEMA,
        "task": task,
        "status": normalized_status,
        "tests_passed": tests_passed,
        "artifacts_generated": artifacts_generated,
    }


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


def _diagnostic(code: str, message: str, *, file: str) -> dict[str, Any]:
    return diagnostic_from_parts(
        code=code,
        severity="ERROR",
        category="AgentProtocol",
        message=message,
        file=file,
        metadata={"rule": code},
    ).to_dict()
