"""Language-to-runtime integration for Tensor standard functions.

This module is deliberately backend neutral.  It owns the stable public
registry, semantic call validation, Reason IR tensor nodes, and physical
ExecutionPlan projection.  Numeric execution remains in :mod:`.runtime`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import fields, is_dataclass
from typing import Any

from frontend.language_surface.nodes import (
    ArrayLiteralNode,
    AssignmentStatementNode,
    CallExpressionNode,
    ConstStatementNode,
    ExpressionNode,
    FloatLiteralNode,
    IdentifierNode,
    IntegerLiteralNode,
    LetStatementNode,
    MemberAccessNode,
    ParenthesizedExpressionNode,
    ResultStatementNode,
    ReturnStatementNode,
    StringLiteralNode,
    UnaryExpressionNode,
    UnaryOperator,
    to_json_value,
)

from .runtime import DTYPES, TensorRuntime
from .operations import operation_signature

LOWERINGS: dict[str, tuple[str, ...]] = {
    "tensor.relu": ("tensor.maximum",),
    "tensor.softmax": (
        "tensor.max",
        "tensor.subtract",
        "tensor.exp",
        "tensor.sum",
        "tensor.divide",
    ),
    "tensor.linear": ("tensor.matmul", "tensor.add"),
    "tensor.conv2d": (
        "tensor.im2col",
        "tensor.matmul",
        "tensor.reshape",
    ),
    "tensor.max_pool2d": ("tensor.window", "tensor.max"),
    "tensor.avg_pool2d": ("tensor.window", "tensor.mean"),
    "tensor.grad": ("tensor.reverse_mode_vjp",),
}


class TensorSemanticError(ValueError):
    """Stable semantic diagnostic raised before Reason IR lowering."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code} {message}")


def public_registry() -> tuple[dict[str, Any], ...]:
    """Return the deterministic, serializable Tensor namespace registry."""
    runtime = TensorRuntime()
    return tuple(runtime.contracts[name].to_dict() for name in runtime.function_ids())


def tensor_call_name(value: Any) -> str | None:
    """Resolve ``tensor.name(...)`` without treating ``tensor`` as a module."""
    value = value.expression if isinstance(value, ExpressionNode) else value
    if not isinstance(value, CallExpressionNode):
        return None
    callee = value.callee
    if (
        isinstance(callee, MemberAccessNode)
        and isinstance(callee.object, IdentifierNode)
        and callee.object.name == "tensor"
    ):
        return f"tensor.{callee.member}"
    return None


