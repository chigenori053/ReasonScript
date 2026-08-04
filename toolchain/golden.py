"""Golden Test Corpus runner for reasonscript-golden-tests/1.0."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from playground.backend.main import SourceRequest, analyze_endpoint
from toolchain.diagnostics import diagnostic_from_parts, diagnostics_document

GOLDEN_VERSION = "1.0"
GOLDEN_SCHEMA = "reasonscript-golden-tests/1.0"
SUPPORTED_CATEGORIES = {
    "Valid",
    "Invalid",
    "Workspace",
    "Diagnostics",
    "Artifacts",
    "Compatibility",
    "Runtime",
    "LanguageSurface",
    "ExecutionPlan",
    "Simulation",
    "Knowledge",
}
SUPPORTED_LANGUAGE_VERSIONS = {"0.5", "0.7"}
GENERATED_OUTPUTS = (
    "golden_summary.json",
    "golden_report.json",
    "golden_diagnostics.json",
)


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def discover_cases(corpus_root: str | Path) -> list[Path]:
    root = Path(corpus_root)
    cases: list[Path] = []
    for metadata in sorted(root.glob("*/*/metadata.json"), key=lambda item: item.as_posix()):
        cases.append(metadata.parent)
    return cases


def load_manifest(corpus_root: str | Path) -> dict[str, Any]:
    root = Path(corpus_root)
    path = root / "golden_manifest.json"
    if not path.is_file():
        return {
            "version": GOLDEN_VERSION,
            "schema": GOLDEN_SCHEMA,
            "language_version": "0.5",
            "total_cases": len(discover_cases(root)),
        }
    return json.loads(path.read_text(encoding="utf-8"))


def validate_corpus(corpus_root: str | Path) -> dict[str, Any]:
    root = Path(corpus_root)
    diagnostics: list[Any] = []
    if not root.is_dir():
        return diagnostics_document([
            _gt_diag("GT-011", "Golden corpus directory not found", file=str(root))
        ])
    manifest = load_manifest(root)
    cases = discover_cases(root)
    if manifest.get("version") != GOLDEN_VERSION or manifest.get("total_cases") != len(cases):
        diagnostics.append(_gt_diag("GT-010", "Manifest mismatch", file="golden_manifest.json"))

    seen_ids: set[str] = set()
    for case in _candidate_case_dirs(root):
        if not (case / "metadata.json").is_file():
            diagnostics.append(_gt_diag("GT-001", "Missing metadata", file=_rel(root, case / "metadata.json")))
    for case in cases:
        metadata_path = case / "metadata.json"
        expected_path = case / "expected.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            diagnostics.append(_gt_diag("GT-001", "Missing metadata", file=_rel(root, metadata_path)))
            continue
        if not expected_path.is_file():
            diagnostics.append(_gt_diag("GT-002", "Missing expected output", file=_rel(root, expected_path)))
        category = metadata.get("category")
        if category not in SUPPORTED_CATEGORIES:
            diagnostics.append(_gt_diag("GT-003", f"Invalid category: {category}", file=_rel(root, metadata_path)))
        test_id = metadata.get("id")
        if test_id in seen_ids:
            diagnostics.append(_gt_diag("GT-004", f"Duplicate test id: {test_id}", file=_rel(root, metadata_path)))
        if isinstance(test_id, str):
            seen_ids.add(test_id)
        language_version = metadata.get("language_version")
        if language_version not in SUPPORTED_LANGUAGE_VERSIONS:
            diagnostics.append(_gt_diag("GT-005", f"Invalid language version: {language_version}", file=_rel(root, metadata_path)))
    return diagnostics_document(diagnostics)


def _candidate_case_dirs(root: Path) -> list[Path]:
    candidates = {path.parent for path in root.glob("*/*/test.rsn")}
    candidates.update(path.parent for path in root.glob("*/*/expected.json"))
    candidates.update(path.parent for path in root.glob("*/*/metadata.json"))
    return sorted(candidates, key=lambda item: item.as_posix())


def run_corpus(corpus_root: str | Path, *, out_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(corpus_root)
    validation = validate_corpus(root)
    cases = discover_cases(root)
    results = [run_case(case, root) for case in cases]
    validation_diags = validation["diagnostics"]
    passed = sum(1 for item in results if item["status"] == "passed")
    failed = sum(1 for item in results if item["status"] == "failed") + len(validation_diags)
    summary = {
        "version": GOLDEN_VERSION,
        "schema": "reasonscript-golden-summary/1.0",
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "skipped": 0,
    }
    report = {
        "version": GOLDEN_VERSION,
        "schema": "reasonscript-golden-report/1.0",
        "corpus": str(root),
        "summary": summary,
        "results": results,
    }
    diagnostics = diagnostics_document([
        diagnostic
        for result in results
        for diagnostic in result.get("diagnostics", [])
    ] + validation_diags)
    output = {
        "summary": summary,
        "report": report,
        "diagnostics": diagnostics,
    }
    if out_dir is not None:
        target = Path(out_dir)
        target.mkdir(parents=True, exist_ok=True)
        (target / "golden_summary.json").write_text(stable_json(summary), encoding="utf-8")
        (target / "golden_report.json").write_text(stable_json(report), encoding="utf-8")
        (target / "golden_diagnostics.json").write_text(stable_json(diagnostics), encoding="utf-8")
    return output


def run_case(case_dir: Path, corpus_root: Path | None = None) -> dict[str, Any]:
    root = corpus_root or case_dir.parents[1]
    metadata = json.loads((case_dir / "metadata.json").read_text(encoding="utf-8"))
    expected = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
    actual = evaluate_case(case_dir)
    diagnostics: list[Any] = []

    if actual != evaluate_case(case_dir):
        diagnostics.append(_gt_diag("GT-009", "Non-deterministic output", file=_rel(root, case_dir)))
    if expected.get("ok") != actual.get("ok"):
        diagnostics.append(_gt_diag("GT-008", "Runtime mismatch: ok status differs", file=_rel(root, case_dir / "expected.json")))
    if expected.get("diagnostics") != actual.get("diagnostics"):
        diagnostics.append(_gt_diag("GT-007", "Diagnostics mismatch", file=_rel(root, case_dir / "expected.json")))
    if expected.get("artifacts") != actual.get("artifacts"):
        diagnostics.append(_gt_diag("GT-006", "Artifact mismatch", file=_rel(root, case_dir / "expected.json")))
    if expected.get("runtime") != actual.get("runtime"):
        diagnostics.append(_gt_diag("GT-008", "Runtime mismatch", file=_rel(root, case_dir / "expected.json")))

    status = "passed" if not diagnostics else "failed"
    return {
        "id": metadata.get("id"),
        "name": metadata.get("name"),
        "category": metadata.get("category"),
        "status": status,
        "diagnostics": diagnostics_document(diagnostics)["diagnostics"],
    }


def evaluate_case(case_dir: str | Path) -> dict[str, Any]:
    case = Path(case_dir)
    metadata = json.loads((case / "metadata.json").read_text(encoding="utf-8"))
    source_path = case / "test.rsn"
    if not source_path.is_file():
        return {
            "ok": False,
            "diagnostics": [{"code": "GT-002", "severity": "ERROR", "category": "Compatibility"}],
            "artifacts": {},
            "runtime": {},
        }
    response = analyze_endpoint(SourceRequest(source=source_path.read_text(encoding="utf-8"), filename=str(source_path)))
    diagnostics = diagnostics_document(response.get("diagnostics", []))["diagnostics"]
    artifacts = response.get("artifacts") if isinstance(response.get("artifacts"), dict) else {}
    return {
        "version": GOLDEN_VERSION,
        "schema": "reasonscript-golden-expected/1.0",
        "ok": bool(response.get("ok")),
        "expected": metadata.get("expected"),
        "diagnostics": [
            {
                "code": item.get("code"),
                "severity": item.get("severity"),
                "category": item.get("category"),
            }
            for item in diagnostics
        ],
        "artifacts": _artifact_expectations(artifacts),
        "runtime": _runtime_expectations(response),
    }


def update_case(case_dir: str | Path) -> dict[str, Any]:
    case = Path(case_dir)
    expected = evaluate_case(case)
    (case / "expected.json").write_text(stable_json(expected), encoding="utf-8")
    return expected


def update_manifest(corpus_root: str | Path) -> dict[str, Any]:
    root = Path(corpus_root)
    cases = discover_cases(root)
    manifest = {
        "version": GOLDEN_VERSION,
        "schema": GOLDEN_SCHEMA,
        "language_version": "0.5",
        "total_cases": len(cases),
        "cases": sorted(_rel(root, case) for case in cases),
    }
    (root / "golden_manifest.json").write_text(stable_json(manifest), encoding="utf-8")
    return manifest


def update_corpus(corpus_root: str | Path) -> dict[str, Any]:
    root = Path(corpus_root)
    for case in discover_cases(root):
        update_case(case)
    return update_manifest(root)


def _artifact_expectations(artifacts: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ("ast", "semantic_ast", "reason_ir", "execution_plan", "simulation", "knowledge", "validation"):
        value = artifacts.get(key)
        if isinstance(value, dict):
            result[key] = {
                "present": True,
                "keys": sorted(str(item) for item in value.keys()),
                "schema": value.get("schema") or value.get("schema_version"),
            }
        else:
            result[key] = {"present": value is not None}
    return result


def _runtime_expectations(response: dict[str, Any]) -> dict[str, Any]:
    artifacts = response.get("artifacts") if isinstance(response.get("artifacts"), dict) else {}
    simulation = artifacts.get("simulation") if isinstance(artifacts.get("simulation"), dict) else {}
    knowledge = artifacts.get("knowledge") if isinstance(artifacts.get("knowledge"), dict) else {}
    execution_plan = artifacts.get("execution_plan") if isinstance(artifacts.get("execution_plan"), dict) else {}
    return {
        "execution_plan_keys": sorted(str(key) for key in execution_plan.keys()),
        "goal_reached": simulation.get("goal_reached") if isinstance(simulation, dict) else None,
        "knowledge_count": knowledge.get("knowledge_count") if isinstance(knowledge, dict) else None,
    }


def _gt_diag(code: str, message: str, *, file: str) -> Any:
    return diagnostic_from_parts(
        code=code,
        severity="ERROR",
        category="Compatibility",
        message=message,
        file=file,
        metadata={"rule": code},
    )


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
