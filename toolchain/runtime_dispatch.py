"""Shared Rust-host dispatch for standalone and project execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
    # `[runtime] max_call_depth`) overrides it.
    limits = {"max_call_depth": max_call_depth} if max_call_depth is not None else {}
    try:
        outcome = run_ir(
            ir_document,
            binary=binary,
            cwd=resource_root,
            filesystem_read=filesystem_read,
            filesystem_write=filesystem_write,
            backend=backend,
            trace_enabled=trace_enabled,
            limits=limits,
        )
    except (OSError, ValueError) as error:
        raise RustDispatchError(
            "rust_bridge_error",
            "RTH-BRIDGE-001",
            f"native runtime host invocation failed: {error}",
        ) from error
    if not outcome.ok:
        raise RustDispatchError(
            "native_runtime_error",
            outcome.error_code or "RTH-RUNTIME-001",
            outcome.error_message or "native runtime execution failed",
            diagnostic=outcome.diagnostic,
        )
    calculations = outcome.calculation_results or {}
    result_value = next(reversed(calculations.values()), None) if calculations else None
    return {
        "schema_version": "reasonscript-integrated-runtime/0.1",
        "status": "success",
        "result": result_value,
        "tensor_metadata": outcome.metadata.get("tensor_metadata", []),
        "tensor_trace": outcome.metadata.get("tensor_trace", []),
        "loop_trace": outcome.metadata.get("loop_trace", []),
        "vision_trace": outcome.metadata.get("vision_trace", []),
        "reasoning_trace": outcome.metadata.get("reasoning_trace", []),
        "trace_diagnostics": ([{
            "code": "RTH-TRACE-001",
            "severity": "warning",
            "category": "runtime.trace",
            "message": "native runtime trace was omitted for unsupported operations: " + ", ".join(trace_unsupported),
            "operations": list(trace_unsupported),
        }] if trace_unsupported else []),
        "calculations": calculations,
    }


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
