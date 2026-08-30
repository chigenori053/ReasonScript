"""Deterministic evaluator for integrated Tensor and bounded loop operations."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from frontend.language_surface.nodes import (
    ArrayLiteralNode,
    AssignmentStatementNode,
    BinaryExpressionNode,
    BinaryOperator,
    BooleanLiteralNode,
    BreakStatementNode,
    CalculationNode,
    CallExpressionNode,
    ComparisonExpressionNode,
    ComparisonOperator,
    ConstStatementNode,
    ContinueStatementNode,
    DefaultPatternNode,
    EnumDeclarationNode,
    EnumValuePatternNode,
    ExpressionNode,
    ExpressionStatementNode,
    FieldAssignmentStatementNode,
    FloatLiteralNode,
    ForStatementNode,
    FunctionDeclarationNode,
    GoalNode,
    IdentifierNode,
    IdentifierPatternNode,
    IfStatementNode,
    ImportNode,
    IndexAccessNode,
    IndexAssignmentStatementNode,
    IntegerLiteralNode,
    LetStatementNode,
    LogicalExpressionNode,
    LogicalOperator,
    LoopStatementNode,
    LiteralPatternNode,
    MatchStatementNode,
    MemberAccessNode,
    NoneLiteralNode,
    NullLiteralNode,
    OptionalPatternNode,
    OptionalValuePatternNode,
    OrPatternNode,
    ParenthesizedExpressionNode,
    ProgramNode,
    QualifiedIdentifierNode,
    QualifiedPatternNode,
    ReasonGraphDeclarationNode,
    ReasonObjectBindingNode,
    RangePatternNode,
    ResultStatementNode,
    ReturnStatementNode,
    RuntimeCallExpressionNode,
    StateDeclarationNode,
    ConstraintNode,
    ExecutionPlanDeclarationNode,
    StringLiteralNode,
    StructBindingPatternNode,
    StructPatternNode,
    StructLiteralNode,
    SomeExpressionNode,
    UnaryExpressionNode,
    UnaryOperator,
    WhileStatementNode,
    WildcardPatternNode,
)
from frontend.relation.integration import relation_call_name
from frontend.reason_object_runtime import (
    ReasonObjectRuntimeError,
    call_ruo,
    load_reason_object,
)
from frontend.reasoning_reference import ReasoningReferenceError, call_reasoning
from frontend.tensor.integration import LOWERINGS, tensor_call_name
from frontend.tensor.optimizers import optimizer_call_name
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


class _Return(Exception):
    def __init__(self, value: Any):
        self.value = value


class LoopLimitError(ValueError):
    code = "RT-LOOP-001"


class IntegratedRuntimeError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass
class RuntimeStruct:
    type_name: str
    fields: dict[str, Any]


@dataclass(frozen=True)
class RuntimeEnumValue:
    enum_name: str
    variant_name: str

    def to_runtime_value(self) -> dict[str, Any]:
        return {"enum": self.enum_name, "variant": self.variant_name}


@dataclass(frozen=True)
class RuntimeOptionalSome:
    value: Any

    def to_runtime_value(self) -> dict[str, Any]:
        return {"optional": "some", "value": self.value}


@dataclass(frozen=True)
class RuntimeOptionalNone:
    def to_runtime_value(self) -> dict[str, Any]:
        return {"optional": "none"}


OPTIONAL_NONE = RuntimeOptionalNone()


@dataclass
class RuntimeFunction:
    node: FunctionDeclarationNode
    bindings: dict[str, "RuntimeFunction"]
    globals: dict[str, Any] | None = None


_RELATION_ARGUMENT_COUNTS: dict[str, int] = {
    "relation.filter_eq": 3,
    "relation.filter_ne": 3,
    "relation.filter_gt": 3,
    "relation.filter_gte": 3,
    "relation.filter_lt": 3,
    "relation.filter_lte": 3,
    "relation.count": 1,
    "relation.distinct_by": 2,
    "relation.sort_by": 3,
}

_RELATION_COMPARISONS: dict[str, Any] = {
    "relation.filter_eq": lambda a, b: a == b,
    "relation.filter_ne": lambda a, b: a != b,
    "relation.filter_gt": lambda a, b: a > b,
    "relation.filter_gte": lambda a, b: a >= b,
    "relation.filter_lt": lambda a, b: a < b,
    "relation.filter_lte": lambda a, b: a <= b,
}


def _relation_rows(value: Any) -> list[RuntimeStruct]:
    if not isinstance(value, list) or not all(isinstance(item, RuntimeStruct) for item in value):
        raise IntegratedRuntimeError("REL-004", "Relation function requires Array<Struct>")
    return value


def _relation_field(row: RuntimeStruct, field: str) -> Any:
    if field not in row.fields:
        raise IntegratedRuntimeError("REL-005", f"unknown field {field} on {row.type_name}")
    return row.fields[field]


def call_relation(function_id: str, *args: Any) -> Any:
    """Dispatch a `relation.*` function (Phase 8 "relational algebra core").

    A plain module-level function, not a method on any runtime class:
    every `relation.*` function is pure -- it reads `Array<Struct>`/field
    values and returns a new plain Python value, with no Tensor backend,
    autograd, or other persistent state involved (unlike
    `TensorRuntime.call`/`call_optimizer`). Comparisons reuse Python's
    native operators (`==`, `<`, ...), the same semantics
    `ComparisonExpressionNode` already uses elsewhere in this module, so
    a field comparison behaves identically to a plain `a < b` expression
    -- including raising a `TypeError` for genuinely incomparable types,
    normalized below into a diagnostic rather than left to leak raw.
    """
    if function_id not in _RELATION_ARGUMENT_COUNTS:
        raise IntegratedRuntimeError("REL-001", f"unknown Relation function: {function_id}")
    expected = _RELATION_ARGUMENT_COUNTS[function_id]
    if len(args) != expected:
        raise IntegratedRuntimeError(
            "REL-002",
            f"Relation function argument count mismatch: {function_id} expects {expected}",
        )
    if function_id == "relation.count":
        return len(_relation_rows(args[0]))
    if function_id in _RELATION_COMPARISONS:
        rows, field, value = args
        compare = _RELATION_COMPARISONS[function_id]
        try:
            return [row for row in _relation_rows(rows) if compare(_relation_field(row, field), value)]
        except TypeError as error:
            raise IntegratedRuntimeError("REL-006", f"Relation comparison is undefined: {error}") from error
    if function_id == "relation.distinct_by":
        rows, field = args
        # A linear equality scan, not a hash set: `distinct_by` must
        # accept any comparable field value (including Array/Struct
        # field values, which aren't hashable), matching the Rust side
        # (`relation_dispatch.rs`'s `distinct_by`, which never hashes
        # either -- Value has no Hash impl, only PartialEq).
        seen: list[Any] = []
        result = []
        for row in _relation_rows(rows):
            key = _relation_field(row, field)
            if key not in seen:
                seen.append(key)
                result.append(row)
        return result
    if function_id == "relation.sort_by":
        rows, field, descending = args
        if not isinstance(descending, bool):
            raise IntegratedRuntimeError("REL-007", "Relation sort_by descending must be Bool")
        try:
            return sorted(
                _relation_rows(rows),
                key=lambda row: _relation_field(row, field),
                reverse=descending,
            )
        except TypeError as error:
            raise IntegratedRuntimeError("REL-006", f"Relation field is not orderable: {error}") from error
    raise IntegratedRuntimeError("REL-001", f"unknown Relation function: {function_id}")


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
            "reasoning_trace": list(getattr(self.runtime, "reasoning_trace", [])),
            "calculations": {
                name: _plain(value, self.runtime)
                for name, value in sorted(self.calculation_results.items())
            },
        }


def execute_program(
    program: ProgramNode, *, max_loop_iterations: int = 10_000,
    max_call_depth: int = 128,
    resource_root: Path | None = None,
    filesystem_read: bool = False,
    filesystem_write: bool = False,
) -> IntegratedComputationResult:
    runtime = TensorRuntime(
        resource_root=resource_root or Path.cwd(),
        filesystem_read=filesystem_read,
        filesystem_write=filesystem_write,
    )
    runtime.reasoning_trace = []
    vision_runtime = VisionRuntimeBridge(resource_root or Path.cwd(), filesystem_read=filesystem_read, filesystem_write=filesystem_write)
    loop_trace: list[dict[str, Any]] = []
    calculations: dict[str, Any] = {}
    object_root = (resource_root or Path.cwd()).resolve()
    module_objects: dict[str, dict[str, Any]] = {}
    for module in program.modules:
        loaded: dict[str, Any] = {}
        for item in module.body:
            if isinstance(item, (
                GoalNode,
                StateDeclarationNode,
                ConstraintNode,
                ReasonGraphDeclarationNode,
                ExecutionPlanDeclarationNode,
            )):
                loaded[item.name] = item.name
            if not isinstance(item, ReasonObjectBindingNode):
                continue
            try:
                loaded[item.name] = load_reason_object(
                    object_root / item.source_path,
                    object_root,
                    filesystem_read=filesystem_read,
                    filesystem_write=filesystem_write,
                    expected_object_id=item.expected_object_id,
                )
            except ReasonObjectRuntimeError as error:
                raise IntegratedRuntimeError(error.code, str(error)) from error
        module_objects[module.name] = loaded
    enum_registry: dict[str, dict[str, dict[str, RuntimeEnumValue]]] = {}
    for module in program.modules:
        enum_registry[module.name] = {
            item.name: {
                variant.name: RuntimeEnumValue(item.name, variant.name)
                for variant in item.values
            }
            for item in module.body
            if isinstance(item, EnumDeclarationNode)
        }
        module_objects[module.name].update(enum_registry[module.name])
    for module in program.modules:
        for item in module.body:
            if not isinstance(item, ImportNode) or item.resolution is None:
                continue
            target = enum_registry.get(item.resolution.namespace.rsplit(".", 1)[-1], {})
            if item.resolution.symbol in target:
                namespace = target[item.resolution.symbol]
                for exposed_name in item.resolution.exposed_names:
                    module_objects[module.name][exposed_name] = namespace
            elif item.resolution.symbol is None:
                for exposed_name in item.resolution.exposed_names:
                    if exposed_name in target:
                        module_objects[module.name][exposed_name] = target[exposed_name]
    function_registry: dict[str, RuntimeFunction] = {}
    package_prefix = f"{program.package.name}." if program.package is not None else ""
    for module in program.modules:
        for item in module.body:
            if isinstance(item, FunctionDeclarationNode):
                canonical = f"{package_prefix}{module.name}::{item.name}"
                function_registry[canonical] = RuntimeFunction(item, {})

    module_functions: dict[str, dict[str, RuntimeFunction]] = {}
    for module in program.modules:
        bindings = dict(function_registry)
        for item in module.body:
            if isinstance(item, FunctionDeclarationNode):
                canonical = f"{package_prefix}{module.name}::{item.name}"
                bindings[item.name] = function_registry[canonical]
            elif isinstance(item, ImportNode) and item.resolution is not None:
                for exposed_name in item.resolution.exposed_names:
                    canonical = (
                        f"{item.resolution.namespace}::"
                        f"{item.resolution.symbol or exposed_name}"
                    )
                    if canonical in function_registry:
                        bindings[exposed_name] = function_registry[canonical]
        module_functions[module.name] = bindings

    for canonical, function in function_registry.items():
        module_namespace = canonical.rsplit("::", 1)[0]
        module_name = module_namespace.rsplit(".", 1)[-1]
        function.bindings = module_functions[module_name]
        function.globals = module_objects[module_name]

    for module in program.modules:
        functions = module_functions[module.name]
        for calculation in (
            item for item in module.body if isinstance(item, CalculationNode)
        ):
            env = {**module_objects[module.name], **calculations}
            try:
                _statements(
                    calculation.body,
                    env,
                    runtime,
                    loop_trace,
                    max_loop_iterations,
                    calculation.name,
                    vision_runtime,
                    functions,
                    max_call_depth,
                    0,
                )
            except _Result as result:
                calculations[calculation.name] = result.value
                runtime.collect(calculations)
            else:
                runtime.collect(calculations)
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
    functions: dict[str, FunctionDeclarationNode],
    max_call_depth: int,
    call_depth: int,
) -> None:
    for statement in statements:
        if isinstance(statement, (LetStatementNode, ConstStatementNode)):
            env[statement.identifier] = _expression(
                statement.expression, env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            )
        elif isinstance(statement, AssignmentStatementNode):
            env[statement.target] = _expression(
                statement.expression, env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            )
        elif isinstance(statement, IndexAssignmentStatementNode):
            _assign_index(
                statement.target, statement.expression, env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            )
        elif isinstance(statement, FieldAssignmentStatementNode):
            _assign_field(
                statement.target, statement.expression, env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            )
        elif isinstance(statement, ResultStatementNode):
            raise _Result(_expression(
                statement.expression, env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            ))
        elif isinstance(statement, ReturnStatementNode):
            raise _Return(_expression(
                statement.expression, env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            ))
        elif isinstance(statement, ExpressionStatementNode):
            _expression(
                statement.expression, env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            )
        elif isinstance(statement, BreakStatementNode):
            raise _Break()
        elif isinstance(statement, ContinueStatementNode):
            raise _Continue()
        elif isinstance(statement, ForStatementNode):
            values = _expression(
                statement.iterable, env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            )
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
                functions,
                max_call_depth,
                call_depth,
            )
        elif isinstance(statement, WhileStatementNode):
            _while_loop(
                statement, env, runtime, trace, limit, scope, vision_runtime,
                functions, max_call_depth, call_depth,
            )
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
                functions,
                max_call_depth,
                call_depth,
            )
        elif isinstance(statement, IfStatementNode):
            selected = None
            if _expression(
                statement.condition, env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            ):
                selected = statement.body
            else:
                for branch in statement.elif_branches:
                    if _expression(
                        branch.condition, env, runtime, vision_runtime,
                        functions, max_call_depth, call_depth,
                    ):
                        selected = branch.body
                        break
                if selected is None and statement.else_branch is not None:
                    selected = statement.else_branch.body
            if selected is not None:
                _statements(
                    selected, env, runtime, trace, limit, scope, vision_runtime,
                    functions, max_call_depth, call_depth,
                )
        elif isinstance(statement, MatchStatementNode):
            subject = _expression(
                statement.expression, env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            )
            selected = False
            for arm in statement.arms:
                bindings = _match_pattern(arm.pattern.pattern, subject)
                if bindings is None:
                    continue
                previous = {name: env[name] for name in bindings if name in env}
                missing = set(bindings) - set(previous)
                env.update(bindings)
                try:
                    if arm.guard is not None and not bool(_expression(
                        arm.guard, env, runtime, vision_runtime,
                        functions, max_call_depth, call_depth,
                    )):
                        continue
                    selected = True
                    _statements(
                        arm.body, env, runtime, trace, limit, scope,
                        vision_runtime, functions, max_call_depth, call_depth,
                    )
                    break
                finally:
                    for name in missing:
                        env.pop(name, None)
                    env.update(previous)
            if not selected:
                raise IntegratedRuntimeError("RT-MATCH-001", "match expression selected no arm")
        runtime.collect(env)


def _match_pattern(pattern: Any, value: Any) -> dict[str, Any] | None:
    if isinstance(pattern, IdentifierPatternNode):
        return {pattern.name: value}
    if isinstance(pattern, (WildcardPatternNode, DefaultPatternNode)):
        return {}
    if isinstance(pattern, LiteralPatternNode):
        return {} if value == getattr(pattern.value, "value", None) else None
    if isinstance(pattern, RangePatternNode):
        try:
            lower_ok = value >= pattern.lower.value if pattern.lower_inclusive else value > pattern.lower.value
            upper_ok = value <= pattern.upper.value if pattern.upper_inclusive else value < pattern.upper.value
        except TypeError:
            return None
        return {} if lower_ok and upper_ok else None
    if isinstance(pattern, EnumValuePatternNode):
        expected = RuntimeEnumValue(pattern.enum_name, pattern.value_name)
        return {} if value == expected else None
    if isinstance(pattern, QualifiedPatternNode):
        expected = RuntimeEnumValue(pattern.namespace, pattern.identifier)
        return {} if value == expected else None
    if isinstance(pattern, OptionalPatternNode):
        if pattern.kind == "None":
            return {} if isinstance(value, RuntimeOptionalNone) else None
        if not isinstance(value, RuntimeOptionalSome):
            return None
        return {pattern.binding: value.value} if pattern.binding else {}
    if isinstance(pattern, OptionalValuePatternNode):
        if pattern.kind == "None":
            return {} if isinstance(value, RuntimeOptionalNone) else None
        if not isinstance(value, RuntimeOptionalSome):
            return None
        return _match_pattern(pattern.pattern, value.value)
    if isinstance(pattern, StructBindingPatternNode):
        return {pattern.binding: value}
    if isinstance(pattern, StructPatternNode):
        if not isinstance(value, RuntimeStruct) or value.type_name != pattern.type_name:
            return None
        bindings: dict[str, Any] = {}
        for field in pattern.fields:
            if field.field_name not in value.fields:
                return None
            nested = _match_pattern(field.pattern, value.fields[field.field_name])
            if nested is None:
                return None
            bindings.update(nested)
        return bindings
    if isinstance(pattern, OrPatternNode):
        for alternative in pattern.alternatives:
            bindings = _match_pattern(alternative, value)
            if bindings is not None:
                return bindings
        return None
    return None


def _while_loop(
    statement: WhileStatementNode,
    env: dict[str, Any],
    runtime: TensorRuntime,
    trace: list[dict[str, Any]],
    limit: int,
    scope: str,
    vision_runtime: VisionRuntimeBridge,
    functions: dict[str, FunctionDeclarationNode],
    max_call_depth: int,
    call_depth: int,
) -> None:
    iteration = 0
    loop_id = f"{scope}.while"
    while _expression(
        statement.condition, env, runtime, vision_runtime,
        functions, max_call_depth, call_depth,
    ):
        if iteration >= limit:
            raise LoopLimitError(f"loop iteration limit exceeded: {limit}")
        iteration += 1
        previous = _trace_env(env)
        broke = False
        continued = False
        try:
            _statements(
                statement.body, env, runtime, trace, limit, scope, vision_runtime,
                functions, max_call_depth, call_depth,
            )
        except _Continue:
            continued = True
        except _Break:
            broke = True
        trace.append(_loop_event(loop_id, iteration, previous, env, broke, continued))
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
    functions: dict[str, FunctionDeclarationNode],
    max_call_depth: int,
    call_depth: int,
) -> None:
    iteration = 0
    while values is None or iteration < len(values):
        if iteration >= limit:
            raise LoopLimitError(f"loop iteration limit exceeded: {limit}")
        if values is not None and iterator is not None:
            env[iterator] = values[iteration]
        iteration += 1
        previous = _trace_env(env)
        broke = False
        continued = False
        try:
            _statements(
                body, env, runtime, trace, limit, loop_id, vision_runtime,
                functions, max_call_depth, call_depth,
            )
        except _Continue:
            continued = True
        except _Break:
            broke = True
        trace.append(_loop_event(loop_id, iteration, previous, env, broke, continued))
        if broke:
            break


def _expression(
    value: Any,
    env: dict[str, Any],
    runtime: TensorRuntime,
    vision_runtime: VisionRuntimeBridge,
    functions: dict[str, FunctionDeclarationNode],
    max_call_depth: int,
    call_depth: int,
) -> Any:
    value = value.expression if isinstance(value, ExpressionNode) else value
    if isinstance(value, (IntegerLiteralNode, FloatLiteralNode, BooleanLiteralNode, StringLiteralNode)):
        return value.value
    if isinstance(value, NoneLiteralNode):
        return OPTIONAL_NONE
    if isinstance(value, NullLiteralNode):
        return None
    if isinstance(value, SomeExpressionNode):
        return RuntimeOptionalSome(_expression(
            value.value, env, runtime, vision_runtime,
            functions, max_call_depth, call_depth,
        ))
    if isinstance(value, IdentifierNode):
        if value.name not in env:
            raise IntegratedRuntimeError("RT-NAME-001", f"unknown runtime name: {value.name}")
        return env[value.name]
    if isinstance(value, ArrayLiteralNode):
        return [
            _expression(
                item, env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            )
            for item in value.elements
        ]
    if isinstance(value, StructLiteralNode):
        return RuntimeStruct(
            value.type_name,
            {
                field.name: _expression(
                    field.expression, env, runtime, vision_runtime,
                    functions, max_call_depth, call_depth,
                )
                for field in value.fields
            },
        )
    if isinstance(value, ParenthesizedExpressionNode):
        return _expression(
            value.expression, env, runtime, vision_runtime,
            functions, max_call_depth, call_depth,
        )
    if isinstance(value, UnaryExpressionNode):
        operand = _expression(
            value.operand, env, runtime, vision_runtime,
            functions, max_call_depth, call_depth,
        )
        return -operand if value.operator == UnaryOperator.NEGATE else not operand
    if isinstance(value, BinaryExpressionNode):
        left = _expression(
            value.left, env, runtime, vision_runtime,
            functions, max_call_depth, call_depth,
        )
        right = _expression(
            value.right, env, runtime, vision_runtime,
            functions, max_call_depth, call_depth,
        )
        if value.operator in (BinaryOperator.DIVIDE, BinaryOperator.MODULO) and right == 0:
            raise IntegratedRuntimeError("RT-ARITH-001", "division or modulo by zero")
        return {
            BinaryOperator.ADD: lambda: left + right,
            BinaryOperator.SUBTRACT: lambda: left - right,
            BinaryOperator.MULTIPLY: lambda: left * right,
            BinaryOperator.DIVIDE: lambda: left / right,
            BinaryOperator.MODULO: lambda: left % right,
        }[value.operator]()
    if isinstance(value, ComparisonExpressionNode):
        left = _expression(
            value.left, env, runtime, vision_runtime,
            functions, max_call_depth, call_depth,
        )
        right = _expression(
            value.right, env, runtime, vision_runtime,
            functions, max_call_depth, call_depth,
        )
        return {
            ComparisonOperator.EQUAL: lambda: left == right,
            ComparisonOperator.NOT_EQUAL: lambda: left != right,
            ComparisonOperator.GREATER_THAN: lambda: left > right,
            ComparisonOperator.GREATER_THAN_OR_EQUAL: lambda: left >= right,
            ComparisonOperator.LESS_THAN: lambda: left < right,
            ComparisonOperator.LESS_THAN_OR_EQUAL: lambda: left <= right,
        }[value.operator]()
    if isinstance(value, LogicalExpressionNode):
        left = bool(_expression(
            value.left, env, runtime, vision_runtime,
            functions, max_call_depth, call_depth,
        ))
        return (
            left and bool(_expression(
                value.right, env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            ))
            if value.operator == LogicalOperator.AND
            else left or bool(_expression(
                value.right, env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            ))
        )
    if isinstance(value, IndexAccessNode):
        collection = _expression(
            value.collection, env, runtime, vision_runtime,
            functions, max_call_depth, call_depth,
        )
        index = _expression(
            value.index, env, runtime, vision_runtime,
            functions, max_call_depth, call_depth,
        )
        return _index_value(collection, index, runtime)
    if isinstance(value, MemberAccessNode):
        owner = _expression(
            value.object, env, runtime, vision_runtime,
            functions, max_call_depth, call_depth,
        )
        if isinstance(owner, RuntimeStruct):
            if value.member not in owner.fields:
                raise IntegratedRuntimeError(
                    "RT-FIELD-001",
                    f"unknown field {value.member} on {owner.type_name}",
                )
            return owner.fields[value.member]
        if isinstance(owner, dict) and value.member in owner:
            return owner[value.member]
        if isinstance(owner, (list, tuple, dict)) and value.member == "length":
            return len(owner)
        raise IntegratedRuntimeError(
            "RT-FIELD-001", f"member access is unsupported: {value.member}"
        )
    if isinstance(value, RuntimeCallExpressionNode):
        argument = _expression(
            value.arguments[0], env, runtime, vision_runtime,
            functions, max_call_depth, call_depth,
        )
        try:
            result, trace = call_reasoning(f"runtime.{value.method}", argument)
        except ReasoningReferenceError as error:
            raise IntegratedRuntimeError(error.code, str(error)) from error
        runtime.reasoning_trace.append(trace)
        return result
    if isinstance(value, CallExpressionNode):
        if (
            isinstance(value.callee, MemberAccessNode)
            and isinstance(value.callee.object, IdentifierNode)
            and value.callee.object.name == "ruo"
        ):
            arguments = [
                _expression(
                    argument, env, runtime, vision_runtime,
                    functions, max_call_depth, call_depth,
                )
                for argument in value.arguments
            ]
            try:
                return call_ruo(f"ruo.{value.callee.member}", *arguments)
            except ReasonObjectRuntimeError as error:
                raise IntegratedRuntimeError(error.code, str(error)) from error
        vision_function = vision_call_name(value)
        if vision_function is not None:
            arguments = [
                _expression(
                    argument, env, runtime, vision_runtime,
                    functions, max_call_depth, call_depth,
                )
                for argument in value.arguments
            ]
            return vision_runtime.call(vision_function, *arguments)
        function = tensor_call_name(value)
        if function is not None:
            arguments = [
                _expression(
                    argument, env, runtime, vision_runtime,
                    functions, max_call_depth, call_depth,
                )
                for argument in value.arguments
            ]
            source_location = getattr(value, "_source_location", None)
            result = runtime.call(
                function,
                *arguments,
                _source_location=source_location,
            )
            runtime.trace[-1].update(
                {
                    "operation_id": f"op_tensor_call_{len(runtime.trace):03d}",
                    "semantic_operation": function,
                    "lowered_operations": list(LOWERINGS.get(function, (function,))),
                    "source_ref": source_location,
                }
            )
            return result
        optimizer_function = optimizer_call_name(value)
        if optimizer_function is not None:
            arguments = [
                _expression(
                    argument, env, runtime, vision_runtime,
                    functions, max_call_depth, call_depth,
                )
                for argument in value.arguments
            ]
            source_location = getattr(value, "_source_location", None)
            return runtime.call_optimizer(
                optimizer_function, *arguments, _source_location=source_location
            )
        relation_function = relation_call_name(value)
        if relation_function is not None:
            arguments = [
                _expression(
                    argument, env, runtime, vision_runtime,
                    functions, max_call_depth, call_depth,
                )
                for argument in value.arguments
            ]
            return call_relation(relation_function, *arguments)
        if (
            isinstance(value.callee, MemberAccessNode)
            and isinstance(value.callee.object, IdentifierNode)
            and value.callee.object.name == "array"
            and value.callee.member == "append"
        ):
            if len(value.arguments) != 2:
                raise IntegratedRuntimeError(
                    "RT-CALL-002", "array.append expects two arguments"
                )
            collection = _expression(
                value.arguments[0], env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            )
            item = _expression(
                value.arguments[1], env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            )
            if not isinstance(collection, list):
                raise IntegratedRuntimeError(
                    "RT-CALL-002", "array.append first argument must be an array"
                )
            return [*collection, copy.deepcopy(item)]
        if (
            isinstance(value.callee, MemberAccessNode)
            and isinstance(value.callee.object, IdentifierNode)
            and value.callee.object.name == "array"
            and value.callee.member == "concat"
        ):
            if len(value.arguments) != 2:
                raise IntegratedRuntimeError(
                    "RT-CALL-002", "array.concat expects two arguments"
                )
            left = _expression(
                value.arguments[0], env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            )
            right = _expression(
                value.arguments[1], env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            )
            if not isinstance(left, list) or not isinstance(right, list):
                raise IntegratedRuntimeError(
                    "RT-CALL-002", "array.concat arguments must be arrays"
                )
            return [*copy.deepcopy(left), *copy.deepcopy(right)]
        if (
            isinstance(value.callee, MemberAccessNode)
            and isinstance(value.callee.object, IdentifierNode)
            and value.callee.object.name == "string"
        ):
            func_name = value.callee.member
            args = [
                _expression(arg, env, runtime, vision_runtime, functions, max_call_depth, call_depth)
                for arg in value.arguments
            ]
            if func_name == "concat":
                if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], str):
                    raise IntegratedRuntimeError("RT-CALL-002", "string.concat expects two string arguments")
                return args[0] + args[1]
            elif func_name == "join":
                if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], list):
                    raise IntegratedRuntimeError("RT-CALL-002", "string.join expects separator and list of strings")
                for item in args[1]:
                    if not isinstance(item, str):
                        raise IntegratedRuntimeError("RT-CALL-002", "string.join list elements must be strings")
                return args[0].join(args[1])
            elif func_name == "length":
                if len(args) != 1 or not isinstance(args[0], str):
                    raise IntegratedRuntimeError("RT-CALL-002", "string.length expects one string argument")
                return len(args[0])
            elif func_name == "from_int":
                if len(args) != 1 or isinstance(args[0], bool) or not isinstance(args[0], int):
                    raise IntegratedRuntimeError("RT-CALL-002", "string.from_int expects one int argument")
                return str(args[0])
            elif func_name == "from_float":
                if len(args) != 1 or isinstance(args[0], bool) or not isinstance(args[0], (float, int)):
                    raise IntegratedRuntimeError("RT-CALL-002", "string.from_float expects one float argument")
                return str(float(args[0]))
            elif func_name == "slice":
                if len(args) != 3 or not isinstance(args[0], str) or isinstance(args[1], bool) or not isinstance(args[1], int) or isinstance(args[2], bool) or not isinstance(args[2], int):
                    raise IntegratedRuntimeError("RT-CALL-002", "string.slice expects string, int, int")
                s, start, end = args[0], args[1], args[2]
                if start < 0:
                    start = 0
                if end < start:
                    end = start
                return s[start:end]
            else:
                raise IntegratedRuntimeError("RT-CALL-002", f"unknown string standard function: string.{func_name}")
        if isinstance(value.callee, IdentifierNode) and value.callee.name == "assert":
            if len(value.arguments) != 1:
                raise IntegratedRuntimeError("TEST-ASSERT-001", "assert expects 1 argument")
            cond = _expression(value.arguments[0], env, runtime, vision_runtime, functions, max_call_depth, call_depth)
            if not isinstance(cond, bool):
                raise IntegratedRuntimeError("TEST-ASSERT-001", "assert condition must evaluate to boolean")
            if not cond:
                raise IntegratedRuntimeError("TEST-ASSERT-001", "assertion failed")
            return True
        if isinstance(value.callee, IdentifierNode) and value.callee.name == "assert_eq":
            if len(value.arguments) != 2:
                raise IntegratedRuntimeError("TEST-ASSERT-001", "assert_eq expects 2 arguments")
            left = _expression(value.arguments[0], env, runtime, vision_runtime, functions, max_call_depth, call_depth)
            right = _expression(value.arguments[1], env, runtime, vision_runtime, functions, max_call_depth, call_depth)
            if left != right:
                raise IntegratedRuntimeError("TEST-ASSERT-001", f"assertion failed: {left} != {right}")
            return True
        if (
            isinstance(value.callee, IdentifierNode)
            and value.callee.name in {"float", "int"}
            and value.callee.name not in functions
        ):
            if len(value.arguments) != 1:
                raise IntegratedRuntimeError(
                    "RT-CALL-002", f"{value.callee.name}() expects exactly one argument"
                )
            argument = _expression(
                value.arguments[0], env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            )
            if isinstance(argument, bool) or not isinstance(argument, (int, float)):
                raise IntegratedRuntimeError(
                    "RT-CALL-005", f"{value.callee.name}() argument must be Int or Float"
                )
            return float(argument) if value.callee.name == "float" else int(argument)
        if isinstance(value.callee, (IdentifierNode, QualifiedIdentifierNode)):
            function_ref = (
                functions.get(value.callee.name)
                if isinstance(value.callee, IdentifierNode)
                else functions.get(
                    value.callee.resolved_name
                    or "::".join((*value.callee.path, value.callee.symbol))
                )
            )
            if function_ref is None:
                raise IntegratedRuntimeError(
                    "RT-CALL-001",
                    f"unknown runtime function: {_callee_label(value.callee)}",
                )
            function_node = function_ref.node
            if len(value.arguments) != len(function_node.parameters):
                raise IntegratedRuntimeError(
                    "RT-CALL-002",
                    f"function argument count mismatch: {_callee_label(value.callee)}",
                )
            if call_depth >= max_call_depth:
                raise IntegratedRuntimeError(
                    "RT-CALL-003",
                    f"function call depth exceeded: {max_call_depth}",
                )
            arguments = [
                _expression(
                    argument, env, runtime, vision_runtime,
                    functions, max_call_depth, call_depth,
                )
                for argument in value.arguments
            ]
            local_env = dict(function_ref.globals or {})
            local_env.update({
                _parameter_name(parameter): argument
                for parameter, argument in zip(function_node.parameters, arguments)
            })
            try:
                with runtime.protect(env):
                    _statements(
                        function_node.body,
                        local_env,
                        runtime,
                        [],
                        10_000,
                        f"fn.{function_node.name}",
                        vision_runtime,
                        function_ref.bindings,
                        max_call_depth,
                        call_depth + 1,
                    )
            except _Return as returned:
                return returned.value
            raise IntegratedRuntimeError(
                "RT-CALL-004", f"function returned no value: {function_node.name}"
            )
    raise ValueError(f"unsupported integrated runtime expression: {type(value).__name__}")


def _parameter_name(parameter: Any) -> str:
    return parameter["name"] if isinstance(parameter, dict) else str(parameter)


def _callee_label(callee: IdentifierNode | QualifiedIdentifierNode) -> str:
    if isinstance(callee, IdentifierNode):
        return callee.name
    return callee.resolved_name or "::".join((*callee.path, callee.symbol))


def _index_value(collection: Any, index: Any, runtime: TensorRuntime) -> Any:
    if isinstance(index, bool) or not isinstance(index, (int, str)):
        raise IntegratedRuntimeError("RT-INDEX-001", "index must be int or map key")
    if isinstance(collection, TensorValueRef):
        collection = runtime.to_array(collection)
    if isinstance(collection, (list, tuple)):
        if not isinstance(index, int):
            raise IntegratedRuntimeError("RT-INDEX-001", "array index must be int")
        if index < 0 or index >= len(collection):
            raise IntegratedRuntimeError("RT-INDEX-002", f"index out of range: {index}")
        return collection[index]
    if isinstance(collection, dict):
        if index not in collection:
            raise IntegratedRuntimeError("RT-INDEX-002", f"map key not found: {index}")
        return collection[index]
    raise IntegratedRuntimeError("RT-INDEX-003", "value is not indexable")


def _assign_index(
    target: Any,
    expression: Any,
    env: dict[str, Any],
    runtime: TensorRuntime,
    vision_runtime: VisionRuntimeBridge,
    functions: dict[str, FunctionDeclarationNode],
    max_call_depth: int,
    call_depth: int,
) -> None:
    target_value = target.expression if isinstance(target, ExpressionNode) else target
    if not isinstance(target_value, IndexAccessNode):
        raise IntegratedRuntimeError("RT-INDEX-003", "invalid index assignment target")
    collection = _expression(
        target_value.collection, env, runtime, vision_runtime,
        functions, max_call_depth, call_depth,
    )
    index = _expression(
        target_value.index, env, runtime, vision_runtime,
        functions, max_call_depth, call_depth,
    )
    new_value = _expression(
        expression, env, runtime, vision_runtime,
        functions, max_call_depth, call_depth,
    )
    if isinstance(collection, list):
        if isinstance(index, bool) or not isinstance(index, int):
            raise IntegratedRuntimeError("RT-INDEX-001", "array index must be int")
        if index < 0 or index >= len(collection):
            raise IntegratedRuntimeError("RT-INDEX-002", f"index out of range: {index}")
        collection[index] = new_value
        return
    if isinstance(collection, dict):
        collection[index] = new_value
        return
    raise IntegratedRuntimeError("RT-INDEX-003", "value is not mutable by index")


def _assign_field(
    target: Any,
    expression: Any,
    env: dict[str, Any],
    runtime: TensorRuntime,
    vision_runtime: VisionRuntimeBridge,
    functions: dict[str, FunctionDeclarationNode],
    max_call_depth: int,
    call_depth: int,
) -> None:
    target_value = target.expression if isinstance(target, ExpressionNode) else target
    if not isinstance(target_value, MemberAccessNode):
        raise IntegratedRuntimeError("RT-FIELD-002", "invalid field assignment target")
    owner = _expression(
        target_value.object, env, runtime, vision_runtime,
        functions, max_call_depth, call_depth,
    )
    if not isinstance(owner, RuntimeStruct) or target_value.member not in owner.fields:
        raise IntegratedRuntimeError(
            "RT-FIELD-002", f"unknown mutable field: {target_value.member}"
        )
    owner.fields[target_value.member] = _expression(
        expression, env, runtime, vision_runtime,
        functions, max_call_depth, call_depth,
    )


def _loop_event(
    loop_id: str,
    iteration: int,
    previous: dict[str, Any],
    env: dict[str, Any],
    broke: bool,
    continued: bool,
) -> dict[str, Any]:
    return {
        "loop_id": loop_id,
        "iteration": iteration,
        "condition": True,
        "previous_state": previous,
        "updated_state": _trace_env(env),
        "break_triggered": broke,
        "continue_triggered": continued,
    }

def _trace_env(env: dict[str, Any]) -> dict[str, Any]:
    return {name: _trace_plain(value) for name, value in sorted(env.items())}


def _plain(value: Any, runtime: TensorRuntime) -> Any:
    if isinstance(value, TensorValueRef):
        return runtime.to_array(value)
    if isinstance(value, RuntimeStruct):
        return {
            name: _plain(item, runtime)
            for name, item in sorted(value.fields.items())
        }
    if hasattr(value, "to_runtime_value"):
        return _plain(value.to_runtime_value(), runtime)
    if isinstance(value, dict):
        return {
            str(name): _plain(item, runtime)
            for name, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [_plain(item, runtime) for item in value]
    return value


def _trace_plain(value: Any) -> Any:
    if isinstance(value, TensorValueRef):
        return value.runtime_value()
    if isinstance(value, RuntimeStruct):
        return {
            name: _trace_plain(item)
            for name, item in sorted(value.fields.items())
        }
    if hasattr(value, "to_runtime_value"):
        return _trace_plain(value.to_runtime_value())
    if isinstance(value, dict):
        return {
            str(name): _trace_plain(item)
            for name, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [_trace_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_trace_plain(item) for item in value]
    return value


def _stable_trace(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if key != "duration_ns"}
