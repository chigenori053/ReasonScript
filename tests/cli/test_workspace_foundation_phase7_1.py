from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from toolchain.workspace_foundation import (
    GENERATED_ARTIFACTS,
    build_workspace_index,
    stable_json,
    write_workspace_artifacts,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
REASON = REPO_ROOT / "reason"


def _write_manifest(root: Path, *, language: str = "0.5", workspace: str = "1.0") -> None:
    root.joinpath("reason.toml").write_text(
        "\n".join([
            'name = "Example"',
            'version = "0.5.0"',
            f'language = "{language}"',
            f'workspace = "{workspace}"',
            'edition = "2026"',
            "",
        ]),
        encoding="utf-8",
    )


def _make_project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _write_manifest(root)
    root.joinpath("src").mkdir()
    root.joinpath("src", "main.rsn").write_text(
        "\n".join([
            "module Main {",
            "  fn Value() -> int {",
            "    return 42",
            "  }",
            "  calculation Answer {",
            "    result = Value()",
            "  }",
            "}",
            "",
        ]),
        encoding="utf-8",
    )
    root.joinpath("docs").mkdir()
    root.joinpath("docs", "README.md").write_text("# Example\n", encoding="utf-8")
    root.joinpath("node_modules").mkdir()
    root.joinpath("node_modules", "ignored.rsn").write_text("module Ignored {}\n", encoding="utf-8")
    return root


def _diagnostic_codes(root: Path) -> set[str]:
    return {diagnostic["code"] for diagnostic in build_workspace_index(root)["diagnostics"]}


def test_workspace_index_is_deterministic_for_identical_contents(tmp_path: Path) -> None:
    first = _make_project(tmp_path / "first")
    second = _make_project(tmp_path / "second")

    assert stable_json(build_workspace_index(first)) == stable_json(build_workspace_index(second))


def test_workspace_index_discovers_manifest_files_symbols_and_dependencies(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    index = build_workspace_index(root)

    assert index["schema"] == "reasonscript-workspace/1.0"
    assert index["project_info"]["name"] == "Example"
    assert [file["path"] for file in index["files"]] == ["docs/README.md", "reason.toml", "src/main.rsn"]
    assert "Ignored" not in {symbol["name"] for symbol in index["symbols"]}
    assert {symbol["kind"] for symbol in index["symbols"]} >= {"module", "function", "calculation"}
    assert index["diagnostics"] == []


def test_workspace_artifacts_are_generated_with_canonical_names(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    result = write_workspace_artifacts(root)

    assert result["artifacts"] == sorted(GENERATED_ARTIFACTS)
    assert {path.name for path in root.joinpath("artifacts").iterdir()} == set(GENERATED_ARTIFACTS)
    summary = json.loads(root.joinpath("artifacts", "project_summary.json").read_text(encoding="utf-8"))
    assert summary["project"] == "Example"
    assert summary["modules"] == 1


def test_reason_workspace_cli_outputs_summary(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    result = subprocess.run(
        [sys.executable, str(REASON), "summary", str(root), "--json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["schema"] == "reasonscript-project-summary/1.0"
    assert payload["project"] == "Example"


def test_reason_index_cli_generates_standard_artifacts(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, str(REASON), "index", str(root), "--out", str(out), "--json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["schema"] == "reasonscript-workspace-index/1.0"
    assert {path.name for path in out.iterdir()} == set(GENERATED_ARTIFACTS)


def test_validation_ws_001_missing_project_manifest(tmp_path: Path) -> None:
    assert "WS-001" in _diagnostic_codes(tmp_path)


def test_validation_ws_002_invalid_manifest(tmp_path: Path) -> None:
    tmp_path.joinpath("reason.toml").write_text('name = "Broken"\n', encoding="utf-8")
    assert "WS-002" in _diagnostic_codes(tmp_path)


def test_validation_ws_003_duplicate_module(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    tmp_path.joinpath("src").mkdir()
    tmp_path.joinpath("src", "a.rsn").write_text("module Same {}\n", encoding="utf-8")
    tmp_path.joinpath("src", "b.rsn").write_text("module Same {}\n", encoding="utf-8")
    assert "WS-003" in _diagnostic_codes(tmp_path)


def test_validation_ws_004_duplicate_symbol_in_same_module(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    tmp_path.joinpath("src").mkdir()
    tmp_path.joinpath("src", "main.rsn").write_text(
        "module Main {\n  calculation Answer {}\n  calculation Answer {}\n}\n",
        encoding="utf-8",
    )
    assert "WS-004" in _diagnostic_codes(tmp_path)


def test_validation_ws_005_circular_dependency(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    tmp_path.joinpath("src").mkdir()
    tmp_path.joinpath("src", "a.rsn").write_text("import B\nmodule A {}\n", encoding="utf-8")
    tmp_path.joinpath("src", "b.rsn").write_text("import A\nmodule B {}\n", encoding="utf-8")
    assert "WS-005" in _diagnostic_codes(tmp_path)


def test_validation_ws_006_unsupported_language_version(tmp_path: Path) -> None:
    _write_manifest(tmp_path, language="9.9")
    assert "WS-006" in _diagnostic_codes(tmp_path)


def test_validation_ws_007_workspace_version_mismatch(tmp_path: Path) -> None:
    _write_manifest(tmp_path, workspace="2.0")
    assert "WS-007" in _diagnostic_codes(tmp_path)


def test_validation_ws_008_invalid_project_layout(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    tmp_path.joinpath("src").write_text("not a directory\n", encoding="utf-8")
    assert "WS-008" in _diagnostic_codes(tmp_path)


def test_validation_ws_009_broken_source_reference(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    tmp_path.joinpath("src").mkdir()
    tmp_path.joinpath("src", "main.rsn").write_text("import Missing\nmodule Main {}\n", encoding="utf-8")
    assert "WS-009" in _diagnostic_codes(tmp_path)


def test_validation_ws_010_invalid_artifact_directory(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    tmp_path.joinpath("artifacts").write_text("not a directory\n", encoding="utf-8")
    assert "WS-010" in _diagnostic_codes(tmp_path)
