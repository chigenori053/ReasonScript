"""Deterministic artifact writer for the ReasonScript CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from toolchain.artifacts import write_artifact_directory
from toolchain.diagnostics import diagnostics_document, diagnostics_summary

ARTIFACT_FILENAMES = {
    "language_surface_ast": "language_surface_ast.json",
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
    artifacts = result.get("artifacts") if isinstance(result.get("artifacts"), dict) else {}
    diagnostic_document = diagnostics_document(result.get("diagnostics", []))
    output: dict[str, Any] = {}
    for key, filename in ARTIFACT_FILENAMES.items():
        if key == "diagnostics":
            value = diagnostic_document
        elif key == "diagnostics_summary":
            value = diagnostics_summary(diagnostic_document)
        elif key == "language_surface_ast":
            value = artifacts.get("surface_ast")
        elif key == "project_state":
            value = result.get("project_state")
        else:
            value = artifacts.get(key)
        output[filename] = value
    write_artifact_directory(directory, output, generator="reason-cli", language_version=_language_version(result))


def _language_version(result: dict[str, Any]) -> str:
    project_state = result.get("project_state")
    if isinstance(project_state, dict):
        metadata = project_state.get("metadata")
        if isinstance(metadata, dict) and isinstance(metadata.get("language_version"), str):
            return metadata["language_version"]
    return "0.5"
