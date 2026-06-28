from playground.backend.main import SourceRequest, _run_pipeline_artifacts


def _diagnostic_for(source_kind: str) -> dict[str, object]:
    source = f"""
{source_kind} Example {{
    calculation A {{
        result = 10
    }}
}}
"""
    artifacts, errors = _run_pipeline_artifacts(SourceRequest(source=source))

    assert errors
    assert artifacts["diagnostics"] == errors
    assert artifacts["projection_summary"] is None
    assert artifacts["reason_ir"] == []
    return artifacts["diagnostics"][0]


def test_world_is_reserved_top_level_construct() -> None:
    diagnostic = _diagnostic_for("world")

    assert diagnostic["code"] == "LL-002-RESERVED-TOP-LEVEL-CONSTRUCT"
    assert diagnostic["layer"] == "L1"
    assert diagnostic["severity"] == "error"
    assert "future WorldModel syntax" in diagnostic["message"]


def test_system_is_reserved_top_level_construct() -> None:
    diagnostic = _diagnostic_for("system")

    assert diagnostic["code"] == "LL-002-RESERVED-TOP-LEVEL-CONSTRUCT"
    assert diagnostic["layer"] == "L1"
    assert diagnostic["severity"] == "error"
    assert "multi-model orchestration" in diagnostic["message"]


def test_component_is_reserved_top_level_construct() -> None:
    diagnostic = _diagnostic_for("component")

    assert diagnostic["code"] == "LL-002-RESERVED-TOP-LEVEL-CONSTRUCT"
    assert diagnostic["layer"] == "L1"
    assert diagnostic["severity"] == "error"
    assert "UI / SDK structural composition" in diagnostic["message"]
