"""Phase F0 — Reason Entity Foundation baseline freeze (RS-RE-FSM-001 §13).

This module observes existing compiler/runtime behavior only. It does not
change language, compiler, or runtime semantics. It exists so that later
Phases (F1 onward) can verify, by byte comparison, that a change was the
one intended change and not an incidental regression.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from frontend import ast as semantic_ast
from frontend.language_surface.nodes import to_json_value as surface_to_json_value
from frontend.language_surface.parser import SurfaceSyntaxError, parse
from frontend.integrated_computation_runtime import execute_program
from toolchain.diagnostics import DIAGNOSTIC_CODE_PATTERN, CODE_CATEGORY_PREFIXES
from toolchain.pipeline import PipelineError, compile_source

PROFILE = "reasonscript-reason-entity-baseline/1.0"

CANONICAL_ARTIFACTS = (
    "environment_manifest.json",
    "surface_ast_baseline.json",
    "semantic_ast_baseline.json",
    "reason_ir_baseline.json",
    "execution_plan_baseline.json",
    "diagnostic_code_inventory.json",
    "tensor_numeric_baseline.json",
    "ruo_compatibility_baseline.json",
    "performance_baseline.json",
    "validation_summary.json",
)
REQUIRED_ARTIFACTS = (*CANONICAL_ARTIFACTS, "run_manifest.json")

# performance_baseline.json contains wall-clock timings and is intentionally
# excluded from the byte-identical determinism check (RS-RE-FSM-001 §7 treats
# performance as a separately measured, non-canonical indicator).
DETERMINISTIC_ARTIFACTS = tuple(
    name for name in CANONICAL_ARTIFACTS if name != "performance_baseline.json"
)

# Fixtures are drawn from the repository's own example corpus rather than a
# newly authored one, so the baseline reflects real observed behavior.
VALID_FIXTURES = (
    "examples/function_basic.rsn",
    "examples/function_call_from_calculation.rsn",
    "examples/scalar_arithmetic.rsn",
    "examples/scalar_literals.rsn",
    "examples/session_fix.rsn",
    "examples/v0_5/001_minimal_module.rsn",
    "examples/v0_5/002_single_calculation.rsn",
    "examples/v0_5/003_calculation_dependency.rsn",
    "examples/v0_5/004_function_call.rsn",
    "examples/v0_5/005_branching_function.rsn",
    "examples/v0_5/006_runtime_input_print.rsn",
    "examples/v0_5/007_runtime_operation.rsn",
    "examples/v0_5/008_struct_pattern.rsn",
    "examples/v0_5/009_optional_match.rsn",
)
INVALID_FIXTURES = (
    # (path, expected diagnostic code substring)
    ("examples/proof_failure.rsn", "CAL-030"),
)

# Self-contained (no filesystem I/O) Tensor programs used to freeze numeric
# behavior. tensor_training_foundation.rsn requires external data files and
# is intentionally excluded from the runtime-execution baseline.
TENSOR_NUMERIC_FIXTURES = {
    "matmul_relu_mean": """
module TensorNumericBaseline {
  calculation Compute {
    let a = tensor.random_normal([4, 4], 0.0, 1.0, 7, 0, "f32")
    let b = tensor.random_normal([4, 4], 0.0, 1.0, 7, 1, "f32")
    let c = tensor.matmul(a, b)
    let d = tensor.relu(c)
    let loss = tensor.mean(d)
    result = loss
  }
}
""",
    "conv2d_train_step": """
