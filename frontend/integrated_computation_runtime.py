"""Deterministic evaluator for integrated Tensor and bounded loop operations."""

from __future__ import annotations

import copy
import math
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from frontend.entity import (
    EntityKind as ReasonEntityModelKind,
    EntityRecord,
    canonical_entity_id,
)
from frontend.entity.slot import EntityEnvironment as ReasonEntityEnvironment
from frontend.language_surface.integration import (
    _expression_identifiers as _reason_expression_identifiers,
)
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
    ConstDeclarationNode,
    ConstStatementNode,
    ContinueStatementNode,
    ExpressionNode,
    ExpressionStatementNode,
    FieldAssignmentStatementNode,
    FloatLiteralNode,
    ForStatementNode,
    FunctionDeclarationNode,
    IdentifierNode,
    IfStatementNode,
    ImportNode,
    IndexAccessNode,
    IndexAssignmentStatementNode,
    IntegerLiteralNode,
    LetStatementNode,
    LogicalExpressionNode,
    LogicalOperator,
    LoopStatementNode,
    MemberAccessNode,
    ModuleNode,
    NoneLiteralNode,
    NullLiteralNode,
    ParenthesizedExpressionNode,
    ProgramNode,
    QualifiedIdentifierNode,
    ReasonEntityDeclarationNode,
    ReasonEntityKind,
    ReasonStateTransitionNode,
    ResultStatementNode,
    ReturnStatementNode,
    StringLiteralNode,
    StructLiteralNode,
    UnaryExpressionNode,
    UnaryOperator,
    WhileStatementNode,
    entity_value_type_label,
)
from frontend.tensor.integration import LOWERINGS, tensor_call_name
from frontend.tensor.runtime import TensorError, TensorRuntime, TensorValueRef
from frontend.vision.integration import vision_call_name
from frontend.vision.runtime import VisionRuntimeBridge
from frontend.optimizer import OptimizerError, call_optimizer, optimizer_call_name

_SURFACE_TO_MODEL_ENTITY_KIND = {
    ReasonEntityKind.RU: ReasonEntityModelKind.RU,
    ReasonEntityKind.RUS: ReasonEntityModelKind.RUS,
    ReasonEntityKind.RUO: ReasonEntityModelKind.RUO,
    ReasonEntityKind.DERIVE: ReasonEntityModelKind.DERIVE,
}


@dataclass
class _RuntimeEntityScope:
    """Companion index mapping a module's Entity identifiers to their
    Canonical IDs, alongside the RU Slot runtime that owns their state.
    Threaded through recursive evaluation via a ContextVar rather than an
    added parameter on every one of the ~46 mutually-recursive `_statements`/
    `_expression` call sites in this module (RS-RE-FSM-001 SS3.8 C-5)."""

    environment: ReasonEntityEnvironment
    identifiers: dict[str, str] = field(default_factory=dict)


_CURRENT_ENTITY_SCOPE: ContextVar["_RuntimeEntityScope | None"] = ContextVar(
    "reasonscript_current_entity_scope", default=None
)


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


@dataclass
class RuntimeFunction:
    node: FunctionDeclarationNode
    bindings: dict[str, "RuntimeFunction"]


@dataclass
class IntegratedComputationResult:
    value: Any
    runtime: TensorRuntime
    loop_trace: list[dict[str, Any]]
    calculation_results: dict[str, Any]
    vision_runtime: VisionRuntimeBridge | None = None
    result_artifact_dir: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "reasonscript-integrated-runtime/0.1",
            "status": "success",
            "result": _plain(self.value, self.runtime, self.result_artifact_dir),
            "tensor_metadata": [
                ref.metadata()
                for ref in sorted(self.runtime._refs.values(), key=lambda item: item.tensor_id)
            ],
            "tensor_trace": [_stable_trace(item) for item in self.runtime.trace],
            "loop_trace": list(self.loop_trace),
            "vision_trace": list(self.vision_runtime.trace) if self.vision_runtime is not None else [],
            "calculations": {
                name: _plain(value, self.runtime, self.result_artifact_dir)
                for name, value in sorted(self.calculation_results.items())
            },
        }


