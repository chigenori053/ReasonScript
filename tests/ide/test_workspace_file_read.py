from playground.backend import workspace


def _make_workspace(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.rsn").write_text("module Hello {}\n", encoding="utf-8")
    return tmp_path


def test_read_workspace_file_success(tmp_path):
    root = _make_workspace(tmp_path)
    result = workspace.read_workspace_file(root, "src/main.rsn")

    assert result["ok"] is True
    assert result["relative_path"] == "src/main.rsn"
    assert result["content"] == "module Hello {}\n"
    assert result["version"]
    assert result["read_only"] is False


def test_read_workspace_file_missing(tmp_path):
    root = _make_workspace(tmp_path)
    result = workspace.read_workspace_file(root, "src/does_not_exist.rsn")

    assert result["ok"] is False
    assert result["error"]["code"] == "NOT_FOUND"


def test_read_workspace_file_not_a_file(tmp_path):
    root = _make_workspace(tmp_path)
    result = workspace.read_workspace_file(root, "src")

    assert result["ok"] is False
    assert result["error"]["code"] == "NOT_A_FILE"


def test_read_workspace_file_after_external_deletion_is_missing(tmp_path):
    root = _make_workspace(tmp_path)
    first = workspace.read_workspace_file(root, "src/main.rsn")
    assert first["ok"] is True

    (root / "src" / "main.rsn").unlink()

    second = workspace.read_workspace_file(root, "src/main.rsn")
    assert second["ok"] is False
    assert second["error"]["code"] == "NOT_FOUND"


def test_scan_workspace_lists_source_and_ignored_files(tmp_path):
    root = _make_workspace(tmp_path)
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.js").write_text("x", encoding="utf-8")
    (tmp_path / "README.md").write_text("# readme", encoding="utf-8")

    files, scan_status = workspace.scan_workspace(root)

    names = {node["name"] for node in files}
    assert names == {"node_modules", "src", "README.md"}
    assert scan_status["status"] == "success"
    assert scan_status["truncated"] is False

    node_modules = next(n for n in files if n["name"] == "node_modules")
    assert node_modules["is_ignored"] is True
    assert node_modules["children"] == []

    readme = next(n for n in files if n["name"] == "README.md")
    assert readme["is_source"] is False

    src = next(n for n in files if n["name"] == "src")
    main_rsn = next(n for n in src["children"] if n["name"] == "main.rsn")
    assert main_rsn["is_source"] is True
    assert main_rsn["relative_path"] == "src/main.rsn"
    assert "path" not in main_rsn
