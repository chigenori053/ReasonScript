from playground.backend.main import SourceRequest, _run_pipeline_artifacts


MODEL_SOURCE = """
model Example {
    calculation A {
        result = 10
    }
}
"""

MODULE_SOURCE = MODEL_SOURCE.replace("model Example", "module Example")


def test_diagnostics_view_consumes_diagnostics_json() -> None:
    artifacts, errors = _run_pipeline_artifacts(SourceRequest(source=MODEL_SOURCE))

    assert errors == []
    assert "diagnostics" in artifacts
    assert artifacts["diagnostics"] == []


def test_module_compatibility_notice_is_l7_info() -> None:
    artifacts, errors = _run_pipeline_artifacts(SourceRequest(source=MODULE_SOURCE))

    assert errors == []
    assert artifacts["diagnostics"] == [
        {
            "severity": "info",
            "layer": "L7",
            "code": "LL-001C-MODULE-COMPAT-INFO",
            "message": "module is supported as compatibility syntax. model is the preferred syntax for reasoning model definitions.",
        }
    ]
