"""Reasoning Model Contract validation and serialization for reasonscript-reasoning-model/1.0.

Phase 8A establishes an artifact-level contract above the existing ReasonScript
pipeline (Reason IR / ExecutionPlan / Simulation / Knowledge). It introduces no
new source syntax, parser behavior, or runtime execution semantics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTRACT_SCHEMA = "reasonscript-reasoning-model/1.0"
VALIDATOR_SCHEMA = "reasonscript-reasoning-model-validator/1.0"

SEVERITIES = ("info", "warning", "error", "fatal")
FAILING_SEVERITIES = ("error", "fatal")

SOURCE_KINDS = (
    "reason_script_source",
    "reason_ir",
    "execution_plan",
    "simulation",
    "knowledge",
    "external_fixture",
)

SUPPORTED_INPUT_KINDS = ("structured_state",)
KNOWN_INPUT_KINDS = ("structured_state", "text", "number", "logic")

PATH_STATUSES = ("selected", "candidate", "rejected", "failed")

STEP_TYPES = (
    "state_transition",
    "relation_check",
    "calculation",
    "function_return",
    "branch_selection",
    "knowledge_emission",
    "runtime_operation",
    "external_reference",
)

REQUIRED_CHECKS = (
    "reachability",
    "determinism",
    "evidence_completeness",
    "consistency",
    "minimality",
    "branch_traceability",
)

TOP_LEVEL_ORDER = (
    "schema_version",
    "model_id",
    "source_ref",
    "input_state",
    "reasoning_paths",
    "selected_path_id",
    "knowledge_emissions",
    "evaluation_target",
    "diagnostics",
    "metadata",
)

_SOURCE_REF_ORDER = ("source_id", "source_kind", "artifact_refs")
_INPUT_STATE_ORDER = ("input_id", "input_kind", "units", "relations")
_INPUT_UNIT_ORDER = ("unit_id", "unit_type", "value")
_INPUT_RELATION_ORDER = ("relation_id", "relation_type", "source", "target")
_PATH_ORDER = ("path_id", "path_signature", "status", "steps", "metadata")
_STEP_ORDER = ("step_id", "step_type", "source", "target", "operation", "evidence_refs")
_KNOWLEDGE_ORDER = ("knowledge_id", "source_step_id", "relation", "source", "target", "evidence_path", "path_signature")
_EVAL_ORDER = ("target_id", "goal", "expected_relation", "expected_value", "success_criteria", "required_checks")
_DIAGNOSTIC_ORDER = ("code", "severity", "message", "location")


def load_model(source: dict[str, Any] | str | Path) -> Any:
    if isinstance(source, dict):
        return source
    path = Path(source)
    return json.loads(path.read_text(encoding="utf-8"))


def validate(source: dict[str, Any] | str | Path) -> dict[str, Any]:
    model = load_model(source)
    diagnostics: list[dict[str, Any]] = []

    if not isinstance(model, dict):
        diagnostics.append(_diag("RM-001", "missing schema_version", location="schema_version"))
        return _result(diagnostics)

    _check_top_level(model, diagnostics)
    _check_input_state(model, diagnostics)
    path_ids, path_signatures, step_ids_by_path = _check_reasoning_paths(model, diagnostics)
    _check_selected_path(model, diagnostics, path_ids)
    successful = _is_successful(model, diagnostics, path_ids)
    _check_knowledge_emissions(model, diagnostics, step_ids_by_path, path_signatures, successful)
    _check_evaluation_target(model, diagnostics)

    return _result(diagnostics)


def _result(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    valid = not any(item["severity"] in FAILING_SEVERITIES for item in diagnostics)
    return {
        "schema_version": VALIDATOR_SCHEMA,
        "valid": valid,
        "diagnostics": diagnostics,
    }


def render_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def serialize_reasoning_model(model: dict[str, Any]) -> str:
    return json.dumps(_canonicalize(model), ensure_ascii=False, indent=2) + "\n"


def _diag(code: str, message: str, *, severity: str = "error", location: str | None = None) -> dict[str, Any]:
    diagnostic = {"code": code, "severity": severity, "message": message}
    if location is not None:
        diagnostic["location"] = location
    return diagnostic


def _check_top_level(model: dict[str, Any], diagnostics: list[dict[str, Any]]) -> None:
    if "schema_version" not in model:
        diagnostics.append(_diag("RM-001", "missing schema_version", location="schema_version"))
    elif model.get("schema_version") != CONTRACT_SCHEMA:
        diagnostics.append(_diag("RM-002", "unsupported schema_version", location="schema_version"))

    model_id = model.get("model_id")
    if "model_id" not in model:
        diagnostics.append(_diag("RM-003", "missing model_id", location="model_id"))
    elif not isinstance(model_id, str) or not model_id.strip():
        diagnostics.append(_diag("RM-004", "invalid model_id", location="model_id"))

    if "source_ref" not in model or not isinstance(model.get("source_ref"), dict):
        diagnostics.append(_diag("RM-005", "missing source_ref", location="source_ref"))

    if "input_state" not in model or not isinstance(model.get("input_state"), dict):
        diagnostics.append(_diag("RM-006", "missing input_state", location="input_state"))

    if "reasoning_paths" not in model or not isinstance(model.get("reasoning_paths"), list):
        diagnostics.append(_diag("RM-007", "missing reasoning_paths", location="reasoning_paths"))

    if "selected_path_id" not in model or not isinstance(model.get("selected_path_id"), str) or not model.get("selected_path_id"):
        diagnostics.append(_diag("RM-008", "missing selected_path_id", location="selected_path_id"))

    if "evaluation_target" not in model or not isinstance(model.get("evaluation_target"), dict):
        diagnostics.append(_diag("RM-010", "missing evaluation_target", location="evaluation_target"))


def _check_input_state(model: dict[str, Any], diagnostics: list[dict[str, Any]]) -> set[str]:
    input_state = model.get("input_state")
    if not isinstance(input_state, dict):
        return set()

    if not input_state.get("input_id"):
        diagnostics.append(_diag("RM-IN-001", "missing input_id", location="input_state.input_id"))

    input_kind = input_state.get("input_kind")
    if not input_kind:
        diagnostics.append(_diag("RM-IN-002", "missing input_kind", location="input_state.input_kind"))
    elif input_kind not in KNOWN_INPUT_KINDS:
        diagnostics.append(_diag("RM-IN-003", "unsupported input_kind", location="input_state.input_kind"))

    units = _as_list(input_state.get("units"))
    seen_units: set[str] = set()
    unit_ids: set[str] = set()
    for unit in units:
        if not isinstance(unit, dict):
            continue
        unit_id = unit.get("unit_id")
        if not unit_id:
            continue
        unit_ids.add(unit_id)
        if unit_id in seen_units:
            diagnostics.append(_diag("RM-IN-004", f"duplicate input unit_id: {unit_id}", location="input_state.units"))
        seen_units.add(unit_id)

    relations = _as_list(input_state.get("relations"))
    seen_relations: set[str] = set()
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        relation_id = relation.get("relation_id")
        if relation_id:
            if relation_id in seen_relations:
                diagnostics.append(_diag("RM-IN-005", f"duplicate input relation_id: {relation_id}", location="input_state.relations"))
            seen_relations.add(relation_id)
        source = relation.get("source")
        target = relation.get("target")
        if source is not None and source not in unit_ids:
            diagnostics.append(_diag("RM-IN-006", f"relation source does not reference an existing unit: {source}", location="input_state.relations"))
        if target is not None and target not in unit_ids:
            diagnostics.append(_diag("RM-IN-007", f"relation target does not reference an existing unit: {target}", location="input_state.relations"))

    return unit_ids


def _check_reasoning_paths(
    model: dict[str, Any],
    diagnostics: list[dict[str, Any]],
) -> tuple[set[str], set[str], dict[str, set[str]]]:
    paths = model.get("reasoning_paths")
    if not isinstance(paths, list):
        return set(), set(), {}

    path_ids: set[str] = set()
    path_signatures: set[str] = set()
    step_ids_by_path: dict[str, set[str]] = {}
    selected_count = 0
    seen_path_ids: set[str] = set()

    for path in paths:
        if not isinstance(path, dict):
            continue
        path_id = path.get("path_id")
        if path_id:
            if path_id in seen_path_ids:
                diagnostics.append(_diag("RM-PATH-001", f"duplicate path_id: {path_id}", location="reasoning_paths"))
            seen_path_ids.add(path_id)
            path_ids.add(path_id)

        signature = path.get("path_signature")
        if not signature:
            diagnostics.append(_diag("RM-PATH-002", "empty path_signature", location=f"reasoning_paths[{path_id}].path_signature"))
        else:
            path_signatures.add(signature)

        status = path.get("status")
        if not status:
            diagnostics.append(_diag("RM-PATH-003", "missing path status", location=f"reasoning_paths[{path_id}].status"))
        elif status not in PATH_STATUSES:
            diagnostics.append(_diag("RM-PATH-004", f"invalid path status: {status}", location=f"reasoning_paths[{path_id}].status"))
        elif status == "selected":
            selected_count += 1

        step_ids = _check_steps(path, diagnostics, path_id)
        if path_id:
            step_ids_by_path[path_id] = step_ids

    if selected_count == 0:
        diagnostics.append(_diag("RM-PATH-005", "no selected path", location="reasoning_paths"))
    elif selected_count > 1:
        diagnostics.append(_diag("RM-PATH-006", "multiple selected paths", location="reasoning_paths"))

    return path_ids, path_signatures, step_ids_by_path


def _check_steps(path: dict[str, Any], diagnostics: list[dict[str, Any]], path_id: str | None) -> set[str]:
    steps = path.get("steps")
    if not isinstance(steps, list):
        return set()

    seen_step_ids: set[str] = set()
    step_ids: set[str] = set()
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_id = step.get("step_id")
        location_prefix = f"reasoning_paths[{path_id}].steps"
        if step_id:
            if step_id in seen_step_ids:
                diagnostics.append(_diag("RM-STEP-001", f"duplicate step_id within path: {step_id}", location=location_prefix))
            seen_step_ids.add(step_id)
            step_ids.add(step_id)

        step_type = step.get("step_type")
        if step_type not in STEP_TYPES:
            diagnostics.append(_diag("RM-STEP-002", f"invalid step_type: {step_type}", location=location_prefix))
        if not step.get("source"):
            diagnostics.append(_diag("RM-STEP-003", "missing step source", location=location_prefix))
        if not step.get("target"):
            diagnostics.append(_diag("RM-STEP-004", "missing step target", location=location_prefix))
        if not step.get("operation"):
            diagnostics.append(_diag("RM-STEP-005", "missing step operation", location=location_prefix))
        if "evidence_refs" not in step or not isinstance(step.get("evidence_refs"), list):
            diagnostics.append(_diag("RM-STEP-006", "missing evidence_refs", location=location_prefix))

    return step_ids


def _check_selected_path(model: dict[str, Any], diagnostics: list[dict[str, Any]], path_ids: set[str]) -> None:
    selected_path_id = model.get("selected_path_id")
    if not selected_path_id:
        return
    if selected_path_id not in path_ids:
        diagnostics.append(_diag("RM-009", "selected_path_id does not reference an existing path", location="selected_path_id"))


def _is_successful(model: dict[str, Any], diagnostics: list[dict[str, Any]], path_ids: set[str]) -> bool:
    selected_path_id = model.get("selected_path_id")
    has_selected_reference = bool(selected_path_id) and selected_path_id in path_ids
    has_blocking_diagnostic = any(item["severity"] in FAILING_SEVERITIES for item in diagnostics)
    return has_selected_reference and not has_blocking_diagnostic


def _check_knowledge_emissions(
    model: dict[str, Any],
    diagnostics: list[dict[str, Any]],
    step_ids_by_path: dict[str, set[str]],
    path_signatures: set[str],
    successful: bool,
) -> None:
    emissions = model.get("knowledge_emissions")
    if not isinstance(emissions, list):
        return

    all_step_ids: set[str] = set()
    for step_ids in step_ids_by_path.values():
        all_step_ids |= step_ids

    seen_ids: set[str] = set()
    for emission in emissions:
        if not isinstance(emission, dict):
            continue
        knowledge_id = emission.get("knowledge_id")
        if knowledge_id:
            if knowledge_id in seen_ids:
                diagnostics.append(_diag("RM-KNOW-001", f"duplicate knowledge_id: {knowledge_id}", location="knowledge_emissions"))
            seen_ids.add(knowledge_id)

        source_step_id = emission.get("source_step_id")
        location = f"knowledge_emissions[{knowledge_id}]"
        if source_step_id is not None and source_step_id not in all_step_ids:
            diagnostics.append(_diag("RM-KNOW-002", f"source_step_id does not reference an existing step: {source_step_id}", location=location))

        evidence_path = emission.get("evidence_path")
        if successful and not evidence_path:
            diagnostics.append(_diag("RM-KNOW-003", "empty evidence_path in successful model", location=location))

        signature = emission.get("path_signature")
        if signature is not None and signature not in path_signatures:
            diagnostics.append(_diag("RM-KNOW-004", f"path_signature does not reference an existing path signature: {signature}", location=location))


def _check_evaluation_target(model: dict[str, Any], diagnostics: list[dict[str, Any]]) -> None:
    target = model.get("evaluation_target")
    if not isinstance(target, dict):
        return

    if not target.get("target_id"):
        diagnostics.append(_diag("RM-EVAL-001", "missing target_id", location="evaluation_target.target_id"))
    if not target.get("goal"):
        diagnostics.append(_diag("RM-EVAL-002", "missing goal", location="evaluation_target.goal"))

    required_checks = target.get("required_checks")
    if not required_checks:
        diagnostics.append(_diag("RM-EVAL-003", "missing required_checks", location="evaluation_target.required_checks"))
        return

    for check in required_checks:
        if check not in REQUIRED_CHECKS:
            diagnostics.append(_diag("RM-EVAL-004", f"invalid required_check: {check}", location="evaluation_target.required_checks"))


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return _canonicalize_dict(value)
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


def _canonicalize_dict(value: dict[str, Any]) -> dict[str, Any]:
    if _looks_like(value, {"schema_version", "model_id"}):
        ordered = _reorder(value, TOP_LEVEL_ORDER)
        ordered["input_state"] = _canonicalize_input_state(value.get("input_state", {}))
        ordered["source_ref"] = _reorder(_canonicalize(value.get("source_ref", {})), _SOURCE_REF_ORDER)
        ordered["reasoning_paths"] = _sort_by_id(
            [_canonicalize_path(item) for item in value.get("reasoning_paths", [])], "path_id"
        )
        ordered["knowledge_emissions"] = _sort_by_id(
            [_reorder(_canonicalize(item), _KNOWLEDGE_ORDER) for item in value.get("knowledge_emissions", [])],
            "knowledge_id",
        )
        ordered["evaluation_target"] = _reorder(_canonicalize(value.get("evaluation_target", {})), _EVAL_ORDER)
        ordered["diagnostics"] = _sort_diagnostics(
            [_reorder(_canonicalize(item), _DIAGNOSTIC_ORDER) for item in value.get("diagnostics", [])]
        )
        if "metadata" not in value or not value.get("metadata"):
            ordered.pop("metadata", None)
        return ordered
    return {key: _canonicalize(value[key]) for key in sorted(value)}


def _canonicalize_input_state(input_state: dict[str, Any]) -> dict[str, Any]:
    ordered = _reorder(_canonicalize(input_state), _INPUT_STATE_ORDER)
    ordered["units"] = _sort_by_id(
        [_reorder(_canonicalize(item), _INPUT_UNIT_ORDER) for item in input_state.get("units", [])], "unit_id"
    )
    ordered["relations"] = _sort_by_id(
        [_reorder(_canonicalize(item), _INPUT_RELATION_ORDER) for item in input_state.get("relations", [])],
        "relation_id",
    )
    return ordered


def _canonicalize_path(path: dict[str, Any]) -> dict[str, Any]:
    ordered = _reorder(_canonicalize(path), _PATH_ORDER)
    ordered["steps"] = [_reorder(_canonicalize(item), _STEP_ORDER) for item in path.get("steps", [])]
    if "metadata" not in path or not path.get("metadata"):
        ordered.pop("metadata", None)
    return ordered


def _reorder(value: dict[str, Any], order: tuple[str, ...]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}
    for key in order:
        if key in value:
            ordered[key] = value[key]
    for key in sorted(value):
        if key not in ordered:
            ordered[key] = value[key]
    return ordered


def _sort_by_id(items: list[dict[str, Any]], id_field: str) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: str(item.get(id_field, "")))


def _sort_diagnostics(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: (str(item.get("code", "")), str(item.get("message", ""))))


def _looks_like(value: dict[str, Any], required: set[str]) -> bool:
    return required.issubset(value.keys())


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
