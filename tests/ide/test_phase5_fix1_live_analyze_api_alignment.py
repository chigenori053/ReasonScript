from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
BACKEND = REPO_ROOT / "playground" / "backend" / "main.py"


def _read_ui(path: str) -> str:
    return (UI_SRC / path).read_text(encoding="utf-8")


def test_build_project_state_uses_existing_analyze_endpoint():
    source = _read_ui("bridge.ts")

    assert 'fetch("/api/analyze"' in source
    assert 'method: "POST"' in source
    assert '"Content-Type": "application/json"' in source
    assert "JSON.stringify({" in source
    assert "source," in source
    assert "filename," in source
    assert "compiler_mode: compilerMode" in source


def test_build_project_state_does_not_reference_missing_project_state_endpoints():
    source = _read_ui("bridge.ts")

    assert "/api/build-project-state" not in source
    assert "/api/project-state" not in source


def test_build_project_state_preserves_project_state_normalization():
    source = _read_ui("bridge.ts")

    assert "function normalizeProjectState(" in source
    assert 'data.schema_version ?? "reasonscript-project-state/0.1"' in source
    assert 'data.compiler_version ?? "playground-backend"' in source
    assert "Array.isArray(data.source_files)" in source
    assert "Array.isArray(data.diagnostics)" in source
    assert "data.artifacts ?? null" in source
    assert "data.analysis ?? data.analyzer ?? null" in source
    assert "metadata.compiler_mode ?? data.compiler_mode ?? compilerMode" in source
    assert "data.generated_at ?? new Date().toISOString()" in source


def test_app_analyze_handler_remains_wired_to_project_store():
    source = _read_ui("App.tsx")

    analyze_index = source.index("const runBuild = useCallback(async () => {")
    build_index = source.index("buildProjectState(", analyze_index)
    set_state_index = source.index("store.setProjectState(state)", build_index)
    error_index = source.index("store.setLastError(message)", build_index)

    assert "store.setLastError(null)" in source[analyze_index:build_index]
    assert "compilerMode," in source[build_index:set_state_index]
    assert build_index < set_state_index
    assert set_state_index < error_index


def test_backend_exposes_post_analyze_without_requiring_missing_endpoints():
    source = BACKEND.read_text(encoding="utf-8")

    assert '@app.post("/api/analyze")' in source
    assert 'def analyze_endpoint(req: SourceRequest) -> dict[str, Any]:' in source
    assert '@app.post("/api/build-project-state")' not in source
    assert '@app.post("/api/project-state")' not in source


def test_vite_proxies_api_requests_to_backend():
    source = (REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "vite.config.ts").read_text(encoding="utf-8")

    assert '"/api": {' in source
    assert 'target: "http://127.0.0.1:8000"' in source
    assert "changeOrigin: true" in source
