from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import toolchain.golden as golden
from toolchain.golden import (
    discover_cases,
    evaluate_case,
    run_case,
    run_corpus,
    stable_json,
    update_case,
    update_manifest,
    validate_corpus,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "scripts" / "dev.py"
REASON = REPO_ROOT / "reason"
CORPUS = REPO_ROOT / "golden"


def _codes(document: dict[str, object]) -> set[str]:
    diagnostics = document.get("diagnostics")
    assert isinstance(diagnostics, list)
    return {str(item["code"]) for item in diagnostics if isinstance(item, dict)}


def _write_case(
    root: Path,
    category_dir: str,
    name: str,
    *,
    test_id: str = "GT-TEMP",
    category: str = "Valid",
    language_version: str = "0.5",
    expected: dict[str, object] | None = None,
    include_metadata: bool = True,
    include_expected: bool = True,
) -> Path:
    case = root / category_dir / name
    case.mkdir(parents=True, exist_ok=True)
    case.joinpath("test.rsn").write_text("module T {\n  calculation Answer {\n    result = 42\n  }\n}\n", encoding="utf-8")
    if include_metadata:
        case.joinpath("metadata.json").write_text(
            stable_json({
                "id": test_id,
                "name": name,
                "category": category,
                "language_version": language_version,
                "expected": "pass",
            }),
            encoding="utf-8",
        )
    if include_expected:
        default_expected = {"ok": True, "diagnostics": [], "artifacts": {}, "runtime": {}}
        case.joinpath("expected.json").write_text(
            stable_json(expected or (evaluate_case(case) if include_metadata else default_expected)),
            encoding="utf-8",
        )
    return case


def test_canonical_golden_corpus_structure_and_manifest() -> None:
    for directory in ["valid", "invalid", "runtime", "workspace", "artifacts", "diagnostics", "compatibility"]:
        assert (CORPUS / directory).exists(), directory
    manifest = json.loads((CORPUS / "golden_manifest.json").read_text(encoding="utf-8"))
    cases = discover_cases(CORPUS)
    assert manifest["schema"] == "reasonscript-golden-tests/1.0"
    assert manifest["total_cases"] == len(cases)
    assert (CORPUS / "valid" / "single_calculation" / "test.rsn").is_file()
    assert (CORPUS / "valid" / "single_calculation" / "metadata.json").is_file()
    assert (CORPUS / "valid" / "single_calculation" / "expected.json").is_file()


def test_golden_corpus_runs_and_is_deterministic(tmp_path: Path) -> None:
    first = run_corpus(CORPUS, out_dir=tmp_path / "first")
    second = run_corpus(CORPUS, out_dir=tmp_path / "second")
    assert first["summary"]["failed"] == 0
    assert stable_json(first["report"]["results"]) == stable_json(second["report"]["results"])
    assert (tmp_path / "first" / "golden_summary.json").is_file()
    assert (tmp_path / "first" / "golden_report.json").is_file()
    assert (tmp_path / "first" / "golden_diagnostics.json").is_file()


def test_reason_golden_cli_commands(tmp_path: Path) -> None:
    run_result = subprocess.run(
        [sys.executable, str(REASON), "golden", str(CORPUS), "--out", str(tmp_path), "--json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    dev_result = subprocess.run(
        [sys.executable, str(DEV), "reason", "golden-summary", str(CORPUS), "--json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    report = json.loads(run_result.stdout)
    summary = json.loads(dev_result.stdout)
    assert run_result.returncode == 0
    assert dev_result.returncode == 0
    assert report["schema"] == "reasonscript-golden-report/1.0"
    assert summary["schema"] == "reasonscript-golden-summary/1.0"
    assert (tmp_path / "golden_summary.json").is_file()


def test_update_golden_generates_expected_and_manifest(tmp_path: Path) -> None:
    case = _write_case(tmp_path, "valid", "generated", include_expected=False)
    expected = update_case(case)
    manifest = update_manifest(tmp_path)
    assert expected["schema"] == "reasonscript-golden-expected/1.0"
    assert (case / "expected.json").is_file()
    assert manifest["total_cases"] == 1
    assert validate_corpus(tmp_path)["diagnostics"] == []


def test_golden_validation_rules_gt_001_through_gt_010(tmp_path: Path, monkeypatch) -> None:
    _write_case(tmp_path / "missing_metadata", "valid", "case", include_metadata=False)
    assert "GT-001" in _codes(validate_corpus(tmp_path / "missing_metadata"))

    _write_case(tmp_path / "missing_expected", "valid", "case", include_expected=False)
    assert "GT-002" in _codes(validate_corpus(tmp_path / "missing_expected"))

    _write_case(tmp_path / "bad_category", "valid", "case", category="Bad")
    assert "GT-003" in _codes(validate_corpus(tmp_path / "bad_category"))

    dup = tmp_path / "duplicate"
    _write_case(dup, "valid", "a", test_id="GT-DUP")
    _write_case(dup, "valid", "b", test_id="GT-DUP")
    assert "GT-004" in _codes(validate_corpus(dup))

    _write_case(tmp_path / "bad_language", "valid", "case", language_version="9.9")
    assert "GT-005" in _codes(validate_corpus(tmp_path / "bad_language"))

    mismatch_root = tmp_path / "mismatch"
    case = _write_case(mismatch_root, "valid", "case")
    expected = json.loads(case.joinpath("expected.json").read_text(encoding="utf-8"))
    expected["artifacts"] = {}
    case.joinpath("expected.json").write_text(stable_json(expected), encoding="utf-8")
    result = run_case(case, mismatch_root)
    assert "GT-006" in _codes({"diagnostics": result["diagnostics"]})

    expected = evaluate_case(case)
    expected["diagnostics"] = [{"code": "NOPE", "severity": "ERROR", "category": "CLI"}]
    case.joinpath("expected.json").write_text(stable_json(expected), encoding="utf-8")
    result = run_case(case, mismatch_root)
    assert "GT-007" in _codes({"diagnostics": result["diagnostics"]})

    expected = evaluate_case(case)
    expected["runtime"] = {}
    case.joinpath("expected.json").write_text(stable_json(expected), encoding="utf-8")
    result = run_case(case, mismatch_root)
    assert "GT-008" in _codes({"diagnostics": result["diagnostics"]})

    nondeterministic_root = tmp_path / "nondeterministic"
    nondeterministic_case = _write_case(nondeterministic_root, "valid", "case")
    calls = {"count": 0}
    real_evaluate = golden.evaluate_case

    def fake_evaluate(path: Path) -> dict[str, object]:
        calls["count"] += 1
        value = real_evaluate(path)
        if calls["count"] == 2:
            value = dict(value)
            value["runtime"] = {}
        return value

    monkeypatch.setattr(golden, "evaluate_case", fake_evaluate)
    result = golden.run_case(nondeterministic_case, nondeterministic_root)
    assert "GT-009" in _codes({"diagnostics": result["diagnostics"]})

    manifest_mismatch = tmp_path / "manifest_mismatch"
    _write_case(manifest_mismatch, "valid", "case")
    manifest_mismatch.joinpath("golden_manifest.json").write_text(
        stable_json({"version": "1.0", "schema": "reasonscript-golden-tests/1.0", "language_version": "0.5", "total_cases": 99}),
        encoding="utf-8",
    )
    assert "GT-010" in _codes(validate_corpus(manifest_mismatch))
