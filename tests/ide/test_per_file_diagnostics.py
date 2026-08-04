from playground.backend.main import SourceRequest, analyze_endpoint

ERROR_SOURCE = """
module Test {
  calculation Value {
    result = Unknown * 2
  }
}
"""


def test_diagnostics_carry_relative_path_when_source_context_given(tmp_path):
    (tmp_path / "broken.rsn").write_text(ERROR_SOURCE, encoding="utf-8")

    response = analyze_endpoint(SourceRequest(
        source=ERROR_SOURCE,
        source_context={"workspace_root": str(tmp_path), "relative_path": "broken.rsn", "dirty": False},
    ))

    assert response["ok"] is False
    assert response["diagnostics"]
    assert all(d["relative_path"] == "broken.rsn" for d in response["diagnostics"])


def test_diagnostics_have_no_relative_path_without_source_context():
    response = analyze_endpoint(SourceRequest(source=ERROR_SOURCE))

    assert response["ok"] is False
    assert response["diagnostics"]
    assert all("relative_path" not in d for d in response["diagnostics"])


def test_diagnostics_from_different_files_are_not_cross_tagged(tmp_path):
    (tmp_path / "a.rsn").write_text(ERROR_SOURCE, encoding="utf-8")
    (tmp_path / "b.rsn").write_text(ERROR_SOURCE, encoding="utf-8")

    response_a = analyze_endpoint(SourceRequest(
        source=ERROR_SOURCE,
        source_context={"workspace_root": str(tmp_path), "relative_path": "a.rsn", "dirty": False},
    ))
    response_b = analyze_endpoint(SourceRequest(
        source=ERROR_SOURCE,
        source_context={"workspace_root": str(tmp_path), "relative_path": "b.rsn", "dirty": False},
    ))

    assert all(d["relative_path"] == "a.rsn" for d in response_a["diagnostics"])
    assert all(d["relative_path"] == "b.rsn" for d in response_b["diagnostics"])