def execute_program(
    program: ProgramNode, *, max_loop_iterations: int = 10_000,
    max_call_depth: int = 128,
    resource_root: Path | None = None,
    filesystem_read: bool = False,
    filesystem_write: bool = False,
    result_artifact_dir: Path | None = None,
) -> IntegratedComputationResult:
    runtime = TensorRuntime(
        resource_root=resource_root or Path.cwd(),
        filesystem_read=filesystem_read,
        filesystem_write=filesystem_write,
    )
    vision_runtime = VisionRuntimeBridge(resource_root or Path.cwd(), filesystem_read=filesystem_read, filesystem_write=filesystem_write)
    loop_trace: list[dict[str, Any]] = []
    calculations: dict[str, Any] = {}
    function_registry: dict[str, RuntimeFunction] = {}
    package_prefix = f"{program.package.name}." if program.package is not None else ""
    for module in program.modules:
        for item in module.body:
            if isinstance(item, FunctionDeclarationNode):
                function_registry[f"{package_prefix}{module.name}::{item.name}"] = RuntimeFunction(item, {})
    module_functions: dict[str, dict[str, RuntimeFunction]] = {}
    for module in program.modules:
        bindings = dict(function_registry)
        for item in module.body:
            if isinstance(item, FunctionDeclarationNode):
                bindings[item.name] = function_registry[f"{package_prefix}{module.name}::{item.name}"]
            elif isinstance(item, ImportNode) and item.resolution is not None:
                for exposed_name in item.resolution.exposed_names:
                    canonical = f"{item.resolution.namespace}::{item.resolution.symbol or exposed_name}"
                    if canonical in function_registry:
                        bindings[exposed_name] = function_registry[canonical]
        module_functions[module.name] = bindings
    for function in function_registry.values():
        module_name = next(
            name for name, module in ((module.name, module) for module in program.modules)
            if any(item is function.node for item in module.body)
        )
        function.bindings = module_functions[module_name]
    package = program.package.name if program.package else None
    for module in program.modules:
        functions = module_functions[module.name]
        scope = _RuntimeEntityScope(environment=ReasonEntityEnvironment())
        token = _CURRENT_ENTITY_SCOPE.set(scope)
        try:
            module_bindings = _declare_module_bindings(
                module, package, scope, runtime, vision_runtime, functions, max_call_depth,
            )
            for calculation in (
                item for item in module.body if isinstance(item, CalculationNode)
            ):
                env = {**module_bindings, **calculations}
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
                    runtime.collect(calculations, scope.environment.all_slots())
                else:
                    runtime.collect(calculations, scope.environment.all_slots())
        finally:
            _CURRENT_ENTITY_SCOPE.reset(token)
    value = next(reversed(calculations.values()), None) if calculations else None
    return IntegratedComputationResult(
        value, runtime, loop_trace, calculations, vision_runtime, result_artifact_dir
    )


def _declare_module_bindings(
    module: ModuleNode,
    package: str | None,
    scope: "_RuntimeEntityScope",
    runtime: TensorRuntime,
    vision_runtime: VisionRuntimeBridge,
    functions: dict[str, "RuntimeFunction"],
    max_call_depth: int,
) -> dict[str, Any]:
    """Resolve module-level `const` and Reason Entity declarations before
    any calculation runs (fixes D-7: module-level bindings were previously
    invisible to calculation bodies). Assumes `_CURRENT_ENTITY_SCOPE` is
    already set to `scope` by the caller."""
    module_bindings: dict[str, Any] = {}
    for node in module.body:
        if isinstance(node, ConstDeclarationNode):
            module_bindings[node.name] = _expression(
                node.expression, module_bindings, runtime, vision_runtime,
                functions, max_call_depth, 0,
            )
        elif isinstance(node, ReasonEntityDeclarationNode):
            _declare_runtime_entity(
                node, (), None, module.name, package, scope, module_bindings,
                runtime, vision_runtime, functions, max_call_depth,
            )
    return module_bindings


