import pytest

from playground.backend import workspace
from playground.backend.main import (
    WorkspaceListRequest,
    WorkspaceReadRequest,
    WorkspaceSaveRequest,
    workspace_list_endpoint,
    workspace_read_endpoint,
    workspace_save_endpoint,
)


def _make_workspace(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.rsn").write_text("module Hello {}\n", encoding="utf-8")
    (tmp_path.parent / "outside.rsn").write_text("module Outside {}\n", encoding="utf-8")
    return tmp_path


def test_resolve_within_workspace_rejects_parent_traversal(tmp_path):
    root = _make_workspace(tmp_path)
    with pytest.raises(workspace.WorkspacePathError) as exc_info:
        workspace.resolve_within_workspace(root, "../outside.rsn")
    assert exc_info.value.code == "PATH_TRAVERSAL"


def test_resolve_within_workspace_rejects_deep_traversal(tmp_path):
    root = _make_workspace(tmp_path)
    with pytest.raises(workspace.WorkspacePathError):
        workspace.resolve_within_workspace(root, "../../../../etc/passwd")


def test_resolve_within_workspace_allows_nested_path(tmp_path):
    root = _make_workspace(tmp_path)
    resolved = workspace.resolve_within_workspace(root, "src/main.rsn")
    assert resolved == (root / "src" / "main.rsn").resolve()


def test_read_endpoint_rejects_path_traversal(tmp_path):
    root = _make_workspace(tmp_path)
    result = workspace_read_endpoint(WorkspaceReadRequest(workspace_root=str(root), relative_path="../outside.rsn"))
    assert result["ok"] is False
    assert result["error"]["code"] == "PATH_TRAVERSAL"


def test_save_endpoint_rejects_path_traversal(tmp_path):
    root = _make_workspace(tmp_path)
    result = workspace_save_endpoint(
        WorkspaceSaveRequest(workspace_root=str(root), relative_path="../outside.rsn", content="module Evil {}\n")
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "PATH_TRAVERSAL"
    assert not (tmp_path.parent / "outside.rsn").read_text(encoding="utf-8").startswith("module Evil")


def test_list_endpoint_rejects_nonexistent_root(tmp_path):
    result = workspace_list_endpoint(WorkspaceListRequest(workspace_root=str(tmp_path / "does-not-exist")))
    assert result["ok"] is False
    assert result["error"]["code"] == "NOT_FOUND"


def test_list_endpoint_rejects_file_as_root(tmp_path):
    root = _make_workspace(tmp_path)
    result = workspace_list_endpoint(WorkspaceListRequest(workspace_root=str(root / "src" / "main.rsn")))
    assert result["ok"] is False
    assert result["error"]["code"] == "NOT_A_DIRECTORY"
