"""Canonical CI entry point validation for reasonscript-ci-entry/1.0."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from toolchain.artifacts import stable_json
from toolchain.ci import CI_SCHEMA, PHASE_ORDER, REPORT_SCHEMA, SUMMARY_SCHEMA, ci_report, ci_summary, run_pipeline, write_ci_reports
from toolchain.diagnostics import diagnostic_from_parts, diagnostics_document


ENTRY_SCHEMA = "reasonscript-ci-entry/1.0"

VALIDATION_RULES = (
    "CE-001",
    "CE-002",
    "CE-003",
    "CE-004",
    "CE-005",
)

REQUIRED_CONTRACT_PHASES = (
    "workspace",
    "diagnostics",
    "artifacts",
    "golden",
    "agent_protocol",
    "compatibility",
)


def validate_entry_point(root: Path) -> dict[str, Any]:
    diagnostics: list[Any] = []

    if not _has_ci_pipeline(root):
        diagnostics.append(_diag("CE-001", "Missing CI pipeline", file="toolchain/ci.py"))
        document = diagnostics_document(diagnostics)
        return {
            "schema": ENTRY_SCHEMA,
            "ok": len(document["diagnostics"]) == 0,
            "rules": list(VALIDATION_RULES),
            "diagnostics": document["diagnostics"],
        }

    result = run_pipeline(root, run_tests=False)
    order = [phase["id"] for phase in result["phases"]]
    if order != list(PHASE_ORDER):
        diagnostics.append(_diag("CE-002", "Invalid execution order", file="toolchain/ci.py"))

    missing = [phase_id for phase_id in REQUIRED_CONTRACT_PHASES if phase_id not in PHASE_ORDER]
    if missing or not _has_entry_point_policy(root):
        diagnostics.append(_diag("CE-003", "Required validation omitted", file="AGENTS.md"))

    diagnostics.extend(_check_report_generation(result))
    diagnostics.extend(_check_fail_fast_semantics())

    document = diagnostics_document(diagnostics)
    return {
        "schema": ENTRY_SCHEMA,
        "ok": len(document["diagnostics"]) == 0,
        "rules": list(VALIDATION_RULES),
        "diagnostics": document["diagnostics"],
    }


def render_json(value: dict[str, Any]) -> str:
    return stable_json(value)


def _has_ci_pipeline(root: Path) -> bool:
    ci_module = root / "toolchain" / "ci.py"
    ci_cmd_module = root / "toolchain" / "ci_cmd.py"
    main_module = root / "toolchain" / "__main__.py"
    if not (ci_module.is_file() and ci_cmd_module.is_file() and main_module.is_file()):
        return False
    if CI_SCHEMA != "reasonscript-ci/1.0":
        return False
    return '"ci"' in main_module.read_text(encoding="utf-8")


def _has_entry_point_policy(root: Path) -> bool:
    agents = root / "AGENTS.md"
    if not agents.is_file():
        return False
    text = agents.read_text(encoding="utf-8")
    return "reason ci" in text and "Coding Agent Policy" in text


def _check_report_generation(result: dict[str, Any]) -> list[Any]:
    with tempfile.TemporaryDirectory(prefix="reasonscript-ci-entry-") as tmp:
        directory = Path(tmp)
        try:
            paths = write_ci_reports(directory, result)
            report_payload = _read_json(paths["report"])
            summary_payload = _read_json(paths["summary"])
        except (OSError, ValueError):
            return [_diag("CE-004", "Report generation failure", file="ci_report.json")]
    if report_payload.get("schema") != REPORT_SCHEMA or report_payload != ci_report(result):
        return [_diag("CE-004", "Report generation failure", file="ci_report.json")]
    if summary_payload.get("schema") != SUMMARY_SCHEMA or summary_payload != ci_summary(result):
        return [_diag("CE-004", "Report generation failure", file="ci_summary.json")]
    return []


def _check_fail_fast_semantics() -> list[Any]:
    with tempfile.TemporaryDirectory(prefix="reasonscript-ci-entry-broken-") as tmp:
        broken_root = Path(tmp)
        result = run_pipeline(broken_root, run_tests=False)
    phases = result["phases"]
    first_failure = next((index for index, phase in enumerate(phases) if phase["status"] == "FAIL"), None)
    if first_failure is None:
        return [_diag("CE-005", "Pipeline termination failure", file="toolchain/ci.py")]
    remaining = phases[first_failure + 1:]
    if any(phase["status"] != "SKIPPED" for phase in remaining):
        return [_diag("CE-005", "Pipeline termination failure", file="toolchain/ci.py")]
    return []


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _diag(code: str, message: str, *, file: str) -> Any:
    return diagnostic_from_parts(
        code=code,
        severity="ERROR",
        category="CLI",
        message=message,
        file=file,
        metadata={"rule": code},
    )
