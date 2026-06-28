from playground.backend.main import ARTIFACT_FILES, SourceRequest, _run_pipeline_artifacts


SOURCE = """
model Playground {
    calculation Value {
        result = 1
    }
}
"""


def test_playground_pipeline_exposes_language_layer_diagnostics_artifact() -> None:
    artifacts, errors = _run_pipeline_artifacts(SourceRequest(source=SOURCE))

    assert errors == []
    assert ARTIFACT_FILES["diagnostics"] == "diagnostics.json"
    assert artifacts["diagnostics"] == []


def test_failed_playground_pipeline_exports_diagnostics_artifact() -> None:
    artifacts, errors = _run_pipeline_artifacts(SourceRequest(source="model Broken {"))

    assert errors
    assert artifacts["diagnostics"] == errors
    assert artifacts["validation"]["errors"] == errors
