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

    def fake_run_tui(document, *, initial_stage, **_tree_kwargs):
        calls["document"] = document
        calls["initial_stage"] = initial_stage
        calls["tree_kwargs"] = _tree_kwargs
        return 0

    monkeypatch.setattr("toolchain.code_viewer.tui.run_tui", fake_run_tui)

    exit_code = run([DEPENDENCY_SOURCE, "--stage", "ir"], ROOT)

    assert exit_code == 0
    assert calls["initial_stage"] == Stage.IR
    assert calls["document"].ok is True
    # An explicit file still gets the tree scanned (so `e` works right
    # away), just closed by default (design doc §17.4).
    assert calls["tree_kwargs"]["show_file_tree"] is False
    assert calls["tree_kwargs"]["tree_root"] == ROOT


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


# --- file tree browsing (design doc §17) -----------------------------------


def _project_dir(tmp_path):
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "water.rsn").write_text("module Water {}\n", encoding="utf-8")
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "decay.rsn").write_text("module Decay {}\n", encoding="utf-8")
    return tmp_path


def _capture_run_tui(monkeypatch):
    calls: dict[str, Any] = {}

    def fake_run_tui(document, *, initial_stage, **tree_kwargs):
        calls["document"] = document
        calls["initial_stage"] = initial_stage
        calls.update(tree_kwargs)
        return 0

    monkeypatch.setattr("toolchain.code_viewer.tui.run_tui", fake_run_tui)
    return calls


def test_view_on_a_directory_launches_tui_with_the_tree_open(tmp_path, monkeypatch):
    project = _project_dir(tmp_path)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    calls = _capture_run_tui(monkeypatch)

    exit_code = run([str(project)], ROOT)

    assert exit_code == 0
    assert calls["show_file_tree"] is True
    assert calls["tree_root"] == project
    assert calls["tree"] is not None
    # first_file() picks the shallowest file — both models/ and rules/ are
    # equally shallow here, so either is a valid, deterministic choice.
    assert calls["document"].source_path in {
        str((project / "models" / "water.rsn").resolve()),
        str((project / "rules" / "decay.rsn").resolve()),
    }


def test_view_with_no_arguments_browses_cwd_when_attached_to_a_tty(tmp_path, monkeypatch):
    project = _project_dir(tmp_path)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    calls = _capture_run_tui(monkeypatch)

    exit_code = run([], project)

    assert exit_code == 0
    assert calls["show_file_tree"] is True
    assert calls["tree_root"] == project


def test_view_with_no_arguments_still_prints_usage_when_not_a_tty(capsys):
    # capsys makes isatty() False — a script that forgot to pass a file
    # should get the old, unambiguous error, not silently start browsing.
    exit_code = run([], ROOT)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Usage" in captured.out


def test_view_on_a_directory_with_json_reports_cv_007(tmp_path, capsys):
    project = _project_dir(tmp_path)
    exit_code = run([str(project), "--json"], ROOT)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "CV-007" in captured.out


def test_view_on_a_directory_with_plain_reports_cv_007(tmp_path, capsys):
    project = _project_dir(tmp_path)
    exit_code = run([str(project), "--plain"], ROOT)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "CV-007" in captured.out


def test_view_on_a_directory_with_no_rsn_files_reports_cv_008(tmp_path, monkeypatch, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)

    exit_code = run([str(empty)], ROOT)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "CV-008" in captured.out


def test_view_root_option_widens_the_tree_beyond_a_single_file(tmp_path, monkeypatch):
    project = _project_dir(tmp_path)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    calls = _capture_run_tui(monkeypatch)

    exit_code = run([str(project / "models" / "water.rsn"), "--root", str(project)], ROOT)

    assert exit_code == 0
    assert calls["show_file_tree"] is False  # explicit file: tree available but closed
    assert calls["tree_root"] == project
    assert calls["tree"] is not None


def test_view_explicit_file_without_root_defaults_tree_to_project_root(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    calls = _capture_run_tui(monkeypatch)

    exit_code = run([DEPENDENCY_SOURCE], ROOT)

    assert exit_code == 0
    assert calls["tree_root"] == ROOT
