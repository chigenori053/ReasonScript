"""The VS Code extension never launches executables from untrusted locations."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "vscode-extension"

# Loads the compiled resolver with a stub `vscode` module and prints its result.
RESOLVE_SCRIPT = r"""
const Module = require("module");
const [compiled, scenario] = process.argv.slice(1);
const state = JSON.parse(scenario);
const uri = (fsPath) => ({ fsPath, scheme: "file" });
const vscode = {
  workspace: {
    isTrusted: state.trusted,
    workspaceFolders: state.folders.map((folder) => ({ uri: uri(folder) })),
    textDocuments: state.document ? [{ languageId: "reasonscript", uri: uri(state.document) }] : [],
    getConfiguration: () => ({ get: () => "" }),
  },
  window: { activeTextEditor: undefined },
  Uri: { file: uri },
};
const load = Module._load;
Module._load = function (request, ...rest) {
  return request === "vscode" ? vscode : load.call(this, request, ...rest);
};
process.env.PATH = "";
console.log(JSON.stringify(require(compiled).resolveReasonExecutable()));
"""


def _resolve(*, trusted: bool, folders: list[Path], document: Path | None = None) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    scenario = {"trusted": trusted, "folders": [str(f) for f in folders],
                "document": str(document) if document else None}
    completed = subprocess.run(
        [node, "-e", RESOLVE_SCRIPT, str(EXT / "out/workspace/workspace.js"), json.dumps(scenario)],
        check=True, capture_output=True, text=True,
    )
    return json.loads(completed.stdout)


def _launcher(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    launcher = directory / "reason"
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    return launcher


def test_trusted_workspace_root_launcher_is_used(tmp_path):
    project = tmp_path / "project"
    launcher = _launcher(project)

    resolved = _resolve(trusted=True, folders=[project])

    assert resolved == {"path": str(launcher), "exists": True, "source": "workspace"}


def test_untrusted_workspace_launcher_is_ignored(tmp_path):
    project = tmp_path / "project"
    _launcher(project)

    resolved = _resolve(trusted=False, folders=[project])

    assert resolved["exists"] is False
    assert resolved["source"] == "path"


def test_parent_directory_launcher_is_ignored(tmp_path):
    _launcher(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    resolved = _resolve(trusted=True, folders=[project])

    assert resolved["exists"] is False


def test_document_search_stops_at_workspace_folder(tmp_path):
    _launcher(tmp_path)
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)

    resolved = _resolve(trusted=True, folders=[project], document=project / "src" / "main.rsn")

    assert resolved["exists"] is False


def test_document_without_workspace_folder_does_not_search_parents(tmp_path):
    _launcher(tmp_path)
    (tmp_path / "loose").mkdir()

    resolved = _resolve(trusted=True, folders=[], document=tmp_path / "loose" / "a.rsn")

    assert resolved["exists"] is False


def test_document_launcher_inside_workspace_folder_is_used(tmp_path):
    project = tmp_path / "project"
    launcher = _launcher(project / "tools")
    (project / "tools" / "src").mkdir()

    resolved = _resolve(trusted=True, folders=[project], document=project / "tools" / "src" / "main.rsn")

    assert resolved == {"path": str(launcher), "exists": True, "source": "document"}


def test_manifest_requires_trust_and_machine_scoped_executable_path():
    package = json.loads((EXT / "package.json").read_text(encoding="utf-8"))

    assert package["capabilities"]["untrustedWorkspaces"]["supported"] is False
    executable = package["contributes"]["configuration"]["properties"]["reasonscript.executablePath"]
    assert executable["scope"] == "machine"


def test_package_graph_runs_python_isolated_from_workspace():
    source = (EXT / "src/workspace/packageGraph.ts").read_text(encoding="utf-8")

    assert '"-I", "-c"' in source
