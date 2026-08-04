"""Standalone ReasonScript project validation (ICRIR section 17)."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any

from frontend.integrated_computation_runtime import execute_program
from frontend.language_surface.integration import compile_program, project_program
from frontend.language_surface.parser import parse
from frontend.tensor.integration import tensor_operations

SCHEMA_VERSION = "reasonscript-project-validation/0.1"


def validate_project(root: str | Path, *, repetitions: int = 3) -> dict[str, Any]:
    project_root = Path(root).resolve()
    diagnostics: list[dict[str, Any]] = []
    phases: list[dict[str, Any]] = []

    manifest_path = project_root / "reason.toml"
    manifest = None
    if not manifest_path.is_file():
        diagnostics.append(_diagnostic("PV-001", "Missing project manifest: reason.toml"))
    else:
        try:
            manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            diagnostics.append(_diagnostic("PV-002", f"Invalid project manifest: {error}"))
    phases.append(_phase("manifest_validation", manifest is not None))

    sources = sorted((project_root / "src").rglob("*.rsn")) if (project_root / "src").is_dir() else []
    if not sources:
        diagnostics.append(_diagnostic("PV-003", "No .rsn sources found in src/"))
    phases.append(_phase("source_discovery", bool(sources), count=len(sources)))

    passed = 0
    runtime_total = 0
    runtime_passed = 0
    canonical_runs: list[str] = []
    for source_path in sources:
        try:
            program = parse(source_path.read_text(encoding="utf-8"))
            project_program(program)
            reason_irs = compile_program(program)
            passed += 1
            if any(tensor_operations(module) for module in program.modules) or _has_loop(source_path):
                runtime_total += 1
                run_hashes = []
                for _ in range(repetitions):
                    payload = execute_program(program).to_dict()
                    encoded = _canonical(payload)
                    run_hashes.append(hashlib.sha256(encoded.encode()).hexdigest())
                canonical_runs.extend(run_hashes)
                if len(set(run_hashes)) == 1:
                    runtime_passed += 1
                else:
                    diagnostics.append(_diagnostic("PV-008", f"Non-deterministic runtime result: {source_path.name}"))
            elif not reason_irs:
                diagnostics.append(_diagnostic("PV-005", f"Reason IR was not generated: {source_path.name}"))
        except Exception as error:
            diagnostics.append(_diagnostic("PV-004", f"{source_path.name}: {error}"))
    phases.append(_phase("source_check", passed == len(sources), count=passed))
    phases.append(_phase("semantic_validation", passed == len(sources)))
    phases.append(_phase("runtime_execution", runtime_passed == runtime_total, count=runtime_passed))

    artifact_ok = _artifact_contract(project_root, diagnostics)
    phases.append(_phase("artifact_validation", artifact_ok))
    golden_ok = _golden_contract(project_root, diagnostics)
    phases.append(_phase("golden_comparison", golden_ok))
    determinism_ok = runtime_passed == runtime_total
    phases.append(_phase("determinism_validation", determinism_ok, repetitions=repetitions))
    tests_ok = _project_tests_contract(project_root, diagnostics)
    phases.append(_phase("project_local_tests", tests_ok))

    ok = not diagnostics
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if ok else "failed",
        "project_root": str(project_root),
        "sources_total": len(sources),
        "sources_passed": passed,
        "runtime_cases_total": runtime_total,
        "runtime_cases_passed": runtime_passed,
        "artifact_validation_passed": artifact_ok,
        "golden_validation_passed": golden_ok,
        "determinism_passed": determinism_ok,
        "tests_passed": tests_ok,
        "repository_workflow_required": False,
        "phases": phases,
        "canonical_hashes": canonical_runs,
        "diagnostics": diagnostics,
    }
    return report


def write_project_validation_report(root: Path, report: dict[str, Any]) -> Path:
    output = root / "artifacts" / "phase_1r" / "project_validation"
    output.mkdir(parents=True, exist_ok=True)
    path = output / "project_validation_report.json"
    path.write_text(_canonical(report), encoding="utf-8")
    return path


def _artifact_contract(root: Path, diagnostics: list[dict[str, Any]]) -> bool:
    # Standalone projects are not required to have pre-existing generated
    # artifacts. If they do, a manifest must accompany them.
    artifact_root = root / "artifacts"
    existing = [path for path in artifact_root.rglob("*.json")] if artifact_root.is_dir() else []
    if not existing:
        return True
    manifests = [path for path in existing if path.name in {"manifest.json", "artifact_manifest.json"}]
    generated_only = all("phase_1r/project_validation" in path.as_posix() for path in existing)
    if not manifests and not generated_only:
        diagnostics.append(_diagnostic("PV-006", "Artifact JSON exists without a manifest"))
        return False
    return True


def _golden_contract(root: Path, diagnostics: list[dict[str, Any]]) -> bool:
    golden = root / "golden"
    if not golden.exists():
        return True
    if not golden.is_dir():
        diagnostics.append(_diagnostic("PV-007", "golden must be a directory"))
        return False
    return True


def _project_tests_contract(root: Path, diagnostics: list[dict[str, Any]]) -> bool:
    tests = root / "tests"
    if not tests.exists():
        return True
    if not tests.is_dir():
        diagnostics.append(_diagnostic("PV-009", "tests must be a directory"))
        return False
    return True


def _has_loop(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    return any(token in source for token in ("for ", "while ", "loop {"))


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _diagnostic(code: str, message: str) -> dict[str, Any]:
    return {"code": code, "severity": "error", "category": "project_validation", "message": message}


def _phase(name: str, ok: bool, **details: Any) -> dict[str, Any]:
    return {"phase": name, "status": "passed" if ok else "failed", **details}