def _declare_runtime_entity(
    node: ReasonEntityDeclarationNode,
    owner_path: tuple[str, ...],
    owner_canonical_id: str | None,
    module_name: str,
    package: str | None,
    scope: "_RuntimeEntityScope",
    module_bindings: dict[str, Any],
    runtime: TensorRuntime,
    vision_runtime: VisionRuntimeBridge,
    functions: dict[str, "RuntimeFunction"],
    max_call_depth: int,
) -> None:
    canonical_id = canonical_entity_id(
        kind=_SURFACE_TO_MODEL_ENTITY_KIND[node.kind],
        package=package,
        module=module_name,
        owner_path=owner_path,
        identifier=node.identifier,
    )
    if node.kind in (ReasonEntityKind.RUS, ReasonEntityKind.RUO):
        scope.environment.declare_structure(EntityRecord(
            canonical_id=canonical_id,
            kind=_SURFACE_TO_MODEL_ENTITY_KIND[node.kind],
            identifier=node.identifier,
            owner_id=owner_canonical_id,
        ))
        for member in node.members:
            _declare_runtime_entity(
                member, (*owner_path, node.identifier), canonical_id,
                module_name, package, scope, module_bindings,
                runtime, vision_runtime, functions, max_call_depth,
            )
        return
    dependencies: tuple[str, ...] = ()
    if node.kind is ReasonEntityKind.DERIVE and node.initializer is not None:
        referenced = _reason_expression_identifiers(node.initializer)
        dependencies = tuple(
            scope.identifiers[name] for name in sorted(referenced) if name in scope.identifiers
        )
    record = EntityRecord(
        canonical_id=canonical_id,
        kind=_SURFACE_TO_MODEL_ENTITY_KIND[node.kind],
        identifier=node.identifier,
        owner_id=owner_canonical_id,
        dependencies=dependencies,
        value_type=entity_value_type_label(node.type_annotation),
        declared_type=entity_value_type_label(node.type_annotation),
    )
    if node.kind is ReasonEntityKind.DERIVE:
        initializer = node.initializer
        assert initializer is not None
        scope.environment.declare(
            record,
            derive_evaluator=lambda: _expression(
                initializer, module_bindings, runtime, vision_runtime,
                functions, max_call_depth, 0,
            ),
        )
    else:
        assert node.initializer is not None
        value = _expression(
            node.initializer, module_bindings, runtime, vision_runtime,
            functions, max_call_depth, 0,
        )
        scope.environment.declare(record, initial_value=value)
    if owner_canonical_id is None:
        scope.identifiers[node.identifier] = canonical_id


