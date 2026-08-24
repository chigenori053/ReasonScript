"""Shared Rust-host dispatch for standalone and project execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def try_rust_program(
    program: Any,
    resource_root: Path,
    filesystem_read: bool,
    filesystem_write: bool,
    *,
    backend: str = "RuntimeReal",
    include_trace: bool = False,
) -> tuple[dict[str, Any] | None, str | None]:
    from frontend.computation_ir import LoweringError, lower_program

    try:
        ir_document = lower_program(program)
    except LoweringError:
        return None, "computation_ir_lowering_unsupported"
    return try_rust_ir(
        ir_document,
        resource_root,
        filesystem_read,
        filesystem_write,
        backend=backend,
        include_trace=include_trace,
    )


def try_rust_ir(
    ir_document: dict[str, Any],
    resource_root: Path,
    filesystem_read: bool,
    filesystem_write: bool,
    *,
    backend: str = "RuntimeReal",
    include_trace: bool = False,
) -> tuple[dict[str, Any] | None, str | None]:
    from frontend.computation_ir.rust_bridge import find_binary, run_ir

    binary = find_binary()
    if binary is None:
        return None, "rust_binary_missing"
    if unsupported_rust_operations(ir_document):
        return None, "rust_operation_unsupported"
    if include_trace and rust_trace_unsupported_operations(ir_document):
        return None, "rust_trace_operation_unsupported"
    if ir_document.get("reason_object_bindings") and not filesystem_read:
        return None, "ruo_read_capability_not_granted"
    tensor_io = tensor_io_operations(ir_document)
    if ("tensor.load" in tensor_io and not filesystem_read) or (
        "tensor.save" in tensor_io and not filesystem_write
    ):
        return None, "tensor_io_capability_not_granted"
    try:
        outcome = run_ir(
            ir_document,
            binary=binary,
            cwd=resource_root,
            filesystem_read=filesystem_read,
            filesystem_write=filesystem_write,
            backend=backend,
            trace_enabled=include_trace,
        )
    except (OSError, ValueError):
        return None, "rust_bridge_error"
    if not outcome.ok:
        return None, "native_runtime_error"
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
        "calculations": calculations,
    }, None


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


def tensor_io_operations(ir_document: dict[str, Any]) -> frozenset[str]:
    operations: set[str] = set()

    def walk(node: Any) -> bool:
        if isinstance(node, dict):
            if node.get("op") == "call_tensor" and node.get("function_id") in {
                "tensor.load",
                "tensor.save",
            }:
                operations.add(node["function_id"])
            for value in node.values():
                walk(value)
        if isinstance(node, list):
            for item in node:
                walk(item)

    walk(ir_document)
    return frozenset(operations)


def uses_tensor_io(ir_document: dict[str, Any]) -> bool:
    return bool(tensor_io_operations(ir_document))


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
