"""Shared Rust-host dispatch for standalone and project execution."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# `runtime_metrics` entries that measure the machine rather than the program
# (P0 spec section 29: time and memory values are excluded from determinism
# comparisons). The native host always reports them; `reason run` includes
# them only with `--profile-runtime`, so default JSON output stays
# byte-identical across runs and install locations (ACC-10, install parity).
# Everything else in `runtime_metrics` is a deterministic count.
MEASUREMENT_METRIC_KEYS = frozenset({
    "runtime_execution_ns",
    "predicate_execution_ns",
    "relation_execution_ns",
    "reasoning_event_ns",
    "trace_execution_ns",
    "allocation_count",
    "allocated_bytes",
    "peak_live_bytes",
})


def deterministic_runtime_result(result: dict[str, Any]) -> dict[str, Any]:
    """`result` without the measurement-only metrics, for hashing/comparison."""
    metrics = result.get("runtime_metrics")
    if not isinstance(metrics, dict):
        return result
    stripped = dict(result)
    stripped["runtime_metrics"] = {key: value for key, value in metrics.items() if key not in MEASUREMENT_METRIC_KEYS}
    return stripped


@dataclass(frozen=True)
class RustDispatchError(RuntimeError):
    """A product-visible failure to execute through the native Rust host."""

    reason: str
    code: str
    message: str
    diagnostic: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message

    def to_diagnostic(self) -> dict[str, Any]:
        result = dict(self.diagnostic or {})
        result.setdefault("code", self.code)
        result.setdefault("severity", "error")
        result.setdefault("category", "runtime.native")
        result.setdefault("message", self.message)
        result["stage"] = "runtime"
        return result


def execute_rust_program(
    program: Any,
    resource_root: Path,
    filesystem_read: bool,
    filesystem_write: bool,
    *,
    backend: str = "RuntimeReal",
    include_trace: bool = False,
    max_call_depth: int | None = None,
    trace_config: dict[str, Any] | None = None,
    max_loop_iterations: int | None = None,
    budget: dict[str, int] | None = None,
    reasoning_event_mode: str | None = None,
    profile_runtime: bool = False,
    fast_path: bool = True,
) -> dict[str, Any]:
    from frontend.computation_ir import LoweringError, lower_program
    from frontend.computation_ir.optimizer import optimize_program

    try:
        ir_document = optimize_program(lower_program(program))
    except LoweringError as error:
        raise RustDispatchError(
            "computation_ir_lowering_unsupported",
            "RTH-LOWER-001",
            f"program cannot be lowered to the native computation IR: {error}",
        ) from error
    return execute_rust_ir(
        ir_document,
        resource_root,
        filesystem_read,
        filesystem_write,
        backend=backend,
        include_trace=include_trace,
        max_call_depth=max_call_depth,
        trace_config=trace_config,
        max_loop_iterations=max_loop_iterations,
        budget=budget,
        reasoning_event_mode=reasoning_event_mode,
        profile_runtime=profile_runtime,
        fast_path=fast_path,
    )


def execute_rust_ir(
    ir_document: dict[str, Any],
    resource_root: Path,
    filesystem_read: bool,
    filesystem_write: bool,
    *,
    backend: str = "RuntimeReal",
    include_trace: bool = False,
    max_call_depth: int | None = None,
    trace_config: dict[str, Any] | None = None,
    max_loop_iterations: int | None = None,
    budget: dict[str, int] | None = None,
    reasoning_event_mode: str | None = None,
    profile_runtime: bool = False,
    fast_path: bool = True,
) -> dict[str, Any]:
    from frontend.computation_ir.rust_bridge import find_binary, run_ir

    binary = find_binary()
    if binary is None:
        raise RustDispatchError(
            "rust_binary_missing",
            "RTH-HOST-001",
            "native ReasonScript runtime host is not installed or built",
        )
    unsupported = unsupported_rust_operations(ir_document)
    if unsupported:
        raise RustDispatchError(
            "rust_operation_unsupported",
            "RTH-UNSUPPORTED-001",
            "native runtime does not support: " + ", ".join(unsupported),
        )
    # Trace is observational.  An operation without a trace adapter must not
    # turn an otherwise executable calculation into a runtime failure.
    trace_unsupported = rust_trace_unsupported_operations(ir_document) if include_trace else ()
    trace_enabled = include_trace and not trace_unsupported
    # Phase 4 ("制御された再帰"): `None` leaves `max_call_depth` out of the
    # request entirely, so the Rust host falls back to its own
    # DEFAULT_MAX_CALL_DEPTH -- the default value itself isn't duplicated
    # here, only whether the caller (ultimately, `reason.toml`'s
    # `[runtime] max_call_depth` / `max_loop_iterations`) overrides it.
    limits = {
        key: value
        for key, value in (("max_call_depth", max_call_depth), ("max_loop_iterations", max_loop_iterations))
        if value is not None
    }
    limits.update({key: value for key, value in (budget or {}).items() if value is not None})
    if "max_wall_time_ms" not in limits:
        # P0-2 Execution Budget: wall time is the primary stop condition.
        # Default it to the bridge timeout so the host ends with a clean
        # RT-BUDGET-001 (plus runtime metrics) rather than being killed.
        default_wall_ms = int(float(os.environ.get("REASONSCRIPT_RUNTIME_TIMEOUT", "30")) * 1000)
        if default_wall_ms > 0:
            limits["max_wall_time_ms"] = default_wall_ms
    try:
        outcome = run_ir(
            ir_document,
            binary=binary,
            cwd=resource_root,
            filesystem_read=filesystem_read,
            filesystem_write=filesystem_write,
            backend=backend,
            trace_enabled=trace_enabled,
            **({"trace_config": trace_config} if trace_config is not None and not trace_unsupported else {}),
            limits=limits,
            reasoning_event_mode=reasoning_event_mode,
            profile_runtime=profile_runtime,
            fast_path=fast_path,
        )
    except subprocess.TimeoutExpired as error:
        raise RustDispatchError(
            "rust_bridge_timeout",
            "RTH-TIMEOUT-001",
            f"native runtime host timed out after {error.timeout:g} seconds; "
            "raise REASONSCRIPT_RUNTIME_TIMEOUT to allow longer runs",
        ) from error
    except (OSError, ValueError) as error:
        raise RustDispatchError(
            "rust_bridge_error",
            "RTH-BRIDGE-001",
            f"native runtime host invocation failed: {error}",
        ) from error
    if not outcome.ok:
        diagnostic = dict(outcome.diagnostic or {})
        failure_metadata = outcome.metadata or {}
        for key in ("termination_reason", "runtime_metrics"):
            if failure_metadata.get(key) is not None:
                diagnostic[key] = failure_metadata[key]
        if not profile_runtime:
            diagnostic = deterministic_runtime_result(diagnostic)
        raise RustDispatchError(
            "native_runtime_error",
            outcome.error_code or "RTH-RUNTIME-001",
            outcome.error_message or "native runtime execution failed",
            diagnostic=diagnostic,
        )
    calculations = outcome.calculation_results or {}
    result_value = next(reversed(calculations.values()), None) if calculations else None
    result = {
        "schema_version": "reasonscript-integrated-runtime/0.1",
        "status": "success",
        "result": result_value,
        "calculations": calculations,
        "console_output": getattr(outcome, "console_output", []),
        "tensor_metadata": outcome.metadata.get("tensor_metadata", []),
        "tensor_trace": outcome.metadata.get("tensor_trace", []),
        "loop_trace": outcome.metadata.get("loop_trace", []),
        "vision_trace": outcome.metadata.get("vision_trace", []),
        "reasoning_trace": outcome.metadata.get("reasoning_trace", []),
        "runtime_metrics": outcome.metadata.get("runtime_metrics", {}),
        "termination_reason": outcome.metadata.get("termination_reason", "completed"),
        "trace_diagnostics": outcome.metadata.get("trace_diagnostics", []) + ([{
            "code": "RTH-TRACE-001",
            "severity": "warning",
            "category": "runtime.trace",
            "message": "native runtime trace was omitted for unsupported operations: " + ", ".join(trace_unsupported),
            "operations": list(trace_unsupported),
        }] if trace_unsupported else []),
    }
    return result if profile_runtime else deterministic_runtime_result(result)


def unsupported_rust_operations(ir_document: dict[str, Any]) -> tuple[str, ...]:
    """Preflight namespace calls so unsupported features never masquerade as
    native runtime failures and never need execute-then-fallback probing.
    """
    from toolchain.runtime_manifest import RUST_RUO_FUNCTIONS, RUST_TENSOR_FUNCTIONS

    unsupported: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            op = node.get("op")
            function_id = node.get("function_id")
            if op == "call_tensor" and isinstance(function_id, str):
                if function_id.removeprefix("tensor.") not in RUST_TENSOR_FUNCTIONS:
                    unsupported.add(function_id)
            elif op == "call_ruo" and isinstance(function_id, str):
                if function_id not in RUST_RUO_FUNCTIONS:
                    unsupported.add(function_id)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(ir_document)
    return tuple(sorted(unsupported))


def rust_trace_unsupported_operations(ir_document: dict[str, Any]) -> tuple[str, ...]:
    unsupported: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("op") == "call_optimizer":
                unsupported.add(str(node.get("function_id", node.get("op"))))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(ir_document)
    return tuple(sorted(unsupported))