def _statements(
    statements: tuple[Any, ...],
    env: dict[str, Any],
    runtime: TensorRuntime,
    trace: list[dict[str, Any]],
    limit: int,
    scope: str,
    vision_runtime: VisionRuntimeBridge,
    functions: dict[str, RuntimeFunction],
    max_call_depth: int,
    call_depth: int,
) -> None:
    for statement_index, statement in enumerate(statements, start=1):
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
        elif isinstance(statement, ReasonStateTransitionNode):
            entity_scope = _CURRENT_ENTITY_SCOPE.get()
            if entity_scope is None or statement.target not in entity_scope.identifiers:
                raise IntegratedRuntimeError(
                    "RT-ENTITY-001", f"unknown runtime entity: {statement.target}"
                )
            proposed = _expression(
                statement.expression, env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            )
            entity_scope.environment.propose_transition(
                entity_scope.identifiers[statement.target],
                proposed,
                site=f"{scope}#{statement_index}",
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
        entity_scope = _CURRENT_ENTITY_SCOPE.get()
        if entity_scope is not None:
            runtime.collect(env, entity_scope.environment.all_slots())
        else:
            runtime.collect(env)


def _while_loop(
    statement: WhileStatementNode,
    env: dict[str, Any],
    runtime: TensorRuntime,
    trace: list[dict[str, Any]],
    limit: int,
    scope: str,
    vision_runtime: VisionRuntimeBridge,
    functions: dict[str, RuntimeFunction],
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
    functions: dict[str, RuntimeFunction],
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
    if isinstance(value, (NoneLiteralNode, NullLiteralNode)):
        return None
    if isinstance(value, IdentifierNode):
        entity_scope = _CURRENT_ENTITY_SCOPE.get()
        if entity_scope is not None and value.name in entity_scope.identifiers:
            return entity_scope.environment.read(entity_scope.identifiers[value.name])
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
    if isinstance(value, CallExpressionNode):
        optimizer_function = optimizer_call_name(value)
        if optimizer_function is not None:
            arguments: list[Any] = []
            with runtime.protect(arguments):
                for argument in value.arguments:
                    arguments.append(_expression(
                        argument, env, runtime, vision_runtime,
                        functions, max_call_depth, call_depth,
                    ))
                try:
                    return call_optimizer(optimizer_function, runtime, *arguments)
                except OptimizerError as error:
                    raise IntegratedRuntimeError(error.code, str(error)) from error
        vision_function = vision_call_name(value)
        if vision_function is not None:
            arguments: list[Any] = []
            # A sibling argument can invoke a user function, whose statement
            # boundary collection would otherwise release an earlier temporary
            # Tensor argument.  Keep the growing argument list live until the
            # enclosing call consumes every value.
            with runtime.protect(arguments):
                for argument in value.arguments:
                    arguments.append(_expression(
                        argument, env, runtime, vision_runtime,
                        functions, max_call_depth, call_depth,
                    ))
                return vision_runtime.call(vision_function, *arguments)
        function = tensor_call_name(value)
        if function is not None:
            arguments = []
            with runtime.protect(arguments):
                for argument in value.arguments:
                    arguments.append(_expression(
                        argument, env, runtime, vision_runtime,
                        functions, max_call_depth, call_depth,
                    ))
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
        if (
            isinstance(value.callee, IdentifierNode)
            and value.callee.name in {"float", "int"}
            and value.callee.name not in functions
        ):
            argument = _expression(
                value.arguments[0], env, runtime, vision_runtime,
                functions, max_call_depth, call_depth,
            )
            return (
                float(argument)
                if value.callee.name == "float"
                else math.trunc(argument)
            )
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
            arguments = []
            with runtime.protect(arguments):
                for argument in value.arguments:
                    arguments.append(_expression(
                        argument, env, runtime, vision_runtime,
                        functions, max_call_depth, call_depth,
                    ))
                collection, item = arguments
                if not isinstance(collection, list):
                    raise IntegratedRuntimeError(
                        "RT-CALL-002", "array.append first argument must be an array"
                    )
                return [*collection, copy.deepcopy(item)]
        if isinstance(value.callee, (IdentifierNode, QualifiedIdentifierNode)):
            function_ref = (
                functions.get(value.callee.name)
                if isinstance(value.callee, IdentifierNode)
                else functions.get(value.callee.resolved_name or "::".join((*value.callee.path, value.callee.symbol)))
            )
            if function_ref is None:
                raise IntegratedRuntimeError(
                    "RT-CALL-001", f"unknown runtime function: {_callee_label(value.callee)}"
                )
            function_node = function_ref.node
            if len(value.arguments) != len(function_node.parameters):
                raise IntegratedRuntimeError(
                    "RT-CALL-002",
                    f"function argument count mismatch: {value.callee.name}",
                )
            if call_depth >= max_call_depth:
                raise IntegratedRuntimeError(
                    "RT-CALL-003",
                    f"function call depth exceeded: {max_call_depth}",
                )
            arguments = []
            with runtime.protect(arguments):
                for argument in value.arguments:
                    arguments.append(_expression(
                        argument, env, runtime, vision_runtime,
                        functions, max_call_depth, call_depth,
                    ))
                local_env = {
                    _parameter_name(parameter): argument
                    for parameter, argument in zip(function_node.parameters, arguments)
                }
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
    functions: dict[str, RuntimeFunction],
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


def _plain(
    value: Any, runtime: TensorRuntime, result_artifact_dir: Path | None = None
) -> Any:
    if isinstance(value, TensorValueRef):
        if len(runtime._tensor(value).data) > runtime.policy.inline_elements:
            if result_artifact_dir is None:
                return {
                    **value.runtime_value(),
                    "materialization": "required",
                    "reason": "Tensor exceeds inline result policy",
                }
            return runtime.artifact(value, result_artifact_dir)
        return runtime.to_array(value)
    if isinstance(value, RuntimeStruct):
        return {
            name: _plain(item, runtime, result_artifact_dir)
            for name, item in sorted(value.fields.items())
        }
    if isinstance(value, dict):
        return {
            str(name): _plain(item, runtime, result_artifact_dir)
            for name, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [_plain(item, runtime, result_artifact_dir) for item in value]
    return value


def _trace_plain(value: Any) -> Any:
    if isinstance(value, TensorValueRef):
        return value.runtime_value()
    if isinstance(value, RuntimeStruct):
        return {
            name: _trace_plain(item)
            for name, item in sorted(value.fields.items())
        }
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
