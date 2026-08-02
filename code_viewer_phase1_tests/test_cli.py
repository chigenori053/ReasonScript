from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from toolchain.code_viewer import Stage
from toolchain.code_viewer_cmd import run


ROOT = Path(__file__).resolve().parents[1]
DEPENDENCY_SOURCE = "examples/v0_5/003_calculation_dependency.rsn"


def test_view_json_succeeds_for_valid_source(capsys):
    exit_code = run([DEPENDENCY_SOURCE, "--json"], ROOT)
    captured = capsys.readouterr()

    assert exit_code == 0
    document = json.loads(captured.out)
    assert document["schema"] == "reasonscript-code-viewer/0.1"
    assert document["ok"] is True
    assert set(document["stages"]) == {"source", "surface", "semantic", "ir", "plan"}


def test_view_json_returns_2_when_pipeline_fails(tmp_path, capsys):
    broken = tmp_path / "broken.rsn"
    broken.write_text("module Broken {\n  calculation X {\n    result = \n  }\n}\n", encoding="utf-8")

    exit_code = run([str(broken), "--json"], ROOT)
    captured = capsys.readouterr()

    assert exit_code == 2
    document = json.loads(captured.out)
    assert document["ok"] is False


def test_view_missing_file_reports_cv_001(capsys):
    exit_code = run(["does_not_exist.rsn", "--json"], ROOT)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "CV-001" in captured.out


def test_view_unknown_stage_reports_cv_002(capsys):
    exit_code = run([DEPENDENCY_SOURCE, "--stage", "bogus"], ROOT)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "CV-002" in captured.out


def test_view_with_no_arguments_prints_usage(capsys):
    exit_code = run([], ROOT)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Usage" in captured.out


def test_view_without_flags_auto_degrades_to_plain_when_not_a_tty(capsys):
    # pytest's capsys makes sys.stdout.isatty() False, exactly like a CI
    # pipe — this is the non-interactive fallback path from design doc §10.
    exit_code = run([DEPENDENCY_SOURCE], ROOT)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert DEPENDENCY_SOURCE.split("/")[-1] in captured.out or "CalculationDependency" in captured.out
    assert "?:help q:quit" in captured.out


def test_view_launches_tui_when_attached_to_a_real_terminal(monkeypatch):
    # code_viewer_cmd imports run_tui lazily (inside the function body) so
    # that a Windows host without windows-curses only fails at call time,
    # not at module import time. That means patching the attribute on
    # toolchain.code_viewer.tui *before* run() is called is enough to
    # intercept the lazy `from ... import run_tui`.
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    calls: dict[str, Any] = {}

    def fake_run_tui(document, *, initial_stage):
        calls["document"] = document
        calls["initial_stage"] = initial_stage
        return 0

    monkeypatch.setattr("toolchain.code_viewer.tui.run_tui", fake_run_tui)

    exit_code = run([DEPENDENCY_SOURCE, "--stage", "ir"], ROOT)

    assert exit_code == 0
    assert calls["initial_stage"] == Stage.IR
    assert calls["document"].ok is True


def test_view_falls_back_to_plain_when_tui_cannot_be_imported(monkeypatch, capsys):
    # Simulates Windows without the windows-curses extra (design doc §11,
    # diagnostic CV-006): `sys.modules[name] = None` is the standard trick
    # to make a subsequent import of that module raise ImportError.
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setitem(sys.modules, "toolchain.code_viewer.tui", None)

    exit_code = run([DEPENDENCY_SOURCE], ROOT)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "windows-curses" in captured.err
    assert "?:help q:quit" in captured.out


def test_view_plain_succeeds_for_valid_source(capsys):
    exit_code = run([DEPENDENCY_SOURCE, "--plain", "--stage", "plan", "--width", "100"], ROOT)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "module: CalculationDependency" in captured.out
    assert "1:Source" in captured.out and "5:Plan*" in captured.out
    for line in captured.out.splitlines():
        assert len(line) <= 100


def test_view_plain_returns_2_when_pipeline_fails(tmp_path, capsys):
    broken = tmp_path / "broken.rsn"
    broken.write_text("module Broken {\n  calculation X {\n    result = \n  }\n}\n", encoding="utf-8")

    exit_code = run([str(broken), "--plain"], ROOT)
    captured = capsys.readouterr()

    assert exit_code == 2
    # The default --stage is source, which never carries diagnostics itself
    # (design doc §9) — the footer's error count is what tells the user
    # something failed without having to inspect the exit code.
    assert "stage error(s)" in captured.out


def test_view_plain_on_failing_stage_shows_the_diagnostic(tmp_path, capsys):
    broken = tmp_path / "broken.rsn"
    broken.write_text("module Broken {\n  calculation X {\n    result = \n  }\n}\n", encoding="utf-8")

    exit_code = run([str(broken), "--plain", "--stage", "surface"], ROOT)
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "SyntaxError" in captured.out
