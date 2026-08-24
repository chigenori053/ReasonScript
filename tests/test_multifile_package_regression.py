"""Regression coverage for V-002/V-004 multi-file package isolation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from toolchain import build_cmd, check_cmd, runner_cmd
from toolchain.__main__ import main as toolchain_main
from toolchain.project_validation import validate_project
from toolchain.run_cmd import run


def _write_project(root: Path, *, with_calculation: bool = True) -> None:
    (root / "src").mkdir(parents=True)
    (root / "reason.toml").write_text(
        """[package]
name = "cross-run"
version = "0.1.0"

[runtime]
backend = "RuntimeReal"
""",
        encoding="utf-8",
    )
    (root / "src" / "model.rsn").write_text(
        """package crossrun
pub module model {
  pub fn Score(value: int) -> int {
    return value * 2
  }
  pub fn Identity(value: Tensor) -> Tensor {
    return value
  }
}
""",
        encoding="utf-8",
    )
    calculation = """
  calculation Main {
    result = model::Score(21)
  }
""" if with_calculation else ""
    (root / "src" / "train.rsn").write_text(
        f"""module Train {{
  import crossrun.model
{calculation}}}
""",
        encoding="utf-8",
    )


def test_check_build_and_project_validate_share_complete_module_graph(
    tmp_path: Path, capsys
) -> None:
    _write_project(tmp_path)

    assert check_cmd.run(tmp_path) == 0
    assert "2 file(s) validated" in capsys.readouterr().out

    assert build_cmd.run(tmp_path) == 0
    assert "2 file(s) compiled" in capsys.readouterr().out
    assert {path.name for path in (tmp_path / "target" / "ir").glob("*.json")} == {
        "Train.json",
        "model.json",
    }

    report = validate_project(tmp_path)
    assert report["status"] == "passed", report["diagnostics"]
    assert report["sources_passed"] == 2


def test_package_run_executes_imported_function_and_entry(tmp_path: Path, capsys) -> None:
    _write_project(tmp_path)
    assert build_cmd.run(tmp_path) == 0
    capsys.readouterr()

    assert run(tmp_path, entry="Train::Main", include_trace=True) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["entry"] == "Train::Main"
    assert payload["runtime_result"]["result"] == 42
    assert payload["runtime_result"]["calculations"] == {"Main": 42}
    assert payload["trace"] == []


def test_file_form_run_uses_package_context_and_does_not_ignore_entry(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    _write_project(tmp_path)
    assert build_cmd.run(tmp_path) == 0
    capsys.readouterr()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["reason", "run", "src/train.rsn", "--entry", "Train::Main", "--json"],
    )

    assert toolchain_main() == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["entry"] == "Train::Main"
    assert payload["runtime_result"]["calculations"] == {"Main": 42}


def test_run_rejects_unknown_or_missing_executable_entry(
    tmp_path: Path, capsys
) -> None:
    _write_project(tmp_path)
    assert build_cmd.run(tmp_path) == 0
    capsys.readouterr()
    assert run(tmp_path, entry="Train::Missing") == 1
    assert "UnknownEntry" in capsys.readouterr().out

    empty = tmp_path / "empty"
    _write_project(empty, with_calculation=False)
    assert build_cmd.run(empty) == 0
    capsys.readouterr()
    assert run(empty, entry="Train::Missing") == 1
    assert "UnknownEntry" in capsys.readouterr().out


def test_reason_test_resolves_imports_against_package_sources(
    tmp_path: Path, capsys
) -> None:
    _write_project(tmp_path)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "model_test.rsn").write_text(
        """module ModelTest {
  import crossrun.model
  calculation ImportedFunctionWorks {
    result = model::Score(20) == 40
  }
}
""",
        encoding="utf-8",
    )

    assert runner_cmd.run(tmp_path) == 0
    output = capsys.readouterr().out
    assert "PASS  model_test" in output
    assert "1 passed" in output


def test_build_removes_stale_ir_from_deleted_module(tmp_path: Path) -> None:
    _write_project(tmp_path)
    assert build_cmd.run(tmp_path) == 0
    stale = tmp_path / "target" / "ir" / "RemovedModule.json"
    stale.write_text("{}", encoding="utf-8")

    # Force a new cache key so the build performs artifact reconciliation.
    train = tmp_path / "src" / "train.rsn"
    train.write_text(train.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert build_cmd.run(tmp_path) == 0
    assert not stale.exists()
