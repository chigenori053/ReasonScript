"""Canonical artifact model for reasonscript-artifacts/1.0."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from toolchain.diagnostics import diagnostic_from_parts, diagnostics_document


ARTIFACT_VERSION = "1.0"
ARTIFACT_SCHEMA = "reasonscript-artifacts/1.0"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

CANONICAL_ARTIFACTS = (
    "workspace.json",
    "project_summary.json",
    "symbol_index.json",
    "dependency_graph.json",
    "diagnostics.json",
    "diagnostics_summary.json",
    "language_surface_ast.json",
    "semantic_ast.json",
    "reason_ir.json",
    "execution_plan.json",
    "simulation.json",
    "knowledge.json",
    "validation.json",
)

REQUIRED_ARTIFACTS = (
    "artifact_manifest.json",
    "artifact_summary.json",
)

ARTIFACT_SCHEMAS = {
    "workspace.json": "reasonscript-workspace/1.0",
    "project_summary.json": "reasonscript-project-summary/1.0",
    "symbol_index.json": "reasonscript-symbol-index/1.0",
    "dependency_graph.json": "reasonscript-dependency-graph/1.0",
    "diagnostics.json": "reasonscript-diagnostics/1.0",
    "diagnostics_summary.json": "reasonscript-diagnostics-summary/1.0",
    "language_surface_ast.json": "reasonscript-language-surface/0.5",
    "surface_ast.json": "reasonscript-language-surface/0.5",
    "semantic_ast.json": "reasonscript-semantic-ast/0.5",
    "reason_ir.json": "reason-ir/0.5",
    "execution_plan.json": "execution-plan/0.5",
    "simulation.json": "simulation/0.5",
    "knowledge.json": "knowledge/0.5",
    "validation.json": "reasonscript-validation/0.5",
    "table.json": "reasonscript-table/0.1",
    "table_schema.json": "reasonscript-table-schema/0.1",
    "data_source.json": "reasonscript-data-source/0.1",
    "data_operations.json": "reasonscript-data-operations/0.1",
    "aggregation.json": "reasonscript-aggregation/0.1",
    "data_provenance.json": "reasonscript-data-provenance/0.1",
    "data_evidence.json": "reasonscript-data-evidence/0.1",
    "titanic_analysis_result.json": "reasonscript-titanic-analysis-result/1.0",
    "visualization_spec.json": "reasonscript-visualization-spec/0.1",
    "visualization_ir.json": "reasonscript-visualization-ir/0.1",
    "render_plan.json": "reasonscript-visualization-render-plan/0.1",
    "visualization_evidence.json": "reasonscript-visualization-evidence/0.1",
    "visualization_validation.json": "reasonscript-visualization-validation/0.1",
    "workspace_validation.json": "reasonscript-workspace-validation/1.0",
    "project_state.json": "reasonscript-project-state/0.5",
    "runtime_result.json": "reasonscript-integrated-runtime/0.1",
    "tensor_metadata.json": "reasonscript-tensor-metadata/0.1",
    "input.json": "reasonscript-tensor-input/0.1",
    "weights.json": "reasonscript-tensor-input/0.1",
    "reference_result.json": "reasonscript-reference-result/0.1",
    "comparison_report.json": "reasonscript-comparison-report/0.1",
    "diagnostics_validation.json": "reasonscript-diagnostics-validation/0.1",
    "project_validation_report.json": "reasonscript-project-validation/0.1",
    "phase_1r_validation_summary.json": "reasonscript-phase-1r-validation/0.1",
    "manifest.json": "reasonscript-phase-1r-manifest/0.1",
    "artifact_manifest.json": "reasonscript-artifact-manifest/1.0",
    "artifact_summary.json": "reasonscript-artifact-summary/1.0",
}

SUPPORTED_SCHEMA_PREFIXES = (
    "reasonscript-workspace/",
    "reasonscript-project-summary/",
    "reasonscript-symbol-index/",
    "reasonscript-dependency-graph/",
    "reasonscript-diagnostics/",
    "reasonscript-diagnostics-summary/",
    "reasonscript-language-surface/",
    "reasonscript-semantic-ast/",
    "reason-ir/",
    "execution-plan/",
    "simulation/",
    "knowledge/",
    "reasonscript-validation/",
    "reasonscript-workspace-validation/",
    "reasonscript-project-state/",
    "reasonscript-integrated-runtime/",
    "reasonscript-tensor-metadata/",
    "reasonscript-tensor-input/",
    "reasonscript-reference-result/",
    "reasonscript-comparison-report/",
    "reasonscript-diagnostics-validation/",
    "reasonscript-project-validation/",
    "reasonscript-phase-1r-validation/",
    "reasonscript-phase-1r-manifest/",
    "reasonscript-artifact-manifest/",
    "reasonscript-artifact-summary/",
    "reasonscript-table/",
    "reasonscript-table-schema/",
    "reasonscript-data-source/",
    "reasonscript-data-operations/",
    "reasonscript-aggregation/",
    "reasonscript-data-provenance/",
    "reasonscript-data-evidence/",
    "reasonscript-titanic-analysis-result/",
    "reasonscript-visualization-spec/",
    "reasonscript-visualization-ir/",
    "reasonscript-visualization-render-plan/",
    "reasonscript-visualization-evidence/",
    "reasonscript-visualization-validation/",
)


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def artifact_envelope(
    filename: str,
    data: Any,
    *,
    generator: str,
    language_version: str,
    generated_at: str = DETERMINISTIC_GENERATED_AT,
) -> dict[str, Any]:
    return {
        "version": ARTIFACT_VERSION,
        "schema": ARTIFACT_SCHEMAS.get(filename, ARTIFACT_SCHEMA),
        "generator": generator,
        "generated_at": generated_at,
        "language_version": language_version,
        "data": data,
    }


def artifact_manifest(
    artifact_filenames: list[str],
    *,
    generator: str,
    language_version: str,
    generated_at: str = DETERMINISTIC_GENERATED_AT,
) -> dict[str, Any]:
    return {
        "version": ARTIFACT_VERSION,
        "schema": ARTIFACT_SCHEMAS["artifact_manifest.json"],
        "artifact_version": ARTIFACT_VERSION,
        "language_version": language_version,
        "generated_at": generated_at,
        "generator": generator,
        "artifacts": sorted(artifact_filenames),
    }


def artifact_summary(
    artifact_filenames: list[str],
    *,
    errors: int = 0,
    generator: str,
    language_version: str,
    generated_at: str = DETERMINISTIC_GENERATED_AT,
) -> dict[str, Any]:
    return {
        "version": ARTIFACT_VERSION,
        "schema": ARTIFACT_SCHEMAS["artifact_summary.json"],
        "generator": generator,
        "generated_at": generated_at,
        "language_version": language_version,
        "artifact_count": len(artifact_filenames),
        "generated": True,
        "errors": errors,
        "artifacts": sorted(artifact_filenames),
    }


def write_artifact_directory(
    directory: Path,
    artifacts: dict[str, Any],
    *,
    generator: str,
    language_version: str,
) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for filename in sorted(artifacts):
        envelope = artifact_envelope(filename, artifacts[filename], generator=generator, language_version=language_version)
        (directory / filename).write_text(stable_json(envelope), encoding="utf-8")
        written.append(filename)
    manifest = artifact_manifest(written, generator=generator, language_version=language_version)
    summary = artifact_summary(written, errors=0, generator=generator, language_version=language_version)
    (directory / "artifact_manifest.json").write_text(stable_json(manifest), encoding="utf-8")
    (directory / "artifact_summary.json").write_text(stable_json(summary), encoding="utf-8")
    return {
        "manifest": manifest,
        "summary": summary,
        "artifacts": sorted([*written, *REQUIRED_ARTIFACTS]),
    }


def validate_artifact_directory(directory: Path, *, expected: tuple[str, ...] = ()) -> dict[str, Any]:
    diagnostics = []
    if not directory.exists() or not directory.is_dir():
        diagnostics.append(_artifact_diag("AR-010", f"Output directory mismatch: {directory}", file=str(directory)))
        return diagnostics_document(diagnostics)

    for filename in expected:
        if not (directory / filename).is_file():
            diagnostics.append(_artifact_diag("AR-001", f"Missing artifact: {filename}", file=filename))

    parsed: dict[str, Any] = {}
    for path in sorted(directory.glob("*.json"), key=lambda item: item.name):
        try:
            text = path.read_text(encoding="utf-8")
            value = json.loads(text)
        except (OSError, json.JSONDecodeError) as error:
            diagnostics.append(_artifact_diag("AR-002", f"Invalid JSON: {error}", file=path.name))
            continue
        parsed[path.name] = value
        if stable_json(value) != text:
            diagnostics.append(_artifact_diag("AR-006", f"Determinism violation: {path.name}", file=path.name))
        diagnostics.extend(_validate_artifact_payload(path.name, value))

    manifest = parsed.get("artifact_manifest.json")
    if not isinstance(manifest, dict):
        diagnostics.append(_artifact_diag("AR-009", "Invalid manifest: artifact_manifest.json missing", file="artifact_manifest.json"))
    else:
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, list) or not all(isinstance(item, str) for item in artifacts):
            diagnostics.append(_artifact_diag("AR-009", "Invalid manifest: artifacts must be a string array", file="artifact_manifest.json"))
        else:
            seen: set[str] = set()
            for filename in artifacts:
                if filename in seen:
                    diagnostics.append(_artifact_diag("AR-008", f"Duplicate artifact: {filename}", file="artifact_manifest.json"))
                seen.add(filename)
                if not (directory / filename).is_file():
                    diagnostics.append(_artifact_diag("AR-007", f"Broken artifact reference: {filename}", file="artifact_manifest.json"))
        if manifest.get("artifact_version") != ARTIFACT_VERSION:
            diagnostics.append(_artifact_diag("AR-009", "Invalid manifest: artifact_version mismatch", file="artifact_manifest.json"))

    return diagnostics_document(diagnostics)


def unwrap_artifact(value: Any) -> Any:
    if isinstance(value, dict) and {"version", "schema", "generator", "generated_at", "data"}.issubset(value):
        return value.get("data")
    return value


def _validate_artifact_payload(filename: str, value: Any) -> list[Any]:
    diagnostics = []
    if not isinstance(value, dict):
        diagnostics.append(_artifact_diag("AR-005", "Missing metadata: artifact must be an object", file=filename))
        return diagnostics
    if "schema" not in value:
        diagnostics.append(_artifact_diag("AR-003", "Missing schema", file=filename))
    elif not _is_supported_schema(str(value["schema"])):
        diagnostics.append(_artifact_diag("AR-004", f"Unsupported schema version: {value['schema']}", file=filename))
    for field in ("version", "generator", "generated_at"):
        if field not in value:
            diagnostics.append(_artifact_diag("AR-005", f"Missing metadata: {field}", file=filename))
    return diagnostics


def _is_supported_schema(schema: str) -> bool:
    return any(schema.startswith(prefix) for prefix in SUPPORTED_SCHEMA_PREFIXES)


def _artifact_diag(code: str, message: str, *, file: str) -> Any:
    return diagnostic_from_parts(
        code=code,
        severity="ERROR",
        category="Artifact",
        message=message,
        file=file,
        metadata={"rule": code},
    )
