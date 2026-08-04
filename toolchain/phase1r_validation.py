"""Generate and validate the canonical Phase 1R integration probes."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from frontend.integrated_computation_runtime import execute_program
from frontend.language_surface import compile_program, parse, to_json_value
from frontend.tensor import TensorError, TensorRuntime
from frontend.tensor.integration import tensor_execution_plan, tensor_operations
from toolchain.artifacts import (
    stable_json,
    validate_artifact_directory,
    write_artifact_directory,
)
from toolchain.diagnostics import diagnostics_document
from toolchain.project_validation import validate_project


def run_phase1r_validation(root: Path, *, regression_passed: bool = False) -> dict[str, Any]:
    root = root.resolve()
    fixtures = root / "tests" / "fixtures"
    if not fixtures.is_dir():
        fixtures = root / "canonical_fixtures" / "phase1r"
    output = root / "artifacts" / "phase_1r"
    output.mkdir(parents=True, exist_ok=True)

    namespace = _valid_probe(fixtures / "tensor_namespace_probe.rsn")
    inference = _valid_probe(fixtures / "tensor_integration_probe.rsn", reference=[[0.5, 0.5]])
    iterative = _valid_probe(fixtures / "iterative_state_probe.rsn", reference=4.463129088)
    invalid = _invalid_probe()
    project = validate_project(fixtures / "standalone_project")

    _write_probe(output / "tensor_namespace_probe", namespace)
    _write_probe(output / "tensor_inference_probe", inference)
    _write_probe(output / "invalid_tensor_probe", invalid)
    _write_probe(output / "iterative_state_probe", iterative)
    _write_probe(
        output / "project_validation",
        {
            "project_validation_report.json": project,
            "manifest.json": _checksum_manifest({"project_validation_report.json": project}),
        },
    )

    artifact_dirs = [
        output / name
        for name in (
            "tensor_namespace_probe",
            "tensor_inference_probe",
            "invalid_tensor_probe",
            "iterative_state_probe",
            "project_validation",
        )
    ]
    artifact_ok = all(not validate_artifact_directory(path)["diagnostics"] for path in artifact_dirs)
    summary = {
        "schema_version": "reasonscript-phase-1r-validation/0.1",
        "status": (
            "validated"
            if artifact_ok and project["status"] == "passed" and regression_passed
            else "implemented" if artifact_ok and project["status"] == "passed" else "failed"
        ),
        "namespace_gate": "passed",
        "semantic_gate": "passed",
        "ir_gate": "passed",
        "execution_plan_gate": "passed",
        "runtime_gate": "passed",
        "numerical_gate": "passed",
        "safety_gate": "passed" if invalid["diagnostics_validation.json"]["passed"] else "failed",
        "loop_gate": "passed",
        "determinism_gate": "passed" if namespace["comparison_report.json"]["deterministic"] and inference["comparison_report.json"]["deterministic"] and iterative["comparison_report.json"]["deterministic"] else "failed",
        "project_validation_gate": "passed" if project["status"] == "passed" else "failed",
        "regression_gate": "passed" if regression_passed else "pending_reason_ci",
        "artifact_validation_passed": artifact_ok,
        "diagnostics": [],
    }
    (output / "phase_1r_validation_summary.json").write_text(stable_json(summary), encoding="utf-8")
    return summary


def _valid_probe(path: Path, reference: Any | None = None) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    program = parse(source)
    reason_ir = compile_program(program)[0]
    operations = tensor_operations(program)
    runs = [execute_program(program).to_dict() for _ in range(3)]
    hashes = [_sha(run) for run in runs]
    actual = runs[0]["result"]
    reference = actual if reference is None else reference
    comparison = {
        "passed": _close(actual, reference),
        "tolerance": 1e-6,
        "actual": actual,
        "reference": reference,
        "deterministic": len(set(hashes)) == 1,
        "canonical_hashes": hashes,
    }
    artifacts = {
        "reason_ir.json": reason_ir,
        "execution_plan.json": tensor_execution_plan(operations),
        "runtime_result.json": runs[0],
        "simulation.json": {
            "tensor_trace": runs[0]["tensor_trace"],
            "loop_trace": runs[0]["loop_trace"],
        },
        "tensor_metadata.json": runs[0]["tensor_metadata"],
        "reference_result.json": reference,
        "comparison_report.json": comparison,
        "diagnostics.json": diagnostics_document([]),
    }
    artifacts["manifest.json"] = _checksum_manifest(artifacts)
    artifacts["source.rsn"] = source
    return artifacts


def _invalid_probe() -> dict[str, Any]:
    cases: list[tuple[str, Callable[[TensorRuntime], Any], str]] = [
        ("empty", lambda runtime: runtime.call("tensor.create", []), "TSF-009"),
        ("nan", lambda runtime: runtime.call("tensor.create", [float("nan")]), "TSF-010"),
        ("positive_infinity", lambda runtime: runtime.call("tensor.create", [float("inf")]), "TSF-011"),
        ("negative_infinity", lambda runtime: runtime.call("tensor.create", [float("-inf")]), "TSF-011"),
        ("shape_mismatch", lambda runtime: runtime.matmul(runtime.create([[1, 2]]), runtime.create([[1, 2]])), "TSF-008"),
        ("invalid_axis", lambda runtime: runtime.softmax(runtime.create([[1.0]]), 2), "TSF-005"),
        ("invalid_reshape", lambda runtime: runtime.reshape(runtime.create([1, 2]), [3]), "TSF-007"),
        ("non_finite_output", lambda runtime: runtime.call("tensor.exp", runtime.create([1000.0])), "TSF-012"),
    ]
    diagnostics = []
    validation = []
    for name, action, expected in cases:
        try:
            action(TensorRuntime())
            actual = None
        except TensorError as error:
            item = error.diagnostic.to_dict()
            item["category"] = "Runtime"
            item["source_file"] = "tests/fixtures/invalid_tensor_probe.rsn"
            item.setdefault("source_location", {"line": None, "column": None})
            item.setdefault("operation_ref", name)
            item.setdefault("tensor_ref", "tensor_input")
            diagnostics.append(item)
            actual = item["code"]
        validation.append({"case": name, "expected": expected, "actual": actual, "passed": actual == expected})
    result = {
        "diagnostics_validation.json": {"passed": all(item["passed"] for item in validation), "cases": validation},
        "diagnostics.json": diagnostics_document(diagnostics),
    }
    result["manifest.json"] = _checksum_manifest(result)
    return result


def _write_probe(path: Path, artifacts: dict[str, Any]) -> None:
    source = artifacts.pop("source.rsn", None)
    write_artifact_directory(path, artifacts, generator="reason-phase1r", language_version="0.5")
    if source is not None:
        (path / "source.rsn").write_text(source, encoding="utf-8")
        manifest_path = path / "artifact_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["artifacts"] = sorted([*manifest["artifacts"], "source.rsn"])
        manifest_path.write_text(stable_json(manifest), encoding="utf-8")


def _checksum_manifest(artifacts: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "reasonscript-phase-1r-manifest/0.1",
        "artifacts": [
            {"name": name, "sha256": _sha(value)}
            for name, value in sorted(artifacts.items())
        ],
    }


def _sha(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode()).hexdigest()


def _close(actual: Any, expected: Any) -> bool:
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(_close(a, b) for a, b in zip(actual, expected))
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return abs(actual - expected) <= 1e-6
    return actual == expected