def validate_tensor_call(value: CallExpressionNode) -> None:
    name = tensor_call_name(value)
    if name is None:
        return
    contracts = {entry["qualified_name"]: entry for entry in public_registry()}
    if name not in contracts:
        raise TensorSemanticError("NS-030", f"qualified Tensor symbol not found: {name}")

    signature = operation_signature(name)
    minimum, maximum = signature.limits if signature is not None else (1, 3)
    if not minimum <= len(value.arguments) <= maximum:
        raise TensorSemanticError(
            "TSF-016",
            f"Tensor function argument count mismatch: {name} expects {minimum}..{maximum}",
        )
    if name == "tensor.create":
        literal = _literal(value.arguments[0])
        if literal is not _UNKNOWN:
            _literal_shape(literal)
        if len(value.arguments) >= 2:
            dtype = _literal(value.arguments[1])
            if dtype is not _UNKNOWN and dtype not in DTYPES:
                raise TensorSemanticError("TSF-002", f"unsupported dtype: {dtype}")
    tensor_argument_count = {
        "tensor.relu": 1,
        "tensor.softmax": 1,
        "tensor.linear": 2,
        "tensor.matmul": 2,
        "tensor.reshape": 1,
        "tensor.transpose": 1,
        "tensor.slice": 1,
        "tensor.narrow": 1,
        "tensor.gather": 2,
        "tensor.save": 1,
        "tensor.parameter": 1,
        "tensor.detach": 1,
        "tensor.requires_grad": 1,
        "tensor.grad": 1,
        "tensor.conv2d": 2,
        "tensor.max_pool2d": 1,
        "tensor.avg_pool2d": 1,
    }.get(name, 0)
    for argument in value.arguments[:tensor_argument_count]:
        literal = _literal(argument)
        if literal is not _UNKNOWN:
            raise TensorSemanticError("TSF-015", "Tensor argument type mismatch")
    if name == "tensor.softmax" and len(value.arguments) == 2:
        axis = _literal(value.arguments[1])
        if axis is not _UNKNOWN and not isinstance(axis, int):
            raise TensorSemanticError("TSF-015", "Tensor axis must be int")
        shape = infer_tensor_shape(value.arguments[0])
        if isinstance(axis, int) and shape is not None:
            rank = len(shape)
            if axis < -rank or axis >= rank:
                raise TensorSemanticError("TSF-005", "axis is out of range")
    if name == "tensor.reshape":
        source_shape = infer_tensor_shape(value.arguments[0])
        target = _literal(value.arguments[1])
        if source_shape is not None and isinstance(target, list) and all(
            isinstance(item, int) for item in target
        ):
            known = 1
            inferred = 0
            for item in target:
                if item == -1:
                    inferred += 1
                else:
                    known *= item
            source_size = _product(source_shape)
            if inferred > 1 or known == 0 or (inferred == 0 and known != source_size) or (
                inferred == 1 and source_size % known
            ):
                raise TensorSemanticError("TSF-007", "reshape element count mismatch")
    if name in {"tensor.matmul", "tensor.linear"}:
        left = infer_tensor_shape(value.arguments[0])
        right = infer_tensor_shape(value.arguments[1])
        if left is not None and right is not None and (
            len(left) != 2 or len(right) != 2 or left[1] != right[0]
        ):
            raise TensorSemanticError("TSF-008", "tensor.matmul dimension mismatch")


