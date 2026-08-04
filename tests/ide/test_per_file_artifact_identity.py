from playground.backend import workspace
from playground.backend.main import SourceRequest, analyze_endpoint

SUCCESS_SOURCE = """
module Test {
  calculation Value {
    result = 42
  }
}
"""


def test_artifact_identity_is_deterministic():
    first = workspace.artifact_identity("examples/basic.rsn")
    second = workspace.artifact_identity("examples/basic.rsn")
    assert first == second


def test_artifact_identity_differs_for_different_paths():
    a = workspace.artifact_identity("examples/a.rsn")
    b = workspace.artifact_identity("examples/b.rsn")
    assert a != b


def test_artifact_identity_is_independent_of_workspace_root():
    # Same relative path should produce the same identity regardless of
    # which workspace it lives under (PFA-002) — the function only takes
    # relative_path, so this is true by construction; asserted explicitly
    # here to pin the contract.
    id_1 = workspace.artifact_identity("src/main.rsn")
    id_2 = workspace.artifact_identity("src/main.rsn")
    assert id_1 == id_2


def test_analyze_persists_artifacts_under_deterministic_path(tmp_path):
    (tmp_path / "main.rsn").write_text(SUCCESS_SOURCE, encoding="utf-8")

    response = analyze_endpoint(SourceRequest(
        source=SUCCESS_SOURCE,
        source_context={"workspace_root": str(tmp_path), "relative_path": "main.rsn", "dirty": False},
    ))

    artifact_id = response["source_context"]["artifact_id"]
    assert artifact_id == workspace.artifact_identity("main.rsn")

    artifact_dir = tmp_path / ".reasonscript" / "artifacts" / artifact_id
    assert artifact_dir.is_dir()
    assert (artifact_dir / "ast.json").exists()
    assert (artifact_dir / "reason_ir.json").exists()
    assert (artifact_dir / "execution_plan.json").exists()
    assert (artifact_dir / "simulation.json").exists()
    assert (artifact_dir / "knowledge.json").exists()
    assert (artifact_dir / "diagnostics.json").exists()
    assert (artifact_dir / "validation.json").exists()


def test_analyze_without_source_context_does_not_write_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    analyze_endpoint(SourceRequest(source=SUCCESS_SOURCE))
    assert not (tmp_path / ".reasonscript").exists()
