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
    )


def try_rust_ir(
    ir_document: dict[str, Any],
    resource_root: Path,
    filesystem_read: bool,
    filesystem_write: bool,
    *,
    backend: str = "RuntimeReal",
) -> tuple[dict[str, Any] | None, str | None]:
    from frontend.computation_ir.rust_bridge import find_binary, run_ir

    binary = find_binary()
    if binary is None:
        return None, "rust_binary_missing"
    if ir_document.get("reason_object_bindings") and not filesystem_read:
        return None, "ruo_read_capability_not_granted"
    if uses_tensor_io(ir_document) and not (filesystem_read and filesystem_write):
        return None, "tensor_io_capability_not_granted"
    try:
        outcome = run_ir(
            ir_document,
            binary=binary,
            cwd=resource_root,
            filesystem_read=filesystem_read,
            filesystem_write=filesystem_write,
            backend=backend,
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
        "tensor_metadata": [],
        "tensor_trace": [],
        "loop_trace": [],
        "vision_trace": [],
        "calculations": calculations,
    }, None


def uses_tensor_io(ir_document: dict[str, Any]) -> bool:
    def walk(node: Any) -> bool:
        if isinstance(node, dict):
            if node.get("op") == "call_tensor" and node.get("function_id") in {
                "tensor.load",
                "tensor.save",
            }:
                return True
            return any(walk(value) for value in node.values())
        if isinstance(node, list):
            return any(walk(item) for item in node)
        return False

    return walk(ir_document)
