from playground.backend.main import SourceRequest, _run_pipeline_artifacts


MODEL_SOURCE = """
model Example {
    calculation A {
        result = 10
    }
}
"""

MODULE_SOURCE = MODEL_SOURCE.replace("model Example", "module Example")


def _projection(source: str) -> dict[str, object]:
    artifacts, errors = _run_pipeline_artifacts(SourceRequest(source=source))

    assert errors == []
    return artifacts["projection_summary"]


def test_projection_summary_displays_source_kind() -> None:
    model_projection = _projection(MODEL_SOURCE)
    module_projection = _projection(MODULE_SOURCE)

    assert model_projection["source_kind"] == "model"
    assert module_projection["source_kind"] == "module"


def test_projection_marks_model_preferred_and_module_compatibility() -> None:
    model_projection = _projection(MODEL_SOURCE)
    module_projection = _projection(MODULE_SOURCE)

    assert model_projection["syntax_status"] == "preferred"
    assert model_projection["construct_type"] == "Reasoning Model"
    assert module_projection["syntax_status"] == "compatibility"
    assert module_projection["construct_type"] == "Compatibility Namespace Syntax"


def test_projection_displays_same_normalized_core_for_module_and_model() -> None:
    model_projection = _projection(MODEL_SOURCE)
    module_projection = _projection(MODULE_SOURCE)

    assert model_projection["normalized_core"] == module_projection["normalized_core"]
    assert model_projection["normalized_core"]["kind"] == "ReasonGraph"
    assert model_projection["normalized_core"]["namespace"] == "Example"
    assert model_projection["semantic_equivalence"]["core_layers_affected"] is False
    assert module_projection["semantic_equivalence"]["core_layers_affected"] is False
