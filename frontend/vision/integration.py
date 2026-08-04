"""Language, IR, and ExecutionPlan contracts for ``vision.*`` functions."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from frontend.language_surface.nodes import (
    CallExpressionNode,
    ExpressionNode,
    IdentifierNode,
    MemberAccessNode,
    StringLiteralNode,
    to_json_value,
)

from .contracts import PROFILE, VISION_TYPES, public_registry


class VisionSemanticError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code} {message}")


def vision_call_name(value: Any) -> str | None:
    value = value.expression if isinstance(value, ExpressionNode) else value
    if not isinstance(value, CallExpressionNode):
        return None
    callee = value.callee
    if isinstance(callee, MemberAccessNode) and isinstance(callee.object, IdentifierNode) and callee.object.name == "vision":
        return f"vision.{callee.member}"
    return None


def validate_vision_call(value: CallExpressionNode) -> None:
    name = vision_call_name(value)
    if name is None:
        return
    contracts = {entry["qualified_name"]: entry for entry in public_registry()}
    if name not in contracts:
        raise VisionSemanticError("VIS-LANG-001", f"unknown Vision standard function: {name}")
    if len(value.arguments) != 2:
        raise VisionSemanticError("VIS-LANG-002", f"{name} requires exactly two arguments")
    if name == "vision.infer":
        for argument in value.arguments:
            literal = _string_literal(argument)
            if literal is not None:
                _safe_relative(literal, code="VIS-LANG-003")
    if name == "vision.build_ruo":
        output = _string_literal(value.arguments[1])
        if output is not None:
            _safe_relative(output, code="VIS-LANG-004")
            if not output.endswith(".ruo"):
                raise VisionSemanticError("VIS-LANG-004", "vision.build_ruo output must use lowercase .ruo")


def vision_operations(value: Any) -> list[dict[str, Any]]:
    registry = {entry["qualified_name"]: entry for entry in public_registry()}
    result = []
    for index, call in enumerate(_walk_calls(value), 1):
        validate_vision_call(call)
        name = vision_call_name(call)
        assert name is not None
        contract = registry[name]
        result.append({
            "node_type": "VisionCallIR",
            "operation_id": f"vision_call_{index:03d}",
            "function": name,
            "native_operation": contract["native_operation"],
            "arguments": [{"position": position, "value": to_json_value(argument)} for position, argument in enumerate(call.arguments)],
            "input_type": contract["input_type"],
            "output_type": contract["output_type"],
            "capability_requirements": list(contract["capabilities"]),
            "failure_modes": ["capability", "path", "backend", "provenance", "artifact", "resource"],
            "determinism": contract["determinism"],
            "source_ref": {"line": None, "column": None},
        })
    return result


def vision_execution_plan(operations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "profile": PROFILE,
        "operations": [
            {
                "order": index,
                "operation_id": operation["operation_id"],
                "operation": operation["native_operation"],
                "capability_requirements": operation["capability_requirements"],
                "transaction_boundary": operation["native_operation"] == "vision_build_ruo",
            }
            for index, operation in enumerate(operations, 1)
        ],
        "resource_limits_required": True,
        "publication_policy": "atomic_ruo_f1" if any(op["native_operation"] == "vision_build_ruo" for op in operations) else "none",
    }


def _walk_calls(value: Any):
    if isinstance(value, CallExpressionNode) and vision_call_name(value) is not None:
        yield value
    if isinstance(value, (tuple, list)):
        for item in value:
            yield from _walk_calls(item)
    elif hasattr(value, "__dataclass_fields__"):
        for field in value.__dataclass_fields__:
            yield from _walk_calls(getattr(value, field))


def _string_literal(value: Any) -> str | None:
    value = value.expression if isinstance(value, ExpressionNode) else value
    return value.value if isinstance(value, StringLiteralNode) else None


def _safe_relative(value: str, *, code: str) -> None:
    path = PurePosixPath(value)
    if not value or "\\" in value or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise VisionSemanticError(code, "Vision paths must be safe project-relative paths")
