import json
from copy import deepcopy
from pathlib import Path

from frontend.language_surface.integration import compile_program, project_program
from frontend.language_surface.nodes import to_json_value
from frontend.language_surface.parser import parse
from playground.backend.engine import build_execution_plan, extract_knowledge, simulate


ROOT = Path(__file__).resolve().parents[2]

MODULE_SOURCE = """
module Example {
    calculation A {
        result = 10
    }

    calculation B {
        result = A * 2
    }
}
"""

MODEL_SOURCE = MODULE_SOURCE.replace("module Example", "model Example")


def _pipeline(source: str) -> dict[str, object]:
    program = parse(source)
    semantic_ast = project_program(program)[0]
    reason_ir = compile_program(program)[0]
    execution_plan = build_execution_plan(reason_ir)
    simulation = simulate(reason_ir)
    knowledge = extract_knowledge(reason_ir, simulation)
    return {
        "surface_ast": to_json_value(program),
        "semantic_ast": semantic_ast,
        "reason_ir": reason_ir,
        "execution_plan": execution_plan,
        "simulation": simulation,
        "knowledge": knowledge,
    }


def _without_source_kind(value: object) -> object:
    normalized = deepcopy(value)

    def visit(item: object) -> None:
        if isinstance(item, dict):
            item.pop("source_kind", None)
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(normalized)
    return normalized


def test_model_source_kind_is_preserved_in_surface_ast() -> None:
    module_ast = _pipeline(MODULE_SOURCE)["surface_ast"]
    model_ast = _pipeline(MODEL_SOURCE)["surface_ast"]

    assert module_ast["modules"][0]["source_kind"] == "module"
    assert model_ast["modules"][0]["source_kind"] == "model"
    assert json.dumps(module_ast, sort_keys=True) != json.dumps(model_ast, sort_keys=True)
    assert _without_source_kind(module_ast) == _without_source_kind(model_ast)


def test_module_and_model_lower_to_same_reason_ir() -> None:
    module_pipeline = _pipeline(MODULE_SOURCE)
    model_pipeline = _pipeline(MODEL_SOURCE)

    assert module_pipeline["reason_ir"] == model_pipeline["reason_ir"]
    assert "source_kind" not in json.dumps(module_pipeline["reason_ir"], sort_keys=True)


def test_module_and_model_generate_same_execution_plan() -> None:
    module_plan = _pipeline(MODULE_SOURCE)["execution_plan"]
    model_plan = _pipeline(MODEL_SOURCE)["execution_plan"]

    assert module_plan == model_plan
    for key in (
        "goal",
        "start_state",
        "target_state",
        "distance",
        "steps",
        "alternative_paths",
        "selected_branch",
        "selected_branches",
        "path_signature",
    ):
        if key in module_plan or key in model_plan:
            assert module_plan.get(key) == model_plan.get(key)


def test_module_and_model_generate_same_simulation_and_knowledge() -> None:
    module_pipeline = _pipeline(MODULE_SOURCE)
    model_pipeline = _pipeline(MODEL_SOURCE)

    assert module_pipeline["simulation"] == model_pipeline["simulation"]
    assert module_pipeline["knowledge"] == model_pipeline["knowledge"]
    assert module_pipeline["simulation"]["success"] == model_pipeline["simulation"]["success"]
    assert module_pipeline["simulation"].get("trace") == model_pipeline["simulation"].get("trace")
    assert json.dumps(module_pipeline["knowledge"], sort_keys=True) == json.dumps(
        model_pipeline["knowledge"],
        sort_keys=True,
    )


def test_language_layer_v0_6_b_specs_are_adopted() -> None:
    base_spec = (ROOT / "docs/specs/reasonscript_language_layer_v0_6.md").read_text()
    milestone_spec = (
        ROOT / "docs/specs/reasonscript_language_layer_v0_6_b.md"
    ).read_text()

    assert "LL-001B" in base_spec
    assert "Specification ID: reasonscript-language-layer/0.6-B" in milestone_spec
    assert "module/model Equivalence" in milestone_spec
    assert "L3-L6 must preserve semantic canonicality." in milestone_spec
