"""Deterministic evaluator for integrated Tensor and bounded loop operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from pathlib import Path

from frontend.language_surface.nodes import (
    ArrayLiteralNode,
    AssignmentStatementNode,
    BinaryExpressionNode,
    BinaryOperator,
    BooleanLiteralNode,
    BreakStatementNode,
    CallExpressionNode,
    CalculationNode,
    ComparisonExpressionNode,
    ComparisonOperator,
    ConstStatementNode,
    ContinueStatementNode,
    ExpressionNode,
    ExpressionStatementNode,
    FloatLiteralNode,
    ForStatementNode,
    IdentifierNode,
    IfStatementNode,
    IntegerLiteralNode,
    LetStatementNode,
    LogicalExpressionNode,
    LogicalOperator,
    LoopStatementNode,
    ParenthesizedExpressionNode,
    ProgramNode,
    ResultStatementNode,
    StringLiteralNode,
    UnaryExpressionNode,
    UnaryOperator,
    WhileStatementNode,
)
from frontend.tensor.integration import LOWERINGS, tensor_call_name
from frontend.tensor.runtime import TensorError, TensorRuntime, TensorValueRef
from frontend.vision.integration import vision_call_name
from frontend.vision.runtime import VisionRuntimeBridge


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


class _Result(Exception):
    def __init__(self, value: Any):
        self.value = value


class LoopLimitError(ValueError):
    code = "RT-LOOP-001"


@dataclass
class IntegratedComputationResult:
    value: Any
    runtime: TensorRuntime
    loop_trace: list[dict[str, Any]]
    calculation_results: dict[str, Any]
    vision_runtime: VisionRuntimeBridge | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "reasonscript-integrated-runtime/0.1",
            "status": "success",
            "result": _plain(self.value, self.runtime),
            "tensor_metadata": [
                ref.metadata()
                for ref in sorted(self.runtime._refs.values(), key=lambda item: item.tensor_id)
            ],
            "tensor_trace": [_stable_trace(item) for item in self.runtime.trace],
            "loop_trace": list(self.loop_trace),
            "vision_trace": list(self.vision_runtime.trace) if self.vision_runtime is not None else [],
            "calculations": {
                name: _plain(value, self.runtime)
                for name, value in sorted(self.calculation_results.items())
            },
        }


def execute_program(
    program: ProgramNode, *, max_loop_iterations: int = 10_000,
    resource_root: Path | None = None,
    filesystem_read: bool = False,
    filesystem_write: bool = False,
) -> IntegratedComputationResult:
    runtime = TensorRuntime()
    vision_runtime = VisionRuntimeBridge(resource_root or Path.cwd(), filesystem_read=filesystem_read, filesystem_write=filesystem_write)
    loop_trace: list[dict[str, Any]] = []
    calculations: dict[str, Any] = {}
    for module in program.modules:
        for calculation in (
            item for item in module.body if isinstance(item, CalculationNode)
        ):
            env = dict(calculations)
            try:
                _statements(
                    calculation.body,
                    env,
                    runtime,
                    loop_trace,
                    max_loop_iterations,
                    calculation.name,
                    vision_runtime,
                )
            except _Result as result:
                calculations[calculation.name] = result.value
    value = next(reversed(calculations.values()), None) if calculations else None
    return IntegratedComputationResult(value, runtime, loop_trace, calculations, vision_runtime)


def _statements(
    statements: tuple[Any, ...],
    env: dict[str, Any],
    runtime: TensorRuntime,
    trace: list[dict[str, Any]],
    limit: int,
    scope: str,
    vision_runtime: VisionRuntimeBridge,
) -> None:
    for statement in statements:
        if isinstance(statement, (LetStatementNode, ConstStatementNode)):
            env[statement.identifier] = _expression(statement.expression, env, runtime, vision_runtime)
        elif isinstance(statement, AssignmentStatementNode):
            env[statement.target] = _expression(statement.expression, env, runtime, vision_runtime)
        elif isinstance(statement, ResultStatementNode):
            raise _Result(_expression(statement.expression, env, runtime, vision_runtime))
        elif isinstance(statement, ExpressionStatementNode):
            _expression(statement.expression, env, runtime, vision_runtime)
        elif isinstance(statement, BreakStatementNode):
            raise _Break()
        elif isinstance(statement, ContinueStatementNode):
            raise _Continue()
        elif isinstance(statement, ForStatementNode):
            values = _expression(statement.iterable, env, runtime, vision_runtime)
            _loop(
                statement.body,
                env,
                runtime,
                trace,
                limit,
                f"{scope}.for.{statement.iterator}",
                list(values),
                statement.iterator,
                vision_runtime,
            )
        elif isinstance(statement, WhileStatementNode):
            _while_loop(statement, env, runtime, trace, limit, scope, vision_runtime)
        elif isinstance(statement, LoopStatementNode):
            _loop(
                statement.body,
                env,
                runtime,
                trace,
                limit,
                f"{scope}.loop",
                None,
                None,
                vision_runtime,
            )
        elif isinstance(statement, IfStatementNode):
            selected = None
            if _expression(statement.condition, env, runtime, vision_runtime):
                selected = statement.body
            else:
                for branch in statement.elif_branches:
                    if _expression(branch.condition, env, runtime, vision_runtime):
                        selected = branch.body
                        break
                if selected is None and statement.else_branch is not None:
                    selected = statement.else_branch.body
            if selected is not None:
                _statements(selected, env, runtime, trace, limit, scope, vision_runtime)


def _while_loop(
    statement: WhileStatementNode,
    env: dict[str, Any],
    runtime: TensorRuntime,
    trace: list[dict[str, Any]],
    limit: int,
    scope: str,
    vision_runtime: VisionRuntimeBridge,
) -> None:
    iteration = 0
    loop_id = f"{scope}.while"
    while _expression(statement.condition, env, runtime, vision_runtime):
        if iteration >= limit:
            raise LoopLimitError(f"loop iteration limit exceeded: {limit}")
        iteration += 1
        previous = _plain_env(env, runtime)
        broke = False
        continued = False
        try:
            _statements(statement.body, env, runtime, trace, limit, scope, vision_runtime)
        except _Continue:
            continued = True
        except _Break:
            broke = True
        trace.append(_loop_event(loop_id, iteration, previous, env, runtime, broke, continued))
        if broke:
            break


def _loop(
    body: tuple[Any, ...],
    env: dict[str, Any],
    runtime: TensorRuntime,
    trace: list[dict[str, Any]],
    limit: int,
    loop_id: str,
    values: list[Any] | None,
    iterator: str | None,
    vision_runtime: VisionRuntimeBridge,
) -> None:
    iteration = 0
    while values is None or iteration < len(values):
        if iteration >= limit:
            raise LoopLimitError(f"loop iteration limit exceeded: {limit}")
        if values is not None and iterator is not None:
            env[iterator] = values[iteration]
        iteration += 1
        previous = _plain_env(env, runtime)
        broke = False
        continued = False
        try:
            _statements(body, env, runtime, trace, limit, loop_id, vision_runtime)
        except _Continue:
            continued = True
        except _Break:
            broke = True
        trace.append(_loop_event(loop_id, iteration, previous, env, runtime, broke, continued))
        if broke:
            break


def _expression(value: Any, env: dict[str, Any], runtime: TensorRuntime, vision_runtime: VisionRuntimeBridge) -> Any:
    value = value.expression if isinstance(value, ExpressionNode) else value
    if isinstance(value, (IntegerLiteralNode, FloatLiteralNode, BooleanLiteralNode, StringLiteralNode)):
        return value.value
    if isinstance(value, IdentifierNode):
        return env[value.name]
    if isinstance(value, ArrayLiteralNode):
        return [_expression(item, env, runtime, vision_runtime) for item in value.elements]
    if isinstance(value, ParenthesizedExpressionNode):
        return _expression(value.expression, env, runtime, vision_runtime)
    if isinstance(value, UnaryExpressionNode):
        operand = _expression(value.operand, env, runtime, vision_runtime)
        return -operand if value.operator == UnaryOperator.NEGATE else not operand
    if isinstance(value, BinaryExpressionNode):
        left, right = _expression(value.left, env, runtime, vision_runtime), _expression(value.right, env, runtime, vision_runtime)
        return {
            BinaryOperator.ADD: lambda: left + right,
            BinaryOperator.SUBTRACT: lambda: left - right,
            BinaryOperator.MULTIPLY: lambda: left * right,
            BinaryOperator.DIVIDE: lambda: left / right,
            BinaryOperator.MODULO: lambda: left % right,
        }[value.operator]()
    if isinstance(value, ComparisonExpressionNode):
        left, right = _expression(value.left, env, runtime, vision_runtime), _expression(value.right, env, runtime, vision_runtime)
        return {
            ComparisonOperator.EQUAL: lambda: left == right,
            ComparisonOperator.NOT_EQUAL: lambda: left != right,
            ComparisonOperator.GREATER_THAN: lambda: left > right,
            ComparisonOperator.GREATER_THAN_OR_EQUAL: lambda: left >= right,
            ComparisonOperator.LESS_THAN: lambda: left < right,
            ComparisonOperator.LESS_THAN_OR_EQUAL: lambda: left <= right,
        }[value.operator]()
    if isinstance(value, LogicalExpressionNode):
        left = bool(_expression(value.left, env, runtime, vision_runtime))
        return (
            left and bool(_expression(value.right, env, runtime, vision_runtime))
            if value.operator == LogicalOperator.AND
            else left or bool(_expression(value.right, env, runtime, vision_runtime))
        )
    if isinstance(value, CallExpressionNode):
        vision_function = vision_call_name(value)
        if vision_function is not None:
            arguments = [_expression(argument, env, runtime, vision_runtime) for argument in value.arguments]
            return vision_runtime.call(vision_function, *arguments)
        function = tensor_call_name(value)
        if function is not None:
            arguments = [_expression(argument, env, runtime, vision_runtime) for argument in value.arguments]
            result = runtime.call(function, *arguments)
            runtime.trace[-1].update(
                {
                    "operation_id": f"op_tensor_call_{len(runtime.trace):03d}",
                    "semantic_operation": function,
                    "lowered_operations": list(LOWERINGS.get(function, (function,))),
                    "source_ref": {"line": None, "column": None},
                }
            )
            return result
    raise ValueError(f"unsupported integrated runtime expression: {type(value).__name__}")


def _loop_event(
    loop_id: str,
    iteration: int,
    previous: dict[str, Any],
    env: dict[str, Any],
    runtime: TensorRuntime,
    broke: bool,
    continued: bool,
) -> dict[str, Any]:
    return {
        "loop_id": loop_id,
        "iteration": iteration,
        "condition": True,
        "previous_state": previous,
        "updated_state": _plain_env(env, runtime),
        "break_triggered": broke,
        "continue_triggered": continued,
    }


def _plain_env(env: dict[str, Any], runtime: TensorRuntime) -> dict[str, Any]:
    return {name: _plain(value, runtime) for name, value in sorted(env.items())}


def _plain(value: Any, runtime: TensorRuntime) -> Any:
    if isinstance(value, TensorValueRef):
        return runtime.to_array(value)
    if isinstance(value, list):
        return [_plain(item, runtime) for item in value]
    return value


def _stable_trace(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if key != "duration_ns"}
