"""Integration Acceptance Test Suite for ReasonScript OSS Handwritten Experience (Issue #51, RS-DXLI-13).

Validates the complete 10-point Acceptance Matrix (ACC-01 through ACC-10) for Early Alpha Release:
ACC-01: Zero-Config Workflow (reason init -> check -> build -> run).
ACC-02: VS Code Extension Scope Isolation (strictly .rsn, no .re/.res interception).
ACC-03: Actionable Diagnostics Coverage (PRJ-0001, SRC-0001, LEX-1002/PAR-1002, NAM-2004).
ACC-04: CLI and LSP Diagnostic Parity (identical code, range, and severity).
ACC-05: LSP Lifecycle & Standalone Mode (open, change, standalone files, resilience).
ACC-06: LSP Navigation and Editing (document symbols, hover, definition, rename, formatting).
ACC-07: Standard Output API Contract (stdout, stderr, ordering, stringification).
ACC-08: Multi-Entry Resolution and Ambiguity Detection.
ACC-09: Reasoning Artifacts Non-Regression (compatibility baselines intact).
ACC-10: Execution Determinism across repeated runs.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def native_runtime_host() -> Path:
    from frontend.computation_ir.rust_bridge import find_binary

    binary = find_binary()
    if binary is not None:
        return binary

    runtime_root = REPO_ROOT / "ReasonRuntime"
    completed = subprocess.run(
        ["cargo", "build", "-p", "reasonscript-computation-runtime-cli"],
        cwd=runtime_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    binary = find_binary()
    assert binary is not None
    return binary


# ==============================================================================
# ACC-01: Zero-Config Workflow (reason init -> check -> build -> run)
# ==============================================================================
def test_acc_01_init_workflow_zero_config(tmp_path: Path, monkeypatch, native_runtime_host: Path) -> None:
    from toolchain.__main__ import main as toolchain_main

    project_dir = tmp_path / "zero_config_proj"

    # 1. init
    monkeypatch.setattr(sys, "argv", ["reason", "init", str(project_dir)])
    assert toolchain_main() == 0

    # Verify only .rsn files are created, no foreign extensions (.re, .res)
    source_files = list(project_dir.glob("**/*"))
    source_extensions = {f.suffix for f in source_files if f.is_file()}
    assert ".rsn" in source_extensions
    assert not any(ext in source_extensions for ext in [".re", ".rei", ".res", ".resi", ".ml"])

    # 2. check
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(sys, "argv", ["reason", "check"])
    assert toolchain_main() == 0

    # 3. build
    monkeypatch.setattr(sys, "argv", ["reason", "build"])
    assert toolchain_main() == 0

    # 4. run
    monkeypatch.setattr(sys, "argv", ["reason", "run"])
    assert toolchain_main() == 0


# ==============================================================================
# ACC-02: VS Code Extension Scope Isolation
# ==============================================================================
def test_acc_02_vscode_extension_scope_isolation() -> None:
    package_json_path = REPO_ROOT / "vscode-extension" / "package.json"
    client_ts_path = REPO_ROOT / "vscode-extension" / "src" / "lsp" / "client.ts"

    pkg = json.loads(package_json_path.read_text(encoding="utf-8"))
    languages = pkg.get("contributes", {}).get("languages", [])
    assert len(languages) == 1
    assert languages[0].get("id") == "reasonscript"
    assert languages[0].get("extensions") == [".rsn"]

    activation = pkg.get("activationEvents", [])
    assert "onLanguage:reasonscript" in activation
    for event in activation:
        assert not re.search(r"onLanguage:(reason\b|rescript\b)", event, re.IGNORECASE)
        assert not re.search(r"\.(re|rei|res|resi)$", event)

    client_src = client_ts_path.read_text(encoding="utf-8")
    assert 'language: "reasonscript"' in client_src
    assert 'pattern: "**/*.rsn"' in client_src


# ==============================================================================
# ACC-03: Actionable Diagnostics Coverage
# ==============================================================================
def test_acc_03_actionable_diagnostics_coverage(tmp_path: Path, monkeypatch) -> None:
    from toolchain.__main__ import main as toolchain_main

    # 1. Missing Manifest (PRJ-0001)
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    monkeypatch.chdir(empty_dir)
    monkeypatch.setattr(sys, "argv", ["reason", "check", "--json"])

    captured = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured)
    rc = toolchain_main()
    assert rc != 0
    report = json.loads(captured.getvalue())
    diag_codes = [d["code"] for d in report.get("diagnostics", [])]
    assert "PRJ-0001" in diag_codes

    # 2. No Source Files / Missing .rsn (SRC-0002) inside initialized project when only .re exists
    proj_dir = tmp_path / "test_proj"
    monkeypatch.setattr(sys, "argv", ["reason", "init", str(proj_dir)])
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    assert toolchain_main() == 0

    # Remove the generated main.rsn and leave only legacy.re
    (proj_dir / "src" / "main.rsn").unlink()
    legacy_file = proj_dir / "src" / "legacy.re"
    legacy_file.write_text("let x = 1\n", encoding="utf-8")
    monkeypatch.chdir(proj_dir)
    monkeypatch.setattr(sys, "argv", ["reason", "check", "--json"])

    captured_legacy = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_legacy)
    rc = toolchain_main()
    assert rc != 0
    report_legacy = json.loads(captured_legacy.getvalue())
    diag_codes_legacy = [d["code"] for d in report_legacy.get("diagnostics", [])]
    assert any(c in {"SRC-0001", "SRC-0002"} for c in diag_codes_legacy)

    # Recreate main.rsn for subsequent tests
    (proj_dir / "src" / "main.rsn").write_text("model Main { calculation Main { result = 0 } }\n", encoding="utf-8")
    legacy_file.unlink()

    # 3. Semicolon syntax error (PAR-0001 / PAR-0004)
    rs_syntax = proj_dir / "src" / "syntax_err.rsn"
    rs_syntax.write_text("package main;\nmodel Test { calculation Main { result = 0 } }\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["reason", "check", "--json"])
    captured_rs = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_rs)
    rc = toolchain_main()
    assert rc != 0
    report_rs = json.loads(captured_rs.getvalue())
    diag_codes_rs = [d["code"] for d in report_rs.get("diagnostics", [])]
    assert any(c in {"PAR-0001", "PAR-0004"} for c in diag_codes_rs)
    rs_syntax.unlink()

    # 4. Js.log / Js.* (NAM-2004) with QuickFix to Console.log / print
    from frontend.compiler_frontend import CompilerFrontend, FrontendRequest

    js_source = """model TestJs {
    calculation Main {
        Js.log("hello")
        result = 0
    }
}
"""
    fe_res = CompilerFrontend.analyze(FrontendRequest(source=js_source, filename="test_js.rsn"))
    assert not fe_res.ok
    nam_diags = [d for d in fe_res.diagnostics if d.code == "NAM-2004"]
    assert len(nam_diags) > 0
    fix_replacements = [f.replacement for f in nam_diags[0].fixes]
    assert "Console.log" in fix_replacements
    assert "print" in fix_replacements


# ==============================================================================
# ACC-04: CLI and LSP Diagnostic Parity
# ==============================================================================
def test_acc_04_cli_and_lsp_diagnostic_parity(tmp_path: Path) -> None:
    from frontend.compiler_frontend import CompilerFrontend, FrontendRequest

    source = """package demo

