from copy import deepcopy

from playground.backend.main import SourceRequest, _projection_summary, _run_pipeline_artifacts


SOURCE = """
module Example {
    calculation A {
        result = 10
    }
}
"""


def test_projection_does_not_change_core_artifacts() -> None:
    artifacts, errors = _run_pipeline_artifacts(SourceRequest(source=SOURCE))

    assert errors == []
    before = {
        "reason_ir": deepcopy(artifacts["reason_ir"]),
        "execution_plan": deepcopy(artifacts["execution_plan"]),
        "simulation": deepcopy(artifacts["simulation"]),
        "knowledge": deepcopy(artifacts["knowledge"]),
    }

    _projection_summary(artifacts["ast"], artifacts["reason_ir"])

    assert artifacts["reason_ir"] == before["reason_ir"]
    assert artifacts["execution_plan"] == before["execution_plan"]
    assert artifacts["simulation"] == before["simulation"]
    assert artifacts["knowledge"] == before["knowledge"]
