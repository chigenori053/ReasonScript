"""Deterministic artifact writer for the ReasonScript CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from toolchain.diagnostics import diagnostics_document, diagnostics_summary


ARTIFACT_FILENAMES = {
    "surface_ast": "surface_ast.json",
    "semantic_ast": "semantic_ast.json",
    "reason_ir": "reason_ir.json",
    "execution_plan": "execution_plan.json",
    "simulation": "simulation.json",
    "knowledge": "knowledge.json",
    "diagnostics": "diagnostics.json",
    "diagnostics_summary": "diagnostics_summary.json",
    "validation": "validation.json",
    "project_state": "project_state.json",
}


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def write_json(path: Path, value: Any) -> None:
    path.write_text(stable_json(value), encoding="utf-8")


def write_cli_artifacts(directory: Path, result: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    artifacts = result.get("artifacts") if isinstance(result.get("artifacts"), dict) else {}
    diagnostic_document = diagnostics_document(result.get("diagnostics", []))
    for key, filename in ARTIFACT_FILENAMES.items():
        if key == "diagnostics":
            value = diagnostic_document
        elif key == "diagnostics_summary":
            value = diagnostics_summary(diagnostic_document)
        elif key == "project_state":
            value = result.get("project_state")
        else:
            value = artifacts.get(key)
        write_json(directory / filename, value)