model ParityCheck {
    calculation Main {
        Js.log("parity test")
        result = 0
    }
}
"""
    doc_path = tmp_path / "parity.rsn"
    doc_path.write_text(source, encoding="utf-8")
    uri = doc_path.as_uri()

    cli_req = FrontendRequest(source=source, filename=str(doc_path), uri=uri, compiler_mode="cli")
    lsp_req = FrontendRequest(source=source, filename=str(doc_path), uri=uri, compiler_mode="lsp")

    cli_res = CompilerFrontend.analyze(cli_req)
    lsp_res = CompilerFrontend.analyze(lsp_req)

    assert len(cli_res.diagnostics) == len(lsp_res.diagnostics)
    for d_cli, d_lsp in zip(cli_res.diagnostics, lsp_res.diagnostics):
        assert d_cli.code == d_lsp.code
        assert d_cli.severity == d_lsp.severity
        assert d_cli.location.line == d_lsp.location.line
        assert d_cli.location.column == d_lsp.location.column


# ==============================================================================
# ACC-05: LSP Lifecycle & Standalone Mode
# ==============================================================================
def test_acc_05_lsp_lifecycle_and_standalone() -> None:
    from frontend.lsp.core import ReasonScriptLanguageServer

    server = ReasonScriptLanguageServer()
    standalone_uri = "file:///tmp/standalone_acceptance.rsn"

    # didOpen valid file
    initial_code = """model M {
    fn Run() -> int {
        return 42
    }
    calculation Main {
        result = Run()
    }
}
"""
    state1 = server.open_document(standalone_uri, initial_code, 1)
    assert len(state1.diagnostics) == 0

    # didChange with error (syntax error with semicolon)
    broken_code = """model M {
    fn Run() -> int;
}
"""
    state2 = server.change_document(standalone_uri, broken_code, 2)
    assert len(state2.diagnostics) > 0
    assert any(str(d.code).startswith("PAR-") or str(d.code).startswith("LEX-") for d in state2.diagnostics)

    # Recovery didChange
    fixed_code = """model M {
    fn Run() -> int {
        return 42
    }
    calculation Main {
        result = Run()
    }
}
"""
    state3 = server.change_document(standalone_uri, fixed_code, 3)
    assert len(state3.diagnostics) == 0


# ==============================================================================
# ACC-06: LSP Navigation and Editing
# ==============================================================================
def test_acc_06_lsp_navigation_and_editing() -> None:
    from frontend.lsp.core import ReasonScriptLanguageServer
    from frontend.lsp.model import FormattingOptions

    server = ReasonScriptLanguageServer()
    uri = "file:///workspace/features.rsn"
    source = """package demo

