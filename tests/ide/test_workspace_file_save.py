import os

from playground.backend import workspace


def _make_workspace(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.rsn").write_text("module Hello {}\n", encoding="utf-8")
    return tmp_path


def test_save_workspace_file_writes_content_and_bumps_version(tmp_path):
    root = _make_workspace(tmp_path)
    before = workspace.read_workspace_file(root, "src/main.rsn")

    result = workspace.save_workspace_file(
        root, "src/main.rsn", "module Hello {\n  goal Reach\n}\n", expected_version=before["version"]
    )

    assert result["ok"] is True
    assert result["version"]

    after = workspace.read_workspace_file(root, "src/main.rsn")
    assert after["content"] == "module Hello {\n  goal Reach\n}\n"
    # A successful save always leaves editor_content == saved_content, i.e. dirty=false at the data layer.
    assert after["version"] == result["version"]


def test_save_workspace_file_creates_new_file(tmp_path):
    root = _make_workspace(tmp_path)
    result = workspace.save_workspace_file(root, "src/new_file.rsn", "module New {}\n")

    assert result["ok"] is True
    assert (root / "src" / "new_file.rsn").read_text(encoding="utf-8") == "module New {}\n"


def test_save_workspace_file_rejects_version_conflict(tmp_path):
    root = _make_workspace(tmp_path)
    before = workspace.read_workspace_file(root, "src/main.rsn")

    # Simulate an external change between read and save.
    (root / "src" / "main.rsn").write_text("module Hello { /* external edit */ }\n", encoding="utf-8")

    result = workspace.save_workspace_file(
        root, "src/main.rsn", "module Hello { /* my edit */ }\n", expected_version=before["version"]
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "VERSION_CONFLICT"
    assert "current_version" in result


def test_save_workspace_file_without_expected_version_always_succeeds(tmp_path):
    root = _make_workspace(tmp_path)
    result = workspace.save_workspace_file(root, "src/main.rsn", "module Hello { /* forced */ }\n")
    assert result["ok"] is True


def test_save_workspace_file_rejects_read_only(tmp_path):
    root = _make_workspace(tmp_path)
    target = root / "src" / "main.rsn"
    os.chmod(target, 0o444)
    try:
        result = workspace.save_workspace_file(root, "src/main.rsn", "module Hello { /* blocked */ }\n")
        assert result["ok"] is False
        assert result["error"]["code"] == "READ_ONLY"
    finally:
        os.chmod(target, 0o644)
