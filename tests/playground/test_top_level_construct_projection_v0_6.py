from playground.backend.main import SourceRequest, _run_pipeline_artifacts


MODEL_SOURCE = """
model Example {
    calculation A {
        result = 10
    }
}
"""

MODULE_SOURCE = MODEL_SOURCE.replace("model Example", "module Example")


def test_top_level_construct_projection_policy() -> None:
    model_artifacts, model_errors = _run_pipeline_artifacts(SourceRequest(source=MODEL_SOURCE))
    module_artifacts, module_errors = _run_pipeline_artifacts(SourceRequest(source=MODULE_SOURCE))
    world_artifacts, world_errors = _run_pipeline_artifacts(
        SourceRequest(source=MODEL_SOURCE.replace("model Example", "world Example"))
    )

    assert model_errors == []
    assert module_errors == []
    assert model_artifacts["projection_summary"]["syntax_status"] == "preferred"
    assert module_artifacts["projection_summary"]["syntax_status"] == "compatibility"
    assert module_artifacts["projection_summary"]["core_semantics"] == "identical to model for v0.6-D"
    assert world_errors
    assert world_artifacts["projection_summary"] is None