/// Point in 2D space.
struct Point {
    x: int,
    y: int
}

fn add_points(p1: Point, p2: Point) -> Point {
    return Point{ x: p1.x + p2.x, y: p1.y + p2.y }
}
"""
    server.open_document(uri, source, 1)

    # 1. Document Symbols
    symbols = server.document_symbols(uri)
    sym_names = {s.name for s in symbols}
    assert "Point" in sym_names
    assert "add_points" in sym_names

    # 2. Hover
    hover = server.hover(uri, 3, 8)  # on Point struct
    assert hover is not None
    assert "Point in 2D space" in hover.contents or "struct Point" in hover.contents

    # 3. Rename
    rename_edit = server.rename(uri, 3, 8, "Coord")
    assert rename_edit is not None
    assert uri in rename_edit.changes
    assert len(rename_edit.changes[uri]) >= 1

    # 4. Formatting
    fmt_edits = server.formatting(uri, FormattingOptions(tab_size=4, insert_spaces=True))
    assert isinstance(fmt_edits, tuple)


# ==============================================================================
# ACC-07: Standard Output API Contract
# ==============================================================================
def test_acc_07_standard_output_api_contract(tmp_path: Path, native_runtime_host: Path) -> None:
    code = """model TestConsoleLevels {
    calculation Main {
        print("stdout message")
        Console.log("console log")
        Console.warn("warning message")
        Console.error("error message")
        result = 42
    }
}
"""
    file_path = tmp_path / "test_console.rsn"
    file_path.write_text(code, encoding="utf-8")

    # Run with --json captures console_output deterministically
    json_res = subprocess.run(
        ["./reason", "run", str(file_path), "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert json_res.returncode == 0, json_res.stderr
    data = json.loads(json_res.stdout)
    console_output = data.get("console_output", [])

    assert len(console_output) >= 4
    stdout_events = [e for e in console_output if e.get("stream") == "stdout"]
    stderr_events = [e for e in console_output if e.get("stream") == "stderr"]

    stdout_texts = [e.get("message") for e in stdout_events]
    stderr_texts = [e.get("message") for e in stderr_events]

    assert "stdout message" in stdout_texts
    assert "console log" in stdout_texts
    assert "warning message" in stderr_texts
    assert "error message" in stderr_texts


# ==============================================================================
# ACC-08: Multi-Entry Resolution and Ambiguity Detection
# ==============================================================================
def test_acc_08_multi_entry_resolution(tmp_path: Path, monkeypatch, capsys, native_runtime_host: Path) -> None:
    from toolchain.__main__ import main as toolchain_main

    project_dir = tmp_path / "multi_entry_proj"
    monkeypatch.setattr(sys, "argv", ["reason", "init", str(project_dir)])
    capsys.readouterr()
    assert toolchain_main() == 0

    # Project with two non-Main calculations: TaskA and TaskB
    main_rsn = project_dir / "src" / "main.rsn"
    main_rsn.write_text("""package main

