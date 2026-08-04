from playground.backend.main import SourceRequest, analyze_endpoint

SUCCESS_SOURCE = """
module Test {
  calculation Value {
    result = 42
  }
}
"""


def test_analyze_without_source_context_matches_phase2_contract():
    """Regression guard: omitting source_context must not change the Phase 2 response shape."""
    response = analyze_endpoint(SourceRequest(source=SUCCESS_SOURCE, compiler_mode="default"))

    assert response["ok"] is True
    assert "source_context" not in response
    assert all("relative_path" not in d for d in response["diagnostics"])


def test_analyze_with_source_context_echoes_it_back(tmp_path):
    (tmp_path / "main.rsn").write_text(SUCCESS_SOURCE, encoding="utf-8")

    response = analyze_endpoint(SourceRequest(
        source=SUCCESS_SOURCE,
        compiler_mode="default",
        source_context={
            "workspace_root": str(tmp_path),
            "relative_path": "main.rsn",
            "dirty": False,
        },
    ))

    assert response["ok"] is True
    assert response["source_context"]["relative_path"] == "main.rsn"
    assert response["source_context"]["workspace_root"] == str(tmp_path)
    assert response["source_context"]["dirty"] is False
    assert response["source_context"]["artifact_id"]


def test_analyze_with_source_context_preserves_dirty_flag(tmp_path):
    (tmp_path / "main.rsn").write_text(SUCCESS_SOURCE, encoding="utf-8")

    response = analyze_endpoint(SourceRequest(
        source=SUCCESS_SOURCE + "\n// edited\n",
        compiler_mode="default",
        source_context={"workspace_root": str(tmp_path), "relative_path": "main.rsn", "dirty": True},
    ))

    assert response["ok"] is True
    assert response["source_context"]["dirty"] is True
