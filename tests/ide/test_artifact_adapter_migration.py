from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"


def _read(path: str) -> str:
    return (UI_SRC / path).read_text(encoding="utf-8")


def test_browser_platform_uses_analyze_result_backed_artifact_adapter():
    source = _read("platform/browserAdapter.ts")

    assert "createBrowserArtifactAdapter" in source
    assert "setBrowserAnalyzeArtifactSource" in source
    assert "ARTIFACT_FIELDS" in source
    assert 'fileName: "ast.json"' in source
    assert 'fileName: "semantic_ast.json"' in source
    assert 'fileName: "reason_ir.json"' in source
    assert 'fileName: "execution_plan.json"' in source
    assert 'fileName: "simulation.json"' in source
    assert 'fileName: "knowledge.json"' in source
    assert 'fileName: "diagnostics.json"' in source
    assert 'fileName: "validation.json"' in source
    assert "artifacts: createBrowserArtifactAdapter()" in source


def test_artifacts_tab_reads_descriptors_and_content_through_adapter():
    source = _read("views/StandardLayoutViews.tsx")

    assert "getPlatformAdapter().artifacts" in source
    assert "adapter.getArtifactIndex" in source
    assert "adapter.readArtifact" in source
    assert "artifactDescriptors.map" in source
    assert "Raw JSON artifacts remain available" in source


def test_app_registers_latest_analyze_result_as_artifact_source():
    source = _read("App.tsx")

    assert "setAnalyzeArtifactSource(state)" in source
