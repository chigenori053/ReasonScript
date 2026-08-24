"""Frozen runtime-consolidation capability manifest.

Phase 0 of the Rust runtime consolidation freezes the currently observable
execution topology before any dispatch or packaging changes are made.  This
manifest is intentionally separate from the Tensor function contract: it
records *where* an operation executes, whether Rust is complete, and which
production fallback keeps the operation working today.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from frontend.tensor import tensor_function_contracts
from frontend.vision.contracts import public_registry as vision_public_registry


MANIFEST_SCHEMA = "reasonscript-runtime-consolidation-manifest/1.0"
DEFAULT_BASELINE_PATH = Path("docs/reports/runtime_consolidation_manifest.json")

RUST_TENSOR_FUNCTIONS = frozenset(
    """
    create zeros ones full shape rank size dtype dimension reshape flatten
    transpose squeeze unsqueeze add subtract multiply divide power maximum
    minimum equal not_equal greater greater_equal less less_equal negate abs
    exp log sqrt sum mean min max argmax argmin dot matmul norm cast to_array
    scalar random_uniform random_normal random_bernoulli random_permutation
    load save parameter detach requires_grad grad slice narrow gather concat
    stack relu softmax linear conv2d max_pool2d avg_pool2d
    """.split()
)

RUO_FUNCTIONS = tuple(
    f"ruo.{name}"
    for name in (
        "object_id", "snapshot", "resolve", "query", "begin", "apply",
        "validate", "commit", "rollback", "select", "materialize",
        "project", "save", "tensor_view", "status", "diagnostics",
    )
)
RUST_RUO_FUNCTIONS = frozenset(
    {"ruo.object_id", "ruo.snapshot", "ruo.resolve", "ruo.status", "ruo.diagnostics"}
)

RELATION_FUNCTIONS = tuple(
    f"relation.{name}"
    for name in (
        "filter_eq", "filter_ne", "filter_gt", "filter_gte", "filter_lt",
        "filter_lte", "count", "distinct_by", "sort_by",
    )
)
OPTIMIZER_FUNCTIONS = tuple(
    f"optimizer.{name}"
    for name in (
        "sgd", "momentum_velocity", "momentum", "adam_moment1",
        "adam_moment2", "adam", "adamw",
    )
)
REASONING_FUNCTIONS = (
    "runtime.search", "runtime.simulate", "runtime.predict", "runtime.plan"
)


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _operation(name: str, *, python: bool, rust: bool, fallback: str | None) -> dict[str, Any]:
    return {
        "name": name,
        "python": "implemented" if python else "absent",
        "rust": "implemented" if rust else "unsupported",
        "production_fallback": fallback,
    }


def build_manifest() -> dict[str, Any]:
    tensor_names = sorted(tensor_function_contracts())
    optimizer_names = sorted(OPTIMIZER_FUNCTIONS)
    vision_names = sorted(entry["qualified_name"] for entry in vision_public_registry())

    namespaces = {
        "tensor": [
            _operation(
                name,
                python=True,
                rust=name.removeprefix("tensor.") in RUST_TENSOR_FUNCTIONS,
                fallback=None if name.removeprefix("tensor.") in RUST_TENSOR_FUNCTIONS else "python_ast_runtime",
            )
            for name in tensor_names
        ],
        "optimizer": [
            _operation(name, python=True, rust=True, fallback=None)
            for name in optimizer_names
        ],
        "relation": [
            _operation(name, python=True, rust=True, fallback=None)
            for name in RELATION_FUNCTIONS
        ],
        "ruo": [
            _operation(
                name,
                python=True,
                rust=name in RUST_RUO_FUNCTIONS,
                fallback=None if name in RUST_RUO_FUNCTIONS else "python_ast_runtime",
            )
            for name in RUO_FUNCTIONS
        ],
        "vision": [
            _operation(name, python=True, rust=False, fallback="python_bridge_to_rust_process")
            for name in vision_names
        ],
        "reasoning": [
            _operation(name, python=True, rust=False, fallback="python_runtime_integration")
            for name in REASONING_FUNCTIONS
        ],
    }

    return {
        "schema": MANIFEST_SCHEMA,
        "version": "1.0",
        "phase": 0,
        "execution_paths": {
            "standalone_source": {
                "primary": "rust_computation_vm",
                "fallback": "python_ast_runtime",
                "trace_engine": "rust_computation_vm_with_domain_fallback",
            },
            "project": {
                "primary": "rust_computation_vm",
                "fallback": "python_ast_runtime",
                "manifest_backend_selects_engine": False,
            },
            "installed_distribution": {
                "computation_vm_binary_packaged": True,
                "effective_primary": "rust_computation_vm",
            },
        },
        "fallback_reasons": [
            "rust_binary_missing",
            "computation_ir_lowering_unsupported",
            "native_runtime_error",
            "rust_operation_unsupported",
            "rust_trace_operation_unsupported",
            "rust_bridge_error",
            "built_computation_ir_missing",
            "built_computation_ir_invalid",
            "ruo_read_capability_not_granted",
            "tensor_io_capability_not_granted",
        ],
        "namespaces": namespaces,
        "rust_workspaces": [
            "ReasonComputationRuntime", "NativeReasonUnitRuntime", "VisionRuntime",
            "VisualizationRuntime", "ClusterRuntime", "RuntimeReal",
            "HybridRuntime", "RuntimeComplex",
        ],
        "retirement_candidates": {
            "python_production": [
                "frontend/integrated_computation_runtime.py",
                "frontend/computation_ir/interpreter.py",
                "frontend/tensor/runtime.py",
                "frontend/tensor/optimizers.py",
                "frontend/reason_object_runtime.py",
                "frontend/vision/runtime.py",
                "frontend/runtime_integration.py",
                "toolchain/reasoning_runtime.py",
            ],
            "bridges": ["frontend/computation_ir/rust_bridge.py"],
            "rust_layouts_after_migration": [
                "ReasonComputationRuntime", "NativeReasonUnitRuntime", "VisionRuntime",
                "RuntimeReal", "HybridRuntime", "RuntimeComplex", "Legacy/runtime",
            ],
        },
        "deletion_gates": [
            "rust_replacement_exists",
            "differential_parity_passes",
            "diagnostic_source_trace_parity_passes",
            "production_import_count_is_zero",
            "standalone_project_installed_smoke_passes",
            "reason_ci_passes_without_python_fallback",
            "documentation_and_package_manifest_updated",
        ],
    }


def write_manifest(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(build_manifest()), encoding="utf-8")
    return path


def diff_manifest(baseline_path: Path) -> list[str]:
    if not baseline_path.is_file():
        return [f"baseline manifest not found: {baseline_path}"]
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"baseline manifest unreadable: {baseline_path} ({error})"]
    current = build_manifest()
    if baseline == current:
        return []
    diffs: list[str] = []
    for key in sorted(set(baseline) | set(current)):
        if baseline.get(key) != current.get(key):
            diffs.append(f"runtime contract section changed: {key}")
    return diffs