def infer_tensor_shape(
    value: Any, bindings: dict[str, tuple[int, ...]] | None = None
) -> tuple[int, ...] | None:
    bindings = bindings or {}
    value = value.expression if isinstance(value, ExpressionNode) else value
    if isinstance(value, IdentifierNode):
        return bindings.get(value.name)
    if isinstance(value, CallExpressionNode):
        name = tensor_call_name(value)
        if name == "tensor.create":
            literal = _literal(value.arguments[0])
            if literal is not _UNKNOWN:
                return _literal_shape(literal)
        if name in {
            "tensor.relu",
            "tensor.softmax",
            "tensor.parameter",
            "tensor.detach",
        }:
            return infer_tensor_shape(value.arguments[0], bindings)
        if name in {
            "tensor.random_uniform",
            "tensor.random_normal",
            "tensor.random_bernoulli",
        }:
            shape = _literal(value.arguments[0])
            if isinstance(shape, list) and all(
                isinstance(item, int) and item > 0 for item in shape
            ):
                return tuple(shape)
        if name == "tensor.random_permutation":
            size = _literal(value.arguments[0])
            if isinstance(size, int) and size > 0:
                return (size,)
        if name in {"tensor.matmul", "tensor.linear"}:
            left = infer_tensor_shape(value.arguments[0], bindings)
            right = infer_tensor_shape(value.arguments[1], bindings)
            if left is not None and right is not None and len(left) == len(right) == 2:
                return (left[0], right[1])
        if name == "tensor.reshape":
            target = _literal(value.arguments[1])
            if isinstance(target, list) and all(isinstance(item, int) and item >= 0 for item in target):
                return tuple(target)
        if name == "tensor.gather":
            source = infer_tensor_shape(value.arguments[0], bindings)
            indices = infer_tensor_shape(value.arguments[1], bindings)
            axis = _literal(value.arguments[2]) if len(value.arguments) > 2 else 0
            if source is not None and indices is not None and isinstance(axis, int):
                normalized = axis if axis >= 0 else axis + len(source)
                if 0 <= normalized < len(source):
                    return source[:normalized] + indices + source[normalized + 1 :]
        if name == "tensor.narrow":
            source = infer_tensor_shape(value.arguments[0], bindings)
            axis = _literal(value.arguments[1])
            length = _literal(value.arguments[3])
            if source is not None and isinstance(axis, int) and isinstance(length, int):
                normalized = axis if axis >= 0 else axis + len(source)
                if 0 <= normalized < len(source) and length > 0:
                    result = list(source)
                    result[normalized] = length
                    return tuple(result)
        if name == "tensor.slice":
            source = infer_tensor_shape(value.arguments[0], bindings)
            starts = _literal(value.arguments[1])
            ends = _literal(value.arguments[2])
            axes = (
                _literal(value.arguments[3])
                if len(value.arguments) > 3
                else list(range(len(starts) if isinstance(starts, list) else 0))
            )
            steps = (
                _literal(value.arguments[4])
                if len(value.arguments) > 4
                else [1] * (len(starts) if isinstance(starts, list) else 0)
            )
            if (
                source is not None
                and all(isinstance(item, list) for item in (starts, ends, axes, steps))
                and len(starts) == len(ends) == len(axes) == len(steps)
            ):
                result = list(source)
                try:
                    for start, end, axis, step in zip(starts, ends, axes, steps):
                        normalized = axis if axis >= 0 else axis + len(source)
                        result[normalized] = len(
                            range(*slice(start, end, step).indices(source[normalized]))
                        )
                except (IndexError, TypeError, ValueError):
                    return None
                return tuple(result)
        if name == "tensor.conv2d":
            source = infer_tensor_shape(value.arguments[0], bindings)
            weight = infer_tensor_shape(value.arguments[1], bindings)
            if source is not None and weight is not None and len(source) == len(weight) == 4:
                stride = _literal(value.arguments[3]) if len(value.arguments) > 3 else [1, 1]
                padding = _literal(value.arguments[4]) if len(value.arguments) > 4 else [0, 0]
                dilation = _literal(value.arguments[5]) if len(value.arguments) > 5 else [1, 1]
                if all(isinstance(item, list) and len(item) == 2 for item in (stride, padding, dilation)):
                    out_h = (source[2] + 2 * padding[0] - dilation[0] * (weight[2] - 1) - 1) // stride[0] + 1
                    out_w = (source[3] + 2 * padding[1] - dilation[1] * (weight[3] - 1) - 1) // stride[1] + 1
                    return (source[0], weight[0], out_h, out_w)
        if name in {"tensor.max_pool2d", "tensor.avg_pool2d"}:
            source = infer_tensor_shape(value.arguments[0], bindings)
            kernel = _literal(value.arguments[1])
            stride = _literal(value.arguments[2]) if len(value.arguments) > 2 else kernel
            padding = _literal(value.arguments[3]) if len(value.arguments) > 3 else [0, 0]
            if source is not None and len(source) == 4 and all(
                isinstance(item, list) and len(item) == 2
                for item in (kernel, stride, padding)
            ):
                return (
                    source[0],
                    source[1],
                    (source[2] + 2 * padding[0] - kernel[0]) // stride[0] + 1,
                    (source[3] + 2 * padding[1] - kernel[1]) // stride[1] + 1,
                )
    return None


