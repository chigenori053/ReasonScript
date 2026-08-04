from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from frontend.language_surface import StructDeclarationNode, parse, to_json_value
from toolchain.ci import _check_golden
from toolchain.golden import run_corpus, validate_corpus

ROOT = Path(__file__).resolve().parents[2]
REASON = ROOT / "reason"


def _run_reason(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REASON), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def _struct(source: str) -> StructDeclarationNode:
    declaration = parse(source).modules[0].body[0]
    assert isinstance(declaration, StructDeclarationNode)
    return declaration


def test_gsr_001_existing_empty_golden_corpus_passes_standalone_and_ci_phase(
    tmp_path: Path,
) -> None:
    golden = tmp_path / "golden"
    golden.mkdir()

    standalone = _run_reason("golden", "--json", cwd=tmp_path)
    ci_ok, ci_diagnostics, ci_metadata = _check_golden(tmp_path)

    assert standalone.returncode == 0
    assert json.loads(standalone.stdout)["summary"] == {
        "failed": 0,
        "passed": 0,
        "schema": "reasonscript-golden-summary/1.0",
        "skipped": 0,
        "total": 0,
        "version": "1.0",
    }
    assert ci_ok is True
    assert ci_diagnostics == []
    assert ci_metadata is not None
    assert ci_metadata["total"] == 0
    assert "phase8_golden_validation" not in ci_metadata


def test_gsr_001_missing_golden_corpus_fails_with_gt_011_everywhere(
    tmp_path: Path,
) -> None:
    validation = validate_corpus(tmp_path / "golden")
    result = run_corpus(tmp_path / "golden")
    standalone = _run_reason("golden", "--json", cwd=tmp_path)
    ci_ok, ci_diagnostics, ci_metadata = _check_golden(tmp_path)

    assert {item["code"] for item in validation["diagnostics"]} == {"GT-011"}
    assert result["summary"]["failed"] == 1
    assert standalone.returncode == 1
    assert ci_ok is False
    assert [item.code for item in ci_diagnostics] == ["CI-006"]
    assert ci_metadata is not None
    assert ci_metadata["golden_diagnostics"][0]["code"] == "GT-011"


def test_gsr_002_compact_and_multiline_structs_have_equivalent_asts() -> None:
    compact = _struct(
        """
        module Shapes {
          export struct Point { x: int y: optional<map<string, [float]>> }
        }
        """
    )
    multiline = _struct(
        """
        module Shapes {
          export struct Point {
            x: int
            y: optional<map<string, [float]>>
          }
        }
        """
    )

    assert to_json_value(compact) == to_json_value(multiline)


def test_gsr_002_compact_struct_check_and_run() -> None:
    fixture = ROOT / "tests" / "fixtures" / "gsr_one_line_struct.rsn"

    checked = _run_reason("check", str(fixture))
    executed = _run_reason("run", str(fixture), "--json")

    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert executed.returncode == 0, executed.stdout + executed.stderr
    assert json.loads(executed.stdout)["runtime_result"]["result"] == 3


def test_gsr_002_malformed_compact_struct_has_parser_diagnostic(tmp_path: Path) -> None:
    source = tmp_path / "malformed.rsn"
    source.write_text(
        "module Broken {\n  struct Point { x int }\n}\n",
        encoding="utf-8",
    )

    checked = _run_reason("check", str(source), "--json")
    payload = json.loads(checked.stdout)

    assert checked.returncode == 1
    assert payload["diagnostics"][0]["code"] == "PARSE-001"


def test_gsr_003_global_help_forms_succeed() -> None:
    for argument in ("--help", "-h", "help"):
        result = _run_reason(argument)
        assert result.returncode == 0
        assert result.stdout.startswith("Usage: reason <command> [args]")
        assert "UnknownCommand" not in result.stdout


def test_gsr_003_unknown_command_remains_failure() -> None:
    result = _run_reason("definitely-unknown")
    assert result.returncode == 1
    assert "UnknownCommand" in result.stdout
