from playground.backend.main import SourceRequest, analyze_endpoint


SUCCESS_SOURCE = """
module Test {
  calculation Value {
    result = 42
  }
}
"""


ERROR_SOURCE = """
module Test {
  calculation Value {
    result = Unknown * 2
  }
}
"""


EXPECTED_STAGES = [
    "source",
    "surface_ast",
    "semantic_ast",
    "reason_ir",
    "execution_plan",
    "simulation",
    "knowledge",
    "diagnostics",
]


def test_analyze_response_contains_phase2_contract() -> None:
    response = analyze_endpoint(SourceRequest(source=SUCCESS_SOURCE, compiler_mode="default"))

    assert response["ok"] is True
    assert response["compiler_mode"] == "default"
    assert list(stage["id"] for stage in response["pipeline"]["stages"]) == EXPECTED_STAGES
    assert response["artifacts"]["ast"] is not None
    assert response["artifacts"]["reason_ir"] is not None
    assert response["artifacts"]["execution_plan"] is not None
    assert response["artifacts"]["simulation"] is not None
    assert response["artifacts"]["knowledge"] is not None
    assert response["views"]["execution_plan"]["steps"]
    assert response["views"]["simulation"]["trace"]
    assert "_states" in response["artifacts"]


def test_analyze_diagnostics_are_mapped_to_pipeline_stage() -> None:
    response = analyze_endpoint(SourceRequest(source=ERROR_SOURCE))

    assert response["ok"] is False
    assert response["diagnostics"]
    assert all("stage" in diagnostic for diagnostic in response["diagnostics"])
    assert all(diagnostic["severity"] in {"error", "warning", "info"} for diagnostic in response["diagnostics"])
    assert response["diagnostics"][0]["stage"] in {"semantic_ast", "reason_ir", "diagnostics"}

    stages = {stage["id"]: stage for stage in response["pipeline"]["stages"]}
    assert stages[response["diagnostics"][0]["stage"]]["status"] == "error"
    assert stages["execution_plan"]["status"] in {"skipped", "unavailable"}
    assert stages["simulation"]["status"] in {"skipped", "unavailable"}
    assert stages["knowledge"]["status"] in {"skipped", "unavailable"}
