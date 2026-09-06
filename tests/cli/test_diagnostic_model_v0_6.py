"""Tests for ReasonScript common diagnostic model with Source Span and JSON contract (Issue #41)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from toolchain.diagnostics import (
    CATEGORIES,
    CODE_CATEGORY_PREFIXES,
    COMPILER_VERSION,
    DIAGNOSTICS_SCHEMA,
    DIAGNOSTICS_VERSION,
    RUNTIME_VERSION,
    DiagnosticFix,
    SourceLocation,
    SourcePosition,
    SourceSpan,
    category_for_code,
    diagnostic_from_mapping,
    diagnostic_from_parts,
    diagnostics_document,
    normalize_path,
    position_from_lsp,
    position_to_lsp,
    render_diagnostics,
    stable_json,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REASON = REPO_ROOT / "reason"
VALID_EXAMPLE = REPO_ROOT / "examples" / "v0_5" / "002_single_calculation.rsn"
INVALID_EXAMPLE = REPO_ROOT / "examples" / "v0_5" / "invalid" / "missing_module.rsn"
SCHEMA_PATH = REPO_ROOT / "schemas" / "diagnostics.schema.json"


def test_required_categories_and_prefixes_are_defined() -> None:
    required_prefixes = ("CLI", "SRC", "PRJ", "LEX", "PAR", "NAM", "TYP", "BLD", "RUN", "ICE")
    for prefix in required_prefixes:
        assert prefix in CODE_CATEGORY_PREFIXES, f"Prefix {prefix} must be defined in CODE_CATEGORY_PREFIXES"

    required_categories = ("CLI", "Source", "Project", "Lexer", "Parser", "Namespace", "Type", "Build", "Runtime", "ICE")
    for category in required_categories:
        assert category in CATEGORIES, f"Category {category} must be defined in CATEGORIES"

    assert category_for_code("SRC-0001") == "Source"
    assert category_for_code("PRJ-0002") == "Project"
    assert category_for_code("LEX-0001") == "Lexer"
    assert category_for_code("PAR-0001") == "Parser"
    assert category_for_code("NAM-0001") == "Namespace"
    assert category_for_code("TYP-0001") == "Type"
    assert category_for_code("BLD-0001") == "Build"
    assert category_for_code("RUN-0001") == "Runtime"
    assert category_for_code("ICE-0001") == "ICE"
    assert category_for_code("CLI-0001") == "CLI"


def test_source_span_and_position_modeling() -> None:
    pos_start = SourcePosition(line=10, column=5, offset=120)
    pos_end = SourcePosition(line=10, column=15, offset=130)
    span = SourceSpan(start=pos_start, end=pos_end)

    diag = diagnostic_from_parts(
        code="PAR-0001",
        message="Expected identifier",
        file="src/main.rsn",
        line=10,
        column=5,
        length=10,
        span=span,
        title="Syntax error",
        help="Provide a valid identifier name",
        fixes=[DiagnosticFix(title="Insert identifier", description="Add variable name", replacement="foo", span=span)],
    )

    d = diag.to_dict()
    assert d["code"] == "PAR-0001"
    assert d["category"] == "Parser"
    assert d["title"] == "Syntax error"
    assert d["help"] == "Provide a valid identifier name"
    assert d["location"]["file"] == "src/main.rsn"
    assert d["location"]["line"] == 10
    assert d["location"]["column"] == 5
    assert d["location"]["span"]["start"]["line"] == 10
    assert d["location"]["span"]["start"]["column"] == 5
    assert d["location"]["span"]["start"]["offset"] == 120
    assert d["location"]["span"]["end"]["line"] == 10
    assert d["location"]["span"]["end"]["column"] == 15
    assert d["location"]["span"]["end"]["offset"] == 130
    assert len(d["fix_candidates"]) == 1
    assert d["fix_candidates"][0]["title"] == "Insert identifier"


def test_diagnostics_document_holds_versions() -> None:
    diag = diagnostic_from_parts(code="TYP-0001", message="Type mismatch", file="a.rsn")
    doc = diagnostics_document([diag])

    assert doc["version"] == DIAGNOSTICS_VERSION
    assert doc["schema"] == DIAGNOSTICS_SCHEMA
    assert "compiler_version" in doc
    assert "runtime_version" in doc
    assert doc["compiler_version"] == COMPILER_VERSION
    assert doc["runtime_version"] == RUNTIME_VERSION
    assert len(doc["diagnostics"]) == 1


def test_path_normalization_and_deterministic_order() -> None:
    diag1 = diagnostic_from_parts(code="TYP-0002", message="Error B", file="src/b.rsn", line=5, column=2)
    diag2 = diagnostic_from_parts(code="PAR-0001", message="Error A", file="src/a.rsn", line=2, column=1)
    diag3 = diagnostic_from_parts(code="PAR-0002", message="Error C", file="src/a.rsn", line=10, column=1)

    doc1 = diagnostics_document([diag1, diag2, diag3])
    doc2 = diagnostics_document([diag3, diag1, diag2])

    # Both documents must have identical order
    codes1 = [item["code"] for item in doc1["diagnostics"]]
    codes2 = [item["code"] for item in doc2["diagnostics"]]
    assert codes1 == codes2 == ["PAR-0001", "PAR-0002", "TYP-0002"]

    # Byte-stable JSON serialization across multiple runs
    assert stable_json(doc1) == stable_json(doc2)


def test_lsp_position_conversions() -> None:
    lsp_pos = position_to_lsp(line=1, column=1)
    assert lsp_pos == {"line": 0, "character": 0}

    lsp_pos10 = position_to_lsp(line=10, column=5)
    assert lsp_pos10 == {"line": 9, "character": 4}

    orig_line, orig_col = position_from_lsp(line=9, character=4)
    assert orig_line == 10
    assert orig_col == 5


def test_schema_conformance() -> None:
    schema_content = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema_content["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema_content["properties"]["schema"]["const"] == "reasonscript-diagnostics/1.0"
    assert "$defs" in schema_content
    assert "position" in schema_content["$defs"]
    assert "span" in schema_content["$defs"]
    assert "diagnostic" in schema_content["$defs"]

    span = SourceSpan(start=SourcePosition(line=1, column=1, offset=0), end=SourcePosition(line=1, column=5, offset=4))
    diag = diagnostic_from_parts(
        code="PAR-0001",
        message="Unexpected token",
        file="src/main.rsn",
        line=1,
        column=1,
        length=4,
        span=span,
        title="Syntax error",
        help="Check syntax",
        fixes=[DiagnosticFix(title="Fix it", replacement="val", span=span)],
    )
    doc = diagnostics_document([diag])

    # Check structural compatibility against schema definition
    assert doc["version"] == "1.0"
    assert doc["schema"] == "reasonscript-diagnostics/1.0"
    assert len(doc["diagnostics"]) == 1
    d = doc["diagnostics"][0]
    assert all(k in d for k in schema_content["$defs"]["diagnostic"]["required"])

    try:
        import jsonschema

        jsonschema.validate(instance=doc, schema=schema_content)
    except ImportError:
        pass


def test_human_and_json_correspondence() -> None:
    diag = diagnostic_from_parts(
        code="PAR-0001",
        severity="ERROR",
        message="Unexpected token 'foo'",
        file="src/test.rsn",
        line=5,
        column=10,
        title="Parse failure",
        help="Remove token 'foo'",
    )
    rendered = render_diagnostics([diag])
    doc = diagnostics_document([diag])
    item = doc["diagnostics"][0]

    assert item["code"] == "PAR-0001"
    assert item["severity"] == "ERROR"
    assert item["message"] == "Unexpected token 'foo'"
    assert item["title"] == "Parse failure"
    assert item["help"] == "Remove token 'foo'"
    assert item["location"]["file"] == "src/test.rsn"
    assert item["location"]["line"] == 5
    assert item["location"]["column"] == 10

    # Human rendering corresponds to JSON fields
    assert "ERROR PAR-0001: Parse failure" in rendered
    assert "Unexpected token 'foo'" in rendered
    assert "src/test.rsn:5:10" in rendered
    assert "help: Remove token 'foo'" in rendered


def test_cli_check_diagnostic_format_json_single_file() -> None:
    # Run reason check on invalid example with --diagnostic-format json
    result = subprocess.run(
        [str(REASON), "check", str(INVALID_EXAMPLE), "--diagnostic-format", "json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    doc = json.loads(result.stdout)
    assert doc["version"] == "1.0"
    assert doc["schema"] == "reasonscript-diagnostics/1.0"
    assert len(doc["diagnostics"]) >= 1
    first = doc["diagnostics"][0]
    assert "code" in first
    assert "severity" in first
    assert "location" in first
    assert "message" in first

    # Same run produces identical output (deterministic)
    result2 = subprocess.run(
        [str(REASON), "check", str(INVALID_EXAMPLE), "--diagnostic-format", "json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.stdout == result2.stdout


def test_cli_check_diagnostic_format_json_valid_file() -> None:
    result = subprocess.run(
        [str(REASON), "check", str(VALID_EXAMPLE), "--diagnostic-format", "json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    doc = json.loads(result.stdout)
    assert doc["version"] == "1.0"
    assert doc["schema"] == "reasonscript-diagnostics/1.0"
    assert doc["diagnostics"] == []


def test_cli_check_diagnostic_format_json_workspace(tmp_path: Path) -> None:
    tmp_path.joinpath("reason.toml").write_text(
        '[package]\nname = "CheckProject"\nversion = "0.5.0"\n',
        encoding="utf-8",
    )
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    src_dir.joinpath("main.rsn").write_text(
        "module Main {\n  fn Answer() -> int {\n    return 42\n  }\n}\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(REASON), "check", "--diagnostic-format", "json"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    doc = json.loads(result.stdout)
    assert doc["version"] == "1.0"
    assert doc["schema"] == "reasonscript-diagnostics/1.0"
    assert doc["diagnostics"] == []