def tensor_operations(value: Any) -> list[dict[str, Any]]:
    """Lower calls in source order to deterministic Reason IR tensor nodes."""
    calls = list(_walk_tensor_calls(value))
    bindings = _shape_bindings(value)
    call_bindings = _call_bindings(value)
    escaping_bindings, escaping_calls = _escaping_values(value)
    final_binding_calls: dict[str, int] = {}
    for call in calls:
        if binding := call_bindings.get(id(call)):
            final_binding_calls[binding] = id(call)
    output_by_call: dict[int, str] = {}
    output_by_binding: dict[str, str] = {}
    result: list[dict[str, Any]] = []
    for index, call in enumerate(calls, 1):
        validate_tensor_call(call)
        function = tensor_call_name(call)
        assert function is not None
        _validate_bound_shapes(call, function, bindings)
        shape = infer_tensor_shape(call, bindings)
        operation_id = f"tensor_call_{index:03d}"
        output_ref = f"tensor_value_{index:03d}"
        dependencies = _call_dependencies(
            call, output_by_call, output_by_binding
        )
        binding = call_bindings.get(id(call))
        lifecycle = _lifecycle_for_call(
            function,
            binding,
            escaping_bindings,
            id(call) in escaping_calls,
            binding is not None and final_binding_calls.get(binding) == id(call),
        )
        result.append(
            {
                "node_type": "tensor_call",
                "operation_id": operation_id,
                "function": function,
                "semantic_operation": function,
                "lowered_operations": list(LOWERINGS.get(function, (function,))),
                "arguments": [
                    {"position": position, "value": to_json_value(argument)}
                    for position, argument in enumerate(call.arguments)
                ],
                "output_ref": output_ref,
                "dependencies": dependencies,
                "binding": binding,
                "lifecycle": lifecycle,
                "tensor_metadata": {
                    "shape": list(shape) if shape is not None else ["unknown"],
                    "rank": len(shape) if shape is not None else "unknown",
                    "dtype": _dtype_for_call(call),
                    "external_value_policy": "tensor",
                },
                "source_ref": {"line": None, "column": None},
            }
        )
        output_by_call[id(call)] = output_ref
        if binding is not None:
            output_by_binding[binding] = output_ref
    _apply_last_use_analysis(result)
    return result


def _call_bindings(value: Any) -> dict[int, str]:
    result: dict[int, str] = {}

    def visit(item: Any) -> None:
        if isinstance(item, (LetStatementNode, ConstStatementNode, AssignmentStatementNode)):
            call = _outer_tensor_call(item.expression)
            if call is not None:
                binding = getattr(item, "identifier", getattr(item, "target", None))
                if isinstance(binding, str):
                    result[id(call)] = binding
        if is_dataclass(item) and not isinstance(item, type):
            for part in fields(item):
                visit(getattr(item, part.name))
        elif isinstance(item, (tuple, list)):
            for part in item:
                visit(part)

    visit(value)
    return result


def _outer_tensor_call(value: Any) -> CallExpressionNode | None:
    value = value.expression if isinstance(value, ExpressionNode) else value
    while isinstance(value, ParenthesizedExpressionNode):
        value = value.expression
        value = value.expression if isinstance(value, ExpressionNode) else value
    return value if isinstance(value, CallExpressionNode) and tensor_call_name(value) else None


def _escaping_values(value: Any) -> tuple[set[str], set[int]]:
    bindings: set[str] = set()
    calls: set[int] = set()

    def collect(item: Any) -> None:
        item = item.expression if isinstance(item, ExpressionNode) else item
        while isinstance(item, ParenthesizedExpressionNode):
            item = item.expression
            item = item.expression if isinstance(item, ExpressionNode) else item
        if isinstance(item, IdentifierNode):
            bindings.add(item.name)
            return
        if isinstance(item, CallExpressionNode):
            if tensor_call_name(item) is not None:
                calls.add(id(item))
            return
        if is_dataclass(item) and not isinstance(item, type):
            for part in fields(item):
                collect(getattr(item, part.name))
        elif isinstance(item, (tuple, list)):
            for part in item:
                collect(part)

    def visit(item: Any) -> None:
        if isinstance(item, (ResultStatementNode, ReturnStatementNode)):
            collect(item.expression)
            return
        if is_dataclass(item) and not isinstance(item, type):
            for part in fields(item):
                visit(getattr(item, part.name))
        elif isinstance(item, (tuple, list)):
            for part in item:
                visit(part)

    visit(value)
    return bindings, calls


