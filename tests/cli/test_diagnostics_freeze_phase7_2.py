from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from toolchain.diagnostics import (
    CATEGORIES,
    SEVERITIES,
    diagnostic_from_parts,
    diagnostics_document,
    diagnostics_summary,
    render_diagnostics,
    stable_json,
    validate_diagnostic_registry,
    validate_diagnostics_document,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
REASON = REPO_ROOT / "reason"
DEV = REPO_ROOT / "scripts" / "dev.py"
VALID = REPO_ROOT / "examples" / "v0_5" / "002_single_calculation.rsn"


def _codes(diagnostics: list[dict[str, object]]) -> set[str]:
    return {str(diagnostic["code"]) for diagnostic in diagnostics}


def _valid_item(code: str = "WS-001", *, file: str = "a.rsn", line: int = 1, column: int = 1) -> dict[str, object]:
    return {
        "id": "diag-00000001",
        "code": code,
        "severity": "ERROR",
        "category": "Workspace",
        "message": "message",
        "location": {"file": file, "line": line, "column": column, "length": 1},
        "related_locations": [],
        "fix": {},
        "metadata": {},
    }


def test_diagnostic_model_has_frozen_severity_and_category_tables() -> None:
    assert SEVERITIES == ("ERROR", "WARNING", "INFO", "HINT")
    assert "Workspace" in CATEGORIES
    assert "Runtime" in CATEGORIES
    assert "Compatibility" in CATEGORIES


def test_diagnostic_document_is_stably_sorted_and_numbered() -> None:
    diagnostics = [
        diagnostic_from_parts(code="CAL-020", severity="ERROR", category="Calculation", message="B", file="b.rsn", line=2, column=1),
        diagnostic_from_parts(code="WS-001", severity="WARNING", category="Workspace", message="A", file="a.rsn", line=1, column=1),
    ]

    document = diagnostics_document(diagnostics)

    assert [item["id"] for item in document["diagnostics"]] == ["diag-00000001", "diag-00000002"]
    assert [item["code"] for item in document["diagnostics"]] == ["WS-001", "CAL-020"]
    assert stable_json(document) == stable_json(json.loads(stable_json(document)))


def test_diagnostics_summary_counts_by_severity_category_and_code() -> None:
    document = diagnostics_document([
        diagnostic_from_parts(code="WS-001", severity="ERROR", category="Workspace", message="A", file="a.rsn"),
        diagnostic_from_parts(code="FN-004", severity="WARNING", category="Function", message="B", file="b.rsn"),
    ])
    summary = diagnostics_summary(document)

    assert summary["total"] == 2
    assert summary["by_severity"]["ERROR"] == 1
    assert summary["by_category"]["Workspace"] == 1
    assert summary["codes"] == {"FN-004": 1, "WS-001": 1}


def test_cli_renderer_uses_canonical_human_format() -> None:
    rendered = render_diagnostics([
        diagnostic_from_parts(code="CAL-020", severity="ERROR", category="Calculation", message="Undefined variable.", file="src/main.rsn", line=10, column=5)
    ])

    assert rendered == "ERROR CAL-020\n\nUndefined variable.\n\nsrc/main.rsn:10:5"


def test_diagnostic_validation_rules_dg_001_through_dg_010() -> None:
    assert "DG-001" in _codes(validate_diagnostics_document({"version": "1.0", "diagnostics": [{**_valid_item(), "code": ""}]}))
    assert "DG-002" in _codes(validate_diagnostic_registry(["WS-001", "WS-001"]))
    assert "DG-003" in _codes(validate_diagnostics_document({"version": "1.0", "diagnostics": [{**_valid_item(), "severity": "fatal"}]}))
    assert "DG-004" in _codes(validate_diagnostics_document({"version": "1.0", "diagnostics": [{**_valid_item(), "location": {}}]}))
    assert "DG-005" in _codes(validate_diagnostics_document({"version": "1.0", "diagnostics": [{**_valid_item(), "category": "Bad"}]}))
    assert "DG-006" in _codes(validate_diagnostics_document({"version": "1.0", "diagnostics": "bad"}))
    assert "DG-007" in _codes(validate_diagnostics_document({"version": "1.0", "diagnostics": [{**_valid_item(), "fix": "bad"}]}))
    assert "DG-008" in _codes(validate_diagnostics_document({"version": "9.9", "diagnostics": []}))
    assert "DG-009" in _codes(validate_diagnostics_document({"version": "1.0", "diagnostics": [{**_valid_item(), "code": "BAD"}]}))
    assert "DG-010" in _codes(validate_diagnostics_document({
        "version": "1.0",
        "diagnostics": [
            {**_valid_item("CAL-020", file="z.rsn"), "category": "Calculation"},
            _valid_item("WS-001", file="a.rsn"),
        ],
    }))


def test_reason_artifacts_generate_canonical_diagnostics_files(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(DEV), "reason", "artifacts", str(VALID), "--out", str(tmp_path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    diagnostics = json.loads((tmp_path / "diagnostics.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "diagnostics_summary.json").read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert diagnostics["version"] == "1.0"
    assert diagnostics["data"]["diagnostics"] == []
    assert summary["data"]["schema"] == "reasonscript-diagnostics-summary/1.0"


def test_workspace_index_generates_diagnostics_artifacts(tmp_path: Path) -> None:
    tmp_path.joinpath("reason.toml").write_text(
        'name = "Example"\nversion = "0.5.0"\nlanguage = "0.5"\nworkspace = "1.0"\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(REASON), "index", str(tmp_path), "--json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    diagnostics = json.loads(tmp_path.joinpath("artifacts", "diagnostics.json").read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert "diagnostics.json" in payload["artifacts"]
    assert diagnostics["version"] == "1.0"
    assert diagnostics["data"]["version"] == "1.0"
