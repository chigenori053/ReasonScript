import json

from frontend.language_surface.integration import compile_program
from frontend.language_surface.nodes import to_json_value
from frontend.language_surface.parser import SurfaceReservedConstructError, parse
from playground.backend.engine import build_execution_plan, extract_knowledge, simulate
from playground.backend.main import SourceRequest, _run_pipeline_artifacts


MODEL_SOURCE = """
model Example {
    calculation A {
        result = 10
    }
}
"""

MODULE_SOURCE = MODEL_SOURCE.replace("model Example", "module Example")


def _core_artifacts(source: str) -> dict[str, object]:
    program = parse(source)
    reason_ir = compile_program(program)[0]
    execution_plan = build_execution_plan(reason_ir)
    simulation = simulate(reason_ir)
    knowledge = extract_knowledge(reason_ir, simulation)
    return {
        "surface_ast": to_json_value(program),
        "reason_ir": reason_ir,
        "execution_plan": execution_plan,
        "simulation": simulation,
        "knowledge": knowledge,
    }


def test_model_is_active_preferred_top_level_construct() -> None:
    artifacts, errors = _run_pipeline_artifacts(SourceRequest(source=MODEL_SOURCE))

    assert errors == []
    assert artifacts["ast"]["modules"][0]["source_kind"] == "model"
    assert artifacts["projection_summary"]["syntax_status"] == "preferred"
    assert artifacts["projection_summary"]["construct_type"] == "Reasoning Model"


def test_module_is_active_compatibility_top_level_construct() -> None:
    artifacts, errors = _run_pipeline_artifacts(SourceRequest(source=MODULE_SOURCE))

    assert errors == []
    assert artifacts["ast"]["modules"][0]["source_kind"] == "module"
    assert artifacts["projection_summary"]["syntax_status"] == "compatibility"
    assert artifacts["projection_summary"]["construct_type"] == "Compatibility Namespace Syntax"
    assert all(item.get("severity") != "error" for item in artifacts["diagnostics"])


def test_reserved_constructs_are_rejected_by_default() -> None:
    for construct in ("world", "system", "component"):
        source = MODEL_SOURCE.replace("model Example", f"{construct} Example")
        try:
            parse(source)
        except SurfaceReservedConstructError as error:
            assert error.code == "LL-002-RESERVED-TOP-LEVEL-CONSTRUCT"
            assert error.layer == "L1"
            assert error.severity == "error"
            assert construct in str(error)
        else:
            raise AssertionError(f"{construct} parsed without experimental activation")


def test_top_level_construct_policy_does_not_change_model_module_core_semantics() -> None:
    model_artifacts = _core_artifacts(MODEL_SOURCE)
    module_artifacts = _core_artifacts(MODULE_SOURCE)

    assert model_artifacts["reason_ir"] == module_artifacts["reason_ir"]
    assert model_artifacts["execution_plan"] == module_artifacts["execution_plan"]
    assert model_artifacts["simulation"] == module_artifacts["simulation"]
    assert model_artifacts["knowledge"] == module_artifacts["knowledge"]
    assert "source_kind" not in json.dumps(model_artifacts["reason_ir"], sort_keys=True)