def _call_dependencies(
    call: CallExpressionNode,
    output_by_call: dict[int, str],
    output_by_binding: dict[str, str],
) -> list[str]:
    dependencies: list[str] = []

    def add(reference: str) -> None:
        if reference not in dependencies:
            dependencies.append(reference)

    def visit(item: Any) -> None:
        item = item.expression if isinstance(item, ExpressionNode) else item
        if isinstance(item, CallExpressionNode) and tensor_call_name(item) is not None:
            reference = output_by_call.get(id(item))
            if reference is not None:
                add(reference)
                return
        if isinstance(item, IdentifierNode):
            reference = output_by_binding.get(item.name)
            if reference is not None:
                add(reference)
            return
        if is_dataclass(item) and not isinstance(item, type):
            for part in fields(item):
                visit(getattr(item, part.name))
        elif isinstance(item, (tuple, list)):
            for part in item:
                visit(part)

    for argument in call.arguments:
        visit(argument)
    return dependencies


def _lifecycle_for_call(
    function: str,
    binding: str | None,
    escaping_bindings: set[str],
    escapes_directly: bool,
    is_final_binding: bool,
) -> str:
    if function == "tensor.parameter":
        return "Parameter"
    if function == "tensor.load":
        return "Artifact"
    if escapes_directly or (
        is_final_binding and binding is not None and binding in escaping_bindings
    ):
        return "Observation"
    return "Intermediate" if binding is not None else "Temporary"


def _apply_last_use_analysis(operations: list[dict[str, Any]]) -> None:
    """Annotate Reason IR values with deterministic consumer and last-use data."""
    consumers = {operation["output_ref"]: [] for operation in operations}
    for operation in operations:
        step = int(operation["operation_id"].rsplit("_", 1)[-1])
        for dependency in operation["dependencies"]:
            if dependency in consumers:
                consumers[dependency].append(step)
    for operation in operations:
        creation_step = int(operation["operation_id"].rsplit("_", 1)[-1])
        uses = consumers[operation["output_ref"]]
        operation["ref_count"] = len(uses)
        operation["last_use_step"] = max(uses, default=creation_step)


def _validate_bound_shapes(
    call: CallExpressionNode,
    function: str,
    bindings: dict[str, tuple[int, ...]],
) -> None:
    if function in {"tensor.matmul", "tensor.linear"}:
        left = infer_tensor_shape(call.arguments[0], bindings)
        right = infer_tensor_shape(call.arguments[1], bindings)
        if left is not None and right is not None and (
            len(left) != 2 or len(right) != 2 or left[1] != right[0]
        ):
            raise TensorSemanticError("TSF-008", "tensor.matmul dimension mismatch")
        if function == "tensor.linear" and len(call.arguments) == 3 and left and right:
            bias = infer_tensor_shape(call.arguments[2], bindings)
            output = (left[0], right[1])
            if bias is not None and not _broadcast_compatible(output, bias):
                raise TensorSemanticError("TSF-006", "linear bias cannot be broadcast")


def _broadcast_compatible(left: tuple[int, ...], right: tuple[int, ...]) -> bool:
    for a, b in zip(reversed(left), reversed(right)):
        if a != b and a != 1 and b != 1:
            return False
    return True


def _shape_bindings(value: Any) -> dict[str, tuple[int, ...]]:
    statements: list[Any] = []

    def visit(item: Any) -> None:
        if isinstance(item, (LetStatementNode, ConstStatementNode, AssignmentStatementNode)):
            statements.append(item)
        if is_dataclass(item) and not isinstance(item, type):
            for part in fields(item):
                visit(getattr(item, part.name))
        elif isinstance(item, (tuple, list)):
            for part in item:
                visit(part)

    visit(value)
    result: dict[str, tuple[int, ...]] = {}
    # A small fixed point handles forward-independent calculation bindings
    # while preserving deterministic ordering.
    for _ in range(len(statements) + 1):
        changed = False
        for statement in statements:
            shape = infer_tensor_shape(statement.expression, result)
            target = getattr(statement, "identifier", getattr(statement, "target", None))
            if isinstance(target, str) and shape is not None and result.get(target) != shape:
                result[target] = shape
                changed = True
        if not changed:
            break
    return result