module TensorNumericBaseline {
  calculation Compute {
    let input = tensor.random_normal([1, 1, 6, 6], 0.0, 1.0, 11, 0, "f32")
    let weight = tensor.parameter(tensor.random_normal([2, 1, 3, 3], 0.0, 0.02, 11, 1, "f32"))
    let features = tensor.conv2d(input, weight, null, [1, 1], [0, 0], [1, 1], 1)
    let activated = tensor.relu(features)
    let target = tensor.zeros(tensor.shape(activated), "f32")
    let error = tensor.subtract(activated, target)
    let loss = tensor.mean(tensor.power(error, 2.0))
    let gradients = tensor.grad(loss, [weight])
    let updated = tensor.subtract(weight, tensor.multiply(gradients[0], 0.01))
    result = tensor.mean(updated)
  }
}
""",
}


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_of(value: Any) -> str:
    return sha256_bytes(stable_json(value).encode("utf-8"))


def artifact(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"reasonscript-reason-entity-baseline-{kind}/1.0",
        "profile_version": PROFILE,
        "data": data,
    }


def file_evidence(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        return {"path": relative, "available": False}
    payload = path.read_bytes()
    return {"path": relative, "available": True, "sha256": sha256_bytes(payload), "bytes": len(payload)}


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def _environment(root: Path) -> dict[str, Any]:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    return artifact("environment-manifest", {
        "reason_version": version,
        "repository_revision": _git(root, "rev-parse", "HEAD"),
        "repository_branch": _git(root, "branch", "--show-current") or "detached",
        "environment_metadata": {
            "python": platform.python_version(),
            "operating_system": platform.system().lower(),
        },
        "profiles": [PROFILE],
        "canonical_commands": [
            "reason reason-entity-baseline generate",
            "reason reason-entity-baseline validate",
            "reason ci",
        ],
        "fixture_corpus": {
            "valid": list(VALID_FIXTURES),
            "invalid": [path for path, _ in INVALID_FIXTURES],
            "tensor_numeric": sorted(TENSOR_NUMERIC_FIXTURES),
        },
    })


def _compile_fixture(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    source = path.read_text(encoding="utf-8")
    result = compile_source(source, path)
    return {
        "path": relative,
        "sha256": sha256_bytes(source.encode("utf-8")),
        "surface_ast_digest": sha256_of(surface_to_json_value(result.surface_ast)),
        "semantic_ast_digest": sha256_of(
            [semantic_ast.to_json_value(module) for module in _semantic_modules(result.surface_ast)]
        ),
        "reason_ir_digest": sha256_of(list(result.reason_irs)),
        "execution_plan_digest": sha256_of(
            [_execution_plan_for(ir) for ir in result.reason_irs]
        ),
    }


def _semantic_modules(program: Any) -> list[Any]:
    from frontend.language_surface.integration import project_program

    return list(project_program(program))


def _execution_plan_for(reason_ir: dict[str, Any]) -> dict[str, Any]:
    from frontend.language_surface.integration import execution_plan_for

    return execution_plan_for(reason_ir)


def _semantic_ast_baseline(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return artifact("semantic-ast-baseline", {
        "fixtures": [
            {"path": entry["path"], "semantic_ast_digest": entry["semantic_ast_digest"]}
            for entry in entries
        ],
    })


def _reason_ir_baseline(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return artifact("reason-ir-baseline", {
        "fixtures": [
            {"path": entry["path"], "reason_ir_digest": entry["reason_ir_digest"]}
            for entry in entries
        ],
    })


def _execution_plan_baseline(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return artifact("execution-plan-baseline", {
        "fixtures": [
            {"path": entry["path"], "execution_plan_digest": entry["execution_plan_digest"]}
            for entry in entries
        ],
    })


def _diagnostic_from_error(error: Exception) -> str:
    message = str(error)
    return message.split()[0] if message.split() else ""


def _invalid_fixture_result(root: Path, relative: str, expected_code: str) -> dict[str, Any]:
    path = root / relative
    source = path.read_text(encoding="utf-8")
    try:
        compile_source(source, path)
    except (SurfaceSyntaxError, PipelineError) as error:
        code = _diagnostic_from_error(error)
        return {
            "path": relative,
            "raised": type(error).__name__,
            "code": code,
            "matches_expected": expected_code in code,
        }
    return {"path": relative, "raised": None, "code": None, "matches_expected": False}


def _diagnostic_code_inventory(root: Path) -> dict[str, Any]:
    known_prefixes = sorted(CODE_CATEGORY_PREFIXES)
    invalid_results = [
        _invalid_fixture_result(root, path, code) for path, code in INVALID_FIXTURES
    ]
    return artifact("diagnostic-code-inventory", {
        "known_prefixes": known_prefixes,
        "code_pattern": DIAGNOSTIC_CODE_PATTERN.pattern,
        "invalid_fixtures": invalid_results,
    })


def _tensor_numeric_baseline() -> dict[str, Any]:
    fixtures = []
    for name, source in sorted(TENSOR_NUMERIC_FIXTURES.items()):
        program = parse(source)
        result = execute_program(program)
        fixtures.append({
            "name": name,
            "source_sha256": sha256_bytes(source.encode("utf-8")),
            "runtime_result_digest": sha256_of(result.to_dict()),
            "result_value": result.to_dict()["result"],
        })
    return artifact("tensor-numeric-baseline", {"fixtures": fixtures})


def _ruo_compatibility_baseline(root: Path) -> dict[str, Any]:
    paths = (
        "schemas/reasonunit_object",
        "schemas/reasonunit_file",
        "schemas/reasonunit_language",
        "schemas/reasonunit_native_runtime",
        "schemas/reasonunit_baseline",
        "schemas/reasonunit_compatibility",
        "schemas/reasonunit_tensor",
        "toolchain/reasonunit_object/universal.py",
        "toolchain/reasonunit_object/model.py",
    )
    return artifact("ruo-compatibility-baseline", {
        "referenced_paths": [file_evidence(root, path) for path in paths if (root / path).exists()],
        "note": "Existing RUO-C0/C1/U1/F1/T1/N1/N2 artifacts are unmodified by this Phase.",
    })


def _performance_baseline(root: Path, entries: list[dict[str, Any]]) -> dict[str, Any]:
    import time

    timings = []
    for relative in VALID_FIXTURES:
        path = root / relative
        source = path.read_text(encoding="utf-8")
        started = time.perf_counter()
        compile_source(source, path)
        elapsed = time.perf_counter() - started
        timings.append({"path": relative, "compile_seconds": round(elapsed, 6)})
    return artifact("performance-baseline", {
        "compile_timings": timings,
        "fixture_count": len(entries),
        "note": "Wall-clock measurements; informational only, not a determinism target.",
    })


def _report(validation: dict[str, Any]) -> str:
    data = validation["data"]
    return "\n".join([
        "# ReasonScript Reason Entity Foundation — Phase F0 Baseline Report", "",
        "## Completion Summary", "",
        "The v0.5.4.6 observable behavior of the compiler pipeline and integrated "
        "runtime is frozen as a deterministic baseline for RS-RE-FSM-001.", "",
        "## Implemented Features", "",
        "- Surface AST / Semantic AST / Reason IR / ExecutionPlan digests for the "
        "example fixture corpus.",
        "- Diagnostic code inventory and one invalid-fixture regression probe.",
        "- Self-contained Tensor numeric baseline (no filesystem dependency).",
        "- Wall-clock performance baseline for later Phase comparison.", "",
        "## Validation Results", "",
        f"- Fixtures compiled: {data['fixture_count']}.",
        f"- Determinism: {data['determinism_status']}.", "",
        "## Generated Artifacts", "",
        "All canonical JSON documents are recorded by `run_manifest.json` with "
        "SHA-256 digests and byte sizes.", "",
        "## Compatibility Notes", "",
        "No lexer, parser, compiler, runtime, or diagnostic behavior is modified "
        "by this Phase.", "",
        "## Remaining Work", "",
        "Proceed to Phase F1 (Type Foundation Repair) only after this baseline "
        "is verified byte-identical across three independent generations.", "",
    ])


def generate_baseline(root: Path, output: Path) -> dict[str, Any]:
    root, output = root.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    fixture_entries = [_compile_fixture(root, relative) for relative in VALID_FIXTURES]
    documents: dict[str, dict[str, Any]] = {
        "environment_manifest.json": _environment(root),
        "surface_ast_baseline.json": artifact("surface-ast-baseline", {"fixtures": fixture_entries}),
        "semantic_ast_baseline.json": _semantic_ast_baseline(fixture_entries),
        "reason_ir_baseline.json": _reason_ir_baseline(fixture_entries),
        "execution_plan_baseline.json": _execution_plan_baseline(fixture_entries),
        "diagnostic_code_inventory.json": _diagnostic_code_inventory(root),
        "tensor_numeric_baseline.json": _tensor_numeric_baseline(),
        "ruo_compatibility_baseline.json": _ruo_compatibility_baseline(root),
        "performance_baseline.json": _performance_baseline(root, fixture_entries),
    }
    validation = artifact("validation-summary", {
        "fixture_count": len(fixture_entries),
        "invalid_fixture_count": len(INVALID_FIXTURES),
        "determinism_status": "PENDING_VERIFICATION",
        "phase_status": "GENERATED",
    })
    documents["validation_summary.json"] = validation
    report = _report(validation)
    for name, document in sorted(documents.items()):
        (output / name).write_text(stable_json(document), encoding="utf-8", newline="\n")
    (output / "final_report.md").write_text(report, encoding="utf-8", newline="\n")
    manifest_entries = []
    for name in sorted((*documents.keys(), "final_report.md")):
        payload = (output / name).read_bytes()
        manifest_entries.append({"path": name, "sha256": sha256_bytes(payload), "bytes": len(payload)})
    run_body = {
        "artifact_count": len(documents) + 1,
        "artifacts": manifest_entries,
        "canonicalization": {
            "encoding": "UTF-8",
            "json_keys": "sorted",
            "line_endings": "LF",
            "non_finite_numbers": "rejected",
        },
    }
    run_manifest = artifact("run-manifest", run_body)
    (output / "run_manifest.json").write_text(stable_json(run_manifest), encoding="utf-8", newline="\n")
    return {"output": str(output), "artifact_count": len(documents) + 2}


def _directories_equal(runs: list[Path]) -> bool:
    reference = {name: (runs[0] / name).read_bytes() for name in DETERMINISTIC_ARTIFACTS}
    return all(
        all((run / name).read_bytes() == payload for name, payload in reference.items())
        for run in runs[1:]
    )


def validate_baseline(root: Path, directory: Path, *, verify_determinism: bool = True) -> dict[str, Any]:
    root, directory = root.resolve(), directory.resolve()
    issues: list[dict[str, Any]] = []
    missing = [name for name in REQUIRED_ARTIFACTS if not (directory / name).is_file()]
    if missing:
        issues.append({"code": "RE-F0-001", "message": "Missing canonical artifacts", "artifacts": missing})
        return {"ok": False, "issues": issues}
    for name in CANONICAL_ARTIFACTS:
        try:
            json.loads((directory / name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            issues.append({"code": "RE-F0-001", "artifact": name, "message": str(error)})
    deterministic = True
    if verify_determinism:
        with tempfile.TemporaryDirectory(prefix="reason-entity-f0-") as tmp:
            runs = [Path(tmp) / f"run-{index}" for index in range(1, 4)]
            for run in runs:
                generate_baseline(root, run)
            deterministic = _directories_equal(runs)
        if not deterministic:
            issues.append({"code": "RE-F0-002", "message": "three isolated generations differ"})
    return {
        "ok": not issues,
        "issues": issues,
        "determinism": "BYTE_IDENTICAL_THREE_RUNS" if deterministic else "MISMATCH",
    }
