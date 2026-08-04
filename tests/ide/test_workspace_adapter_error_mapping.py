from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BROWSER_ADAPTER = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src" / "platform" / "browserAdapter.ts"


def test_browser_workspace_adapter_maps_backend_errors_to_platform_error_kinds():
    source = BROWSER_ADAPTER.read_text(encoding="utf-8")

    assert 'code === "NOT_FOUND"' in source
    assert '"missing"' in source
    assert 'code === "PATH_TRAVERSAL"' in source
    assert '"path_traversal"' in source
    assert 'code === "PERMISSION_DENIED"' in source
    assert '"permission_denied"' in source
    assert 'code === "DECODE_ERROR"' in source
    assert '"invalid_encoding"' in source
    assert 'code === "VERSION_CONFLICT"' in source
    assert '"conflict"' in source
    assert 'code === "READ_ONLY"' in source
    assert '"read_only"' in source


def test_browser_workspace_adapter_maps_fetch_failures():
    source = BROWSER_ADAPTER.read_text(encoding="utf-8")

    assert 'response.status === 404 ? "missing"' in source
    assert 'response.status === 409 ? "conflict"' in source
    assert '"network_error"' in source
    assert "Request failed before a platform response was available." in source
