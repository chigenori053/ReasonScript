"""Regression coverage for V-002/V-004 multi-file package isolation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from toolchain import build_cmd, check_cmd, runner_cmd
from toolchain.__main__ import main as toolchain_main
from toolchain.project_validation import validate_project
from toolchain.run_cmd import run


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def native_runtime_host() -> Path:
    """Build the actual host binary required by project-mode execution.

    `cargo test` creates only hashed test executables, whereas the Python
    bridge intentionally resolves the normal `reason-runtime-host` binary.
    Keeping the build here makes these integration tests independent of test
    order and of a developer having run a separate build command.
    """
    from frontend.computation_ir.rust_bridge import find_binary

    # Avoid an unnecessary Cargo lock/write when the host was already built.
    binary = find_binary()
    if binary is not None:
        return binary

    runtime_root = ROOT / "ReasonRuntime"
    completed = subprocess.run(
        ["cargo", "build", "-p", "reasonscript-computation-runtime-cli"],
        cwd=runtime_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    binary = find_binary()
    assert binary is not None, "cargo build did not produce reason-runtime-host"
    return binary


def _write_project(
    root: Path, *, with_calculation: bool = True, source_entry: str | None = None
) -> None:
    (root / "src").mkdir(parents=True)
    source_section = f'\n[source]\nentry = "{source_entry}"\n' if source_entry else ""
    (root / "reason.toml").write_text(
        f"""[package]
name = "cross-run"
version = "0.1.0"

[runtime]
backend = "RuntimeReal"
{source_section}""",
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
    tmp_path: Path, capsys, native_runtime_host: Path
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
    assert (tmp_path / "target/computation_ir/package.json").is_file()

    report = validate_project(tmp_path)
    assert report["status"] == "passed", report["diagnostics"]
    assert report["sources_passed"] == 2


def test_package_run_executes_imported_function_and_entry(
    tmp_path: Path, capsys, native_runtime_host: Path
) -> None:
    _write_project(tmp_path)
    assert build_cmd.run(tmp_path) == 0
    capsys.readouterr()

    assert run(tmp_path, entry="Train::Main", include_trace=True) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["entry"] == "Train::Main"
    assert payload["runtime_result"]["result"] == 42
    assert payload["runtime_result"]["calculations"] == {"Main": 42}
    assert payload["trace"] == []
    assert payload["execution_mode"] == "integrated-rust"
    assert "fallback_reason" not in payload["runtime_dispatch"]


def test_file_form_run_uses_package_context_and_does_not_ignore_entry(
    tmp_path: Path, capsys, monkeypatch, native_runtime_host: Path
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
    assert payload["execution_mode"] == "integrated-rust"
    assert payload["runtime_dispatch"]["selected"] == "rust_computation_vm"


def test_project_run_executes_built_computation_ir_without_reparsing_source(
    tmp_path: Path, capsys, native_runtime_host: Path
) -> None:
    _write_project(tmp_path)
    assert build_cmd.run(tmp_path) == 0
    capsys.readouterr()
    # The source remains present for package identity, but is deliberately
    # invalid after the build. A successful run proves the Rust path consumed
    # target/computation_ir/package.json rather than recompiling source.
    (tmp_path / "src/train.rsn").write_text("not valid ReasonScript\n", encoding="utf-8")

    assert run(tmp_path, entry="Train::Main") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["execution_mode"] == "integrated-rust"
    assert payload["runtime_result"]["result"] == 42


def test_run_rejects_unknown_or_missing_executable_entry(
    tmp_path: Path, capsys, native_runtime_host: Path
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


def test_explicit_source_entry_is_first_and_keeps_complete_module_graph(
    tmp_path: Path, capsys, native_runtime_host: Path
) -> None:
    _write_project(tmp_path, source_entry="src/train.rsn")

    assert check_cmd.run(tmp_path) == 0
    capsys.readouterr()
    assert build_cmd.run(tmp_path) == 0
    capsys.readouterr()
    assert run(tmp_path, entry="Train::Main") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["runtime_result"]["result"] == 42
    ast_payload = json.loads((tmp_path / "target/ast/package.json").read_text())
    assert ast_payload["sources"] == ["src/train.rsn", "src/model.rsn"]


def test_explicit_entry_outside_src_is_included_and_cached(
    tmp_path: Path, capsys, native_runtime_host: Path
) -> None:
    _write_project(tmp_path, source_entry="entry.rsn")
    (tmp_path / "entry.rsn").write_text(
        (tmp_path / "src/train.rsn").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "src/train.rsn").unlink()

    assert build_cmd.run(tmp_path) == 0
    capsys.readouterr()
    ast_payload = json.loads((tmp_path / "target/ast/package.json").read_text())
    assert ast_payload["sources"] == ["entry.rsn", "src/model.rsn"]

    (tmp_path / "entry.rsn").write_text(
        (tmp_path / "entry.rsn").read_text(encoding="utf-8").replace("Score(21)", "Score(22)"),
        encoding="utf-8",
    )
    assert build_cmd.run(tmp_path) == 0
    assert "Build succeeded" in capsys.readouterr().out


def test_explicit_missing_source_entry_is_rejected_consistently(
    tmp_path: Path, capsys
) -> None:
    _write_project(tmp_path, source_entry="src/missing.rsn")

    assert check_cmd.run(tmp_path) == 1
    assert "SourceEntryMissing" in capsys.readouterr().out
    assert build_cmd.run(tmp_path) == 1
    assert "SourceEntryMissing" in capsys.readouterr().out
    assert run(tmp_path) == 1
    assert "SourceEntryMissing" in capsys.readouterr().out
    report = validate_project(tmp_path)
    assert report["status"] == "failed"
    assert any(item["code"] == "SourceEntryMissing" for item in report["diagnostics"])