def tensor_execution_plan(operations: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Project semantic Tensor nodes into a backend-neutral physical plan."""
    operations = list(operations)
    by_output = {operation["output_ref"]: operation for operation in operations}
    physical = []
    for index, operation in enumerate(operations, 1):
        dependencies = list(operation.get("dependencies", ()))
        metadata = operation["tensor_metadata"]
        release_after = [
            reference
            for reference in dependencies
            if by_output[reference]["last_use_step"] == index
            and by_output[reference]["lifecycle"]
            not in {"Parameter", "Persistent", "Artifact", "Observation"}
        ]
        if (
            operation["ref_count"] == 0
            and operation["last_use_step"] == index
            and operation["lifecycle"] in {"Intermediate", "Temporary"}
        ):
            release_after.append(operation["output_ref"])
        physical.append(
            {
                "operation_id": f"op_{operation['operation_id']}",
                "operation_type": "tensor_call",
                "function": operation["function"],
                "backend_operation": operation["function"].split(".", 1)[1],
                "semantic_operation": operation["semantic_operation"],
                "lowered_operations": list(operation["lowered_operations"]),
                "dependencies": dependencies,
                "output_ref": operation["output_ref"],
                "binding": operation.get("binding"),
                "lifecycle": operation["lifecycle"],
                "ref_count": operation["ref_count"],
                "last_use_step": operation["last_use_step"],
                "release_after": release_after,
                "shape": list(metadata["shape"]),
                "dtype": metadata["dtype"],
                "execution_order": index,
                "source_ref": dict(operation["source_ref"]),
            }
        )
    return {
        "schema_version": "reasonscript-tensor-execution-plan/0.1",
        "operations": physical,
        "deterministic": True,
        "backend": "abstract",
        "lifetime_policy": {
            "analysis": "reason_ir_last_use",
            "release_condition": "ref_count_zero_and_non_persistent",
            "protected_classes": ["Parameter", "Persistent", "Artifact"],
        },
    }


def _walk_tensor_calls(value: Any):
    # Calls are emitted post-order so nested producers precede consumers.
    if isinstance(value, ExpressionNode):
        yield from _walk_tensor_calls(value.expression)
        return
    if isinstance(value, CallExpressionNode):
        for argument in value.arguments:
            yield from _walk_tensor_calls(argument)
        if tensor_call_name(value) is not None:
            yield value
        return
    if is_dataclass(value) and not isinstance(value, type):
        for item in fields(value):
            yield from _walk_tensor_calls(getattr(value, item.name))
        return
    if isinstance(value, (tuple, list)):
        for item in value:
            yield from _walk_tensor_calls(item)


_UNKNOWN = object()


def _literal(value: Any) -> Any:
    value = value.expression if isinstance(value, ExpressionNode) else value
    if isinstance(value, (IntegerLiteralNode, FloatLiteralNode, StringLiteralNode)):
        return value.value
    if isinstance(value, UnaryExpressionNode) and value.operator == UnaryOperator.NEGATE:
        operand = _literal(value.operand)
        return -operand if isinstance(operand, (int, float)) else _UNKNOWN
    if isinstance(value, ArrayLiteralNode):
        result = [_literal(item) for item in value.elements]
        return _UNKNOWN if any(item is _UNKNOWN for item in result) else result
    return _UNKNOWN


def _literal_shape(value: Any) -> tuple[int, ...]:
    if not isinstance(value, list):
        if not isinstance(value, (bool, int, float)):
            raise TensorSemanticError("TSF-015", "Tensor argument type mismatch")
        return ()
    if not value:
        raise TensorSemanticError("TSF-009", "Empty tensor is not allowed")
    children = [_literal_shape(item) for item in value]
    if any(item != children[0] for item in children[1:]):
        raise TensorSemanticError("TSF-017", "Tensor input array must be rectangular")
    return (len(value),) + children[0]


def _dtype_for_call(call: CallExpressionNode) -> str:
    name = tensor_call_name(call)
    if name == "tensor.create" and len(call.arguments) >= 2:
        dtype = _literal(call.arguments[1])
        if isinstance(dtype, str):
            return dtype
    return "f64"


def _product(shape: tuple[int, ...]) -> int:
    result = 1
    for dimension in shape:
        result *= dimension
    return result