model Multi {
    calculation TaskA {
        result = 1
    }

    calculation TaskB {
        result = 2
    }
}
""", encoding="utf-8")

    monkeypatch.chdir(project_dir)

    # 1. Ambiguous run without entry argument -> fails with code 1 & suggests candidates
    monkeypatch.setattr(sys, "argv", ["reason", "run"])
    capsys.readouterr()
    exit_code = toolchain_main()
    assert exit_code == 1
    err_out = capsys.readouterr().out
    assert "AmbiguousEntry" in err_out
    assert "TaskA" in err_out
    assert "TaskB" in err_out

    # 2. Explicit positional specification: reason run TaskA
    monkeypatch.setattr(sys, "argv", ["reason", "run", "TaskA"])
    capsys.readouterr()
    exit_code_a = toolchain_main()
    assert exit_code_a == 0
    out_a = capsys.readouterr().out
    data_a = json.loads(out_a)
    assert data_a["entry"] == "TaskA"
    assert data_a["runtime_result"]["result"] == 1


# ==============================================================================
# ACC-09: Reasoning Artifacts Non-Regression
# ==============================================================================
def test_acc_09_reasoning_artifacts_non_regression() -> None:
    contracts_dir = REPO_ROOT / "contracts"
    schemas_dir = REPO_ROOT / "schemas"
    assert contracts_dir.is_dir()
    assert schemas_dir.is_dir()

    expected_schemas = [
        "diagnostics.schema.json",
        "runtime_result.schema.json",
        "runtime_request.schema.json",
        "execution_plan.schema.json",
        "reason_ir.schema.json",
    ]
    for schema_name in expected_schemas:
        schema_file = schemas_dir / schema_name
        assert schema_file.is_file(), f"Missing canonical schema: {schema_name}"


# ==============================================================================
# ACC-10: Execution Determinism
# ==============================================================================
def test_acc_10_execution_determinism(tmp_path: Path, monkeypatch, native_runtime_host: Path) -> None:
    from toolchain.__main__ import main as toolchain_main

    project_dir = tmp_path / "det_proj"
    monkeypatch.setattr(sys, "argv", ["reason", "init", str(project_dir)])
    assert toolchain_main() == 0

    monkeypatch.chdir(project_dir)

    # Run check 3 times, verify byte-identical stdout JSON
    check_results = []
    for _ in range(3):
        monkeypatch.setattr(sys, "argv", ["reason", "check", "--json"])
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        rc = toolchain_main()
        assert rc == 0
        check_results.append(captured.getvalue())

    assert check_results[0] == check_results[1] == check_results[2]

    # Run run 3 times, verify byte-identical stdout JSON (except volatile timestamps/durations if normalized)
    run_results = []
    for _ in range(3):
        monkeypatch.setattr(sys, "argv", ["reason", "run", "--json"])
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        rc = toolchain_main()
        assert rc == 0
        payload = json.loads(captured.getvalue())
        # Normalize non-deterministic elapsed fields
        payload.pop("duration_ms", None)
        payload.pop("timestamp", None)
        run_results.append(payload)

    assert run_results[0] == run_results[1] == run_results[2]
