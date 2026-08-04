from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_DIR = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src" / "platform"


def _read(name: str) -> str:
    return (PLATFORM_DIR / name).read_text(encoding="utf-8")


def test_workspace_read_and_save_reject_invalid_paths_before_fetch():
    source = _read("browserAdapter.ts")

    read_validation = source.index("async readFile")
    read_fetch = source.index('"/api/workspace/read"')
    save_validation = source.index("async saveFile")
    save_fetch = source.index('"/api/workspace/save"')

    assert source.index("validateNormalizedRelativePath(request.relativePath)", read_validation) < read_fetch
    assert source.index("validateNormalizedRelativePath(request.relativePath)", save_validation) < save_fetch
    assert "relative_path: pathResult.relativePath" in source


def test_workspace_list_normalizes_backend_paths_before_ui_mapping():
    source = _read("browserAdapter.ts")

    assert "function mapWorkspaceNode" in source
    assert "validateNormalizedRelativePath(relativePath)" in source
    assert "relativePath: normalizedPath" in source
    assert "path: normalizedPath" in source


def test_artifact_requests_validate_optional_relative_path():
    source = _read("browserAdapter.ts")

    assert "request.relativePath" in source
    assert "validateNormalizedRelativePath(request.relativePath)" in source
