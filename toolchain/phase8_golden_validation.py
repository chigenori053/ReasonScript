"""Phase 8 Final golden validation for reasonscript-phase8-golden-validation/1.0."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from toolchain.diagnostics import diagnostic_from_parts, diagnostics_document
from toolchain.reasoning_evaluation_report import (
    serialize_evaluation_report,
    validate_evaluation_report,
)
from toolchain.reasoning_model_contract import (
    serialize_reasoning_model,
)
from toolchain.reasoning_model_contract import (
    validate as validate_reasoning_model,
)
from toolchain.reasoning_runtime import (
    run_reasoning_runtime,
    serialize_reasoning_runtime_result,
    validate_reasoning_runtime_result,
)

CONTRACT_SCHEMA = "reasonscript-phase8-golden-validation/1.0"
VALIDATOR_SCHEMA = "reasonscript-phase8-golden-validation-report/1.0"
GOLDEN_ROOT = Path("tests/fixtures/golden/phase8")
EXAMPLE_ROOT = Path("examples/v0_8/reasoning_runtime")

VALID_SCENARIOS = (
    "animal_isa",
    "calculation_chain",
    "function_return",
    "branch_selection",
    "unreachable_goal",
)
INVALID_SCENARIOS = ("invalid_parse",)
SCENARIOS = VALID_SCENARIOS + INVALID_SCENARIOS


def validate_phase8_golden(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root)
    diagnostics: list[Any] = []
    results: list[dict[str, Any]] = []

    for scenario in SCENARIOS:
        source = root / EXAMPLE_ROOT / f"{scenario}.rsn"
        golden_dir = root / GOLDEN_ROOT / scenario
        scenario_diags: list[Any] = []
        if not source.is_file():
            scenario_diags.append(_gv_diag("GV-001", f"Missing golden source fixture: {scenario}", file=_rel(root, source)))
        if not golden_dir.is_dir():
            scenario_diags.append(_gv_diag("GV-011", f"Missing golden scenario directory: {scenario}", file=_rel(root, golden_dir)))
        if scenario in VALID_SCENARIOS:
            _require_file(root, golden_dir / "reasoning_model.json", "GV-002", scenario_diags)
            _require_file(root, golden_dir / "reasoning_evaluation_report.json", "GV-003", scenario_diags)
        _require_file(root, golden_dir / "reasoning_runtime_result.json", "GV-004", scenario_diags)

        if not scenario_diags:
            scenario_diags.extend(_validate_scenario(root, scenario, source, golden_dir))
        diagnostics.extend(scenario_diags)
        results.append({
            "scenario": scenario,
            "status": "PASS" if not scenario_diags else "FAIL",
            "diagnostics": [item.to_dict() for item in scenario_diags],
        })

    document = diagnostics_document(diagnostics)
    return {
        "schema_version": VALIDATOR_SCHEMA,
        "target": CONTRACT_SCHEMA,
        "status": "PASS" if not document["diagnostics"] else "FAIL",
        "ok": not document["diagnostics"],
        "scenarios": results,
        "diagnostics": document["diagnostics"],
    }


def update_phase8_golden(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root)
    for scenario in SCENARIOS:
        source = root / EXAMPLE_ROOT / f"{scenario}.rsn"
        target = root / GOLDEN_ROOT / scenario
        target.mkdir(parents=True, exist_ok=True)
        runtime = run_reasoning_runtime(source)
        (target / "reasoning_runtime_result.json").write_text(
            serialize_reasoning_runtime_result(runtime),
            encoding="utf-8",
        )
        if scenario in VALID_SCENARIOS:
            model = runtime["reasoning_model"]
            report = runtime["evaluation_report"]
            (target / "reasoning_model.json").write_text(
                serialize_reasoning_model(model),
                encoding="utf-8",
            )
            (target / "reasoning_evaluation_report.json").write_text(
                serialize_evaluation_report(report),
                encoding="utf-8",
            )
    return validate_phase8_golden(root)


def render_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def _validate_scenario(root: Path, scenario: str, source: Path, golden_dir: Path) -> list[Any]:
    diagnostics: list[Any] = []
    runtime = run_reasoning_runtime(source)
    runtime_json = serialize_reasoning_runtime_result(runtime)
    _assert_stable(runtime_json, serialize_reasoning_runtime_result(run_reasoning_runtime(source)), root, source, diagnostics)
    _assert_schema(validate_reasoning_runtime_result(runtime), root, golden_dir / "reasoning_runtime_result.json", diagnostics)
    _assert_match(runtime_json, golden_dir / "reasoning_runtime_result.json", "GV-007", root, diagnostics)
    _assert_cli(root, ["reasoning-runtime", "run", _rel(root, source), "--json"], runtime_json, diagnostics)

    if scenario in VALID_SCENARIOS:
        model = runtime["reasoning_model"]
        model_json = serialize_reasoning_model(model)
        _assert_stable(model_json, serialize_reasoning_model(json.loads(model_json)), root, source, diagnostics)
        _assert_schema(validate_reasoning_model(model), root, golden_dir / "reasoning_model.json", diagnostics)
        _assert_schema(validate_reasoning_model(golden_dir / "reasoning_model.json"), root, golden_dir / "reasoning_model.json", diagnostics)
        _assert_match(model_json, golden_dir / "reasoning_model.json", "GV-005", root, diagnostics)
        _assert_cli(root, ["reasoning-runtime", "build-model", _rel(root, source), "--json"], model_json, diagnostics)

        report = runtime["evaluation_report"]
        report_json = serialize_evaluation_report(report)
        _assert_stable(report_json, serialize_evaluation_report(json.loads(report_json)), root, source, diagnostics)
        _assert_schema(validate_evaluation_report(report), root, golden_dir / "reasoning_evaluation_report.json", diagnostics)
        _assert_schema(validate_evaluation_report(golden_dir / "reasoning_evaluation_report.json"), root, golden_dir / "reasoning_evaluation_report.json", diagnostics)
        _assert_match(report_json, golden_dir / "reasoning_evaluation_report.json", "GV-006", root, diagnostics)
        _assert_cli(root, ["reasoning-runtime", "evaluate", _rel(root, source), "--json"], report_json, diagnostics)

    validation = validate_reasoning_runtime_result(golden_dir / "reasoning_runtime_result.json")
    _assert_schema(validation, root, golden_dir / "reasoning_runtime_result.json", diagnostics)
    _assert_cli(root, ["reasoning-runtime", "validate", _rel(root, golden_dir / "reasoning_runtime_result.json"), "--json"], None, diagnostics)
    return diagnostics


def _require_file(root: Path, path: Path, code: str, diagnostics: list[Any]) -> None:
    if not path.is_file():
        diagnostics.append(_gv_diag(code, f"Missing golden artifact: {path.name}", file=_rel(root, path)))


def _assert_match(actual: str, expected_path: Path, code: str, root: Path, diagnostics: list[Any]) -> None:
    expected = expected_path.read_text(encoding="utf-8")
    if actual != expected:
        diagnostics.append(_gv_diag(code, "Generated artifact does not match golden", file=_rel(root, expected_path)))


def _assert_schema(result: dict[str, Any], root: Path, path: Path, diagnostics: list[Any]) -> None:
    if not result.get("valid", False):
        diagnostics.append(_gv_diag("GV-008", "Generated or golden artifact failed schema validation", file=_rel(root, path)))


def _assert_stable(first: str, second: str, root: Path, source: Path, diagnostics: list[Any]) -> None:
    if first != second:
        diagnostics.append(_gv_diag("GV-009", "Deterministic serialization mismatch", file=_rel(root, source)))


def _assert_cli(root: Path, args: list[str], expected: str | None, diagnostics: list[Any]) -> None:
    completed = subprocess.run([sys.executable, "-m", "toolchain", *args], cwd=root, text=True, capture_output=True, check=False)
    if expected is not None and completed.stdout != expected:
        diagnostics.append(_gv_diag("GV-010", "CLI output mismatch", file=" ".join(args)))
    if expected is None and args[1] == "validate":
        try:
            validation = json.loads(completed.stdout)
        except json.JSONDecodeError:
            validation = {}
        if validation.get("valid") is not True:
            diagnostics.append(_gv_diag("GV-010", "CLI validation output was not valid", file=" ".join(args)))
    if args[1] not in {"run", "evaluate"} and completed.returncode != 0:
        diagnostics.append(_gv_diag("GV-010", "CLI command failed", file=" ".join(args)))
    if args[1] in {"run", "evaluate"} and completed.returncode not in (0, 1):
        diagnostics.append(_gv_diag("GV-010", "CLI command failed", file=" ".join(args)))


def _gv_diag(code: str, message: str, *, file: str) -> Any:
    return diagnostic_from_parts(
        code=code,
        severity="ERROR",
        category="Compatibility",
        message=message,
        file=file,
        metadata={"target": CONTRACT_SCHEMA},
    )


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
