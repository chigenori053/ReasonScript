"""Projection from Surface AST to the validated semantic AST/compiler."""

from __future__ import annotations

from typing import Any

from frontend import ast as semantic
from frontend.compiler import compile as compile_semantic

from .nodes import (
    CalculationNode,
    AssignmentStatementNode,
    ArrayLiteralNode,
    BinaryExpressionNode,
    BinaryOperator,
    BreakStatementNode,
    CallExpressionNode,
    ComparisonExpressionNode,
    ConstDeclarationNode,
    ConstStatementNode,
    ContinueStatementNode,
    EnumDeclarationNode,
    ExecutionPlanDeclarationNode,
    ExpressionNode,
    ConstraintNode,
    ExpressionStatementNode,
    FieldAssignmentStatementNode,
    ForStatementNode,
    FunctionDeclarationNode,
    GoalNode,
    GoalStatementNode,
    IdentifierNode,
    ImportNode,
    IfStatementNode,
    IndexAccessNode,
    IndexAssignmentStatementNode,
    LetStatementNode,
    LogicalExpressionNode,
    LoopStatementNode,
    MapLiteralNode,
    MemberAccessNode,
    NoneLiteralNode,
    ModuleNode,
    ParenthesizedExpressionNode,
    ProgramNode,
    QualifiedIdentifierNode,
    ReasonGraphDeclarationNode,
    ReachStatementNode,
    RelationNode,
    RequireStatementNode,
    ResultStatementNode,
    ReturnStatementNode,
    RuntimeCallExpressionNode,
    RuntimeCallKind,
    RuntimeNamespaceNode,
    SetLiteralNode,
    SomeExpressionNode,
    StateDeclarationNode,
    StructDeclarationNode,
    StructLiteralNode,
    TransitionNode,
    TupleLiteralNode,
    UnaryExpressionNode,
    Visibility,
    WhileStatementNode,
    to_json_value,
)
from .validation import SurfaceValidationError, validate
from .namespace import resolve_program


def project_program(program: ProgramNode) -> tuple[semantic.ModuleNode, ...]:
    resolved_program, _ = resolve_program(program)
    validate(resolved_program)
    package = resolved_program.package.name if resolved_program.package else None
    return tuple(
        project_module(module, package=package)
        for module in resolved_program.modules
    )


def project_module(module: ModuleNode, *, package: str | None = None) -> semantic.ModuleNode:
    namespace = f"{package}.{module.name}" if package else module.name
    calculation_order = _topological_calculations(module)
    calculation_dependencies = _calculation_dependencies(module)
    calculation_result_target = (
        f"{calculation_order[-1].name}.state.result"
        if calculation_order
        else None
    )
    declarations: list[Any] = []
    imports: list[str] = []
    surface_goals = [node for node in module.body if isinstance(node, GoalNode)]
    goal_target = surface_goals[0].name if surface_goals else f"{module.name}Result"
    declarations.append(
        semantic.GoalNode(
            f"{namespace}-goal",
            "reach_state",
            calculation_result_target or goal_target,
        )
    )
    declarations.append(
        semantic.StateNode(
            f"{namespace}-state",
            f"{module.name}Start",
            "language_surface",
            {
                "package": package,
                "module": module.name,
                "namespace": namespace,
                "visibility": module.visibility.value,
                "declarations": [
                    type(node).__name__
                    for node in module.body
                    if not isinstance(node, ImportNode)
                ],
            },
        )
    )
    transition_index = 0
    calculations_projected = False
    for node in module.body:
        if isinstance(node, ImportNode):
            imports.append(".".join(node.path))
        elif isinstance(node, ConstraintNode):
            declarations.append(
                semantic.ConstraintNode(
                    f"{namespace}-constraint-{node.name}",
                    node.name,
                    "predicate",
                    node.name,
                )
            )
        elif isinstance(node, RelationNode):
            transition_index += 1
            declarations.append(
                semantic.TransitionNode(
                    f"{namespace}-relation-{transition_index}",
                    f"{namespace}-relation-{transition_index}",
                    node.source,
                    node.relation.value,
                    node.target,
                )
            )
        elif isinstance(node, TransitionNode):
            transition_index += 1
            requirements = [
                statement.constraint
                for statement in node.body
                if isinstance(statement, RequireStatementNode)
            ]
            goal_refs = [
                statement.goal
                for statement in node.body
                if isinstance(statement, GoalStatementNode)
            ]
            reaches = [
                statement.goal
                for statement in node.body
                if isinstance(statement, ReachStatementNode)
            ]
            declarations.append(
                semantic.TransitionNode(
                    f"{namespace}-transition-{transition_index}",
                    node.name,
                    node.from_state,
                    "Transition",
                    reaches[-1] if reaches else node.to_state,
                    guard=" && ".join(requirements) or None,
                    effect={
                        "goals": goal_refs,
                        "body": [to_json_value(item) for item in node.body],
                    },
                )
            )
        elif isinstance(node, CalculationNode):
            if not calculations_projected:
                transition_index = _project_calculations(
                    declarations,
                    calculation_order,
                    namespace=namespace,
                    module=module,
                    start_index=transition_index,
                )
                calculations_projected = True
    return semantic.ModuleNode(
        node_id=namespace,
        imports=tuple(imports),
        declarations=tuple(declarations),
        metadata=(
            semantic.MetadataNode(
                f"{namespace}-surface-version",
                "language_surface",
                "reasonscript-language-surface/0.1",
            ),
            semantic.MetadataNode(
                f"{namespace}-namespace",
                "namespace",
                namespace,
            ),
            semantic.MetadataNode(
                f"{namespace}-package",
                "package",
                package,
            ),
            semantic.MetadataNode(
                f"{namespace}-module",
                "module",
                module.name,
            ),
            semantic.MetadataNode(
                f"{namespace}-exports",
                "exports",
                _exports(module),
            ),
            semantic.MetadataNode(
                f"{namespace}-import-resolution",
                "import_resolution",
                [
                    to_json_value(node.resolution)
                    for node in module.body
                    if isinstance(node, ImportNode) and node.resolution is not None
                ],
            ),
            semantic.MetadataNode(
                f"{namespace}-functions",
                "function_declarations",
                [
                    to_json_value(node)
                    for node in module.body
                    if isinstance(node, FunctionDeclarationNode)
                ],
            ),
            semantic.MetadataNode(
                f"{namespace}-composite-types",
                "composite_declarations",
                [
                    to_json_value(node)
                    for node in module.body
                    if isinstance(node, (StructDeclarationNode, EnumDeclarationNode))
                ],
            ),
            semantic.MetadataNode(
                f"{namespace}-consts",
                "const_declarations",
                [
                    to_json_value(node)
                    for node in module.body
                    if isinstance(node, ConstDeclarationNode)
                ],
            ),
            semantic.MetadataNode(
                f"{namespace}-runtime-calls",
                "runtime_calls",
                _runtime_calls(module),
            ),
            semantic.MetadataNode(
                f"{namespace}-runtime-operations",
                "runtime_operations",
                _runtime_operations(module),
            ),
            semantic.MetadataNode(
                f"{namespace}-reasoning-types",
                "reasoning_types",
                _reasoning_types(module),
            ),
            semantic.MetadataNode(
                f"{namespace}-reasoning-declarations",
                "reasoning_declarations",
                _reasoning_declarations(module),
            ),
            semantic.MetadataNode(
                f"{namespace}-calculation-order",
                "calculation_order",
                [node.name for node in calculation_order],
            ),
            semantic.MetadataNode(
                f"{namespace}-calculation-dependencies",
                "calculation_dependencies",
                [
                    {"source": source, "target": target}
                    for target in sorted(calculation_dependencies)
                    for source in sorted(calculation_dependencies[target])
                ],
            ),
        ),
    )


def _project_calculations(
    declarations: list[Any],
    calculations: tuple[CalculationNode, ...],
    *,
    namespace: str,
    module: ModuleNode,
    start_index: int,
) -> int:
    transition_index = start_index
    current = f"{module.name}Start"
    calculation_names = {node.name for node in calculations}
    for node in calculations:
        local_names: set[str] = set()
        for index, statement in enumerate(node.body, 1):
            identifier, statement_data, relation = _statement_projection(
                statement, index
            )
            expression = _statement_expression(statement)
            if isinstance(statement, (LetStatementNode, ConstStatementNode)):
                local_names.add(statement.identifier)
            if _terminates_with_result(statement):
                identifier = "result"
            transition_index += 1
            target = (
                f"{node.name}.state.result"
                if identifier == "result"
                else f"{node.name}.state.{identifier}"
            )
            declarations.append(
                semantic.TransitionNode(
                    f"{namespace}-calculation-{transition_index}",
                    f"{node.name}-{index}-{identifier}",
                    current,
                    relation,
                    target,
                    effect={
                        "calculation": node.name,
                        "visibility": node.visibility.value,
                        "goal_annotation": node.goal_annotation,
                        "return_type": (
                            to_json_value(node.return_type)
                            if node.return_type is not None
                            else None
                        ),
                        "target": identifier,
                        "statement": statement_data,
                        "inputs": _resolved_expression_inputs(
                            expression,
                            calculation=node.name,
                            calculation_names=calculation_names,
                            local_names=local_names,
                        ),
                        **(
                            {"expression": statement_data["expression"]}
                            if "expression" in statement_data
                            else {}
                        ),
                    },
                )
            )
            current = target
            if isinstance(statement, AssignmentStatementNode):
                local_names.add(statement.target)
    return transition_index


def _exports(module: ModuleNode) -> list[str]:
    exports: list[str] = []
    for node in module.body:
        visibility = getattr(node, "visibility", None)
        if visibility == Visibility.PUBLIC and hasattr(node, "name"):
            exports.append(node.name)
    return exports


def _runtime_calls(module: ModuleNode) -> list[str]:
    calls: list[str] = []
    for node in module.body:
        for call in _walk_runtime_calls(node):
            if call.method not in calls:
                calls.append(call.method)
    return calls


def _runtime_operations(module: ModuleNode) -> list[dict[str, Any]]:
    operations = {
        RuntimeCallKind.INPUT: "InputOperation",
        RuntimeCallKind.PRINT: "PrintOperation",
        RuntimeCallKind.SEARCH: "RuntimeSearchNode",
        RuntimeCallKind.SIMULATION: "RuntimeSimulateNode",
        RuntimeCallKind.PREDICTION: "RuntimePredictNode",
        RuntimeCallKind.PLANNING: "RuntimePlanNode",
    }
    result: list[dict[str, Any]] = []
    for call in _walk_runtime_calls(module):
        argument = call.arguments[0] if call.arguments else None
        result.append(
            {
                "node_type": operations[call.kind],
                "operation": call.method,
                "method": call.method,
                "kind": call.kind.value,
                "argument": to_json_value(argument),
                "arguments": [to_json_value(item) for item in call.arguments],
                **(
                    {"source_state": _runtime_source_state(argument)}
                    if call.kind == RuntimeCallKind.PRINT and argument is not None
                    else {}
                ),
            }
        )
    return result


def _reasoning_types(module: ModuleNode) -> list[str]:
    result: list[str] = []
    for call in _walk_runtime_calls(module):
        if not call.arguments:
            continue
        reasoning_type = _reasoning_type_for_operation(call.method, call.arguments[0])
        if reasoning_type not in result:
            result.append(reasoning_type)
    return result


def _reasoning_declarations(module: ModuleNode) -> dict[str, list[Any]]:
    return {
        "goals": [
            to_json_value(node) for node in module.body if isinstance(node, GoalNode)
        ],
        "states": [
            to_json_value(node)
            for node in module.body
            if isinstance(node, StateDeclarationNode)
        ],
        "constraints": [
            to_json_value(node)
            for node in module.body
            if isinstance(node, ConstraintNode)
        ],
        "reason_graphs": [
            to_json_value(node)
            for node in module.body
            if isinstance(node, ReasonGraphDeclarationNode)
        ],
        "execution_plans": [
            to_json_value(node)
            for node in module.body
            if isinstance(node, ExecutionPlanDeclarationNode)
        ],
    }


def _reasoning_type_for_operation(method: str, argument: Any) -> str:
    if method in {"search", "plan"}:
        return "goal"
    if method == "predict":
        return "state"
    if method == "simulate":
        return "execution_plan"
    return _reasoning_type_from_argument(argument)


def _reasoning_type_from_argument(argument: Any) -> str:
    name = getattr(argument, "name", None)
    type_name = getattr(argument, "type_name", None)
    text = str(type_name or name or "").lower()
    if "constraint" in text:
        return "constraint"
    if "graph" in text:
        return "reason_graph"
    if "plan" in text:
        return "execution_plan"
    if "state" in text:
        return "state"
    return "goal"


def _topological_calculations(module: ModuleNode) -> tuple[CalculationNode, ...]:
    by_name = {
        node.name: node for node in module.body if isinstance(node, CalculationNode)
    }
    dependencies = _calculation_dependencies(module)
    ready = sorted(name for name in by_name if not dependencies[name])
    ordered: list[CalculationNode] = []
    while ready:
        name = ready.pop(0)
        ordered.append(by_name[name])
        for candidate in sorted(dependencies):
            if name in dependencies[candidate]:
                dependencies[candidate].remove(name)
                if not dependencies[candidate]:
                    ready.append(candidate)
                    ready.sort()
        dependencies.pop(name, None)
    if dependencies:
        cycle = ", ".join(sorted(dependencies))
        raise SurfaceValidationError(f"CAL-030 Dependency Cycle Detected: {cycle}")
    return tuple(ordered)


def _calculation_dependencies(module: ModuleNode) -> dict[str, set[str]]:
    calculations = {
        node.name: node for node in module.body if isinstance(node, CalculationNode)
    }
    calculation_names = set(calculations)
    return {
        name: _dependencies_for_calculation(node, calculation_names)
        for name, node in calculations.items()
    }


def _dependencies_for_calculation(
    calculation: CalculationNode, calculation_names: set[str]
) -> set[str]:
    local_names: set[str] = set()
    dependencies: set[str] = set()
    for statement in calculation.body:
        expression = _statement_expression(statement)
        if expression is not None:
            dependencies.update(
                reference
                for reference in _expression_identifiers(expression)
                if reference in calculation_names and reference not in local_names
            )
        if isinstance(statement, (LetStatementNode, ConstStatementNode)):
            local_names.add(statement.identifier)
        elif isinstance(statement, AssignmentStatementNode):
            local_names.add(statement.target)
    dependencies.discard(calculation.name)
    return dependencies


def _statement_expression(statement: Any) -> ExpressionNode | None:
    if isinstance(
        statement,
        (
            LetStatementNode,
            ConstStatementNode,
            AssignmentStatementNode,
            ResultStatementNode,
            ExpressionStatementNode,
        ),
    ):
        return statement.expression
    if isinstance(statement, FieldAssignmentStatementNode):
        return statement.expression
    if isinstance(statement, IndexAssignmentStatementNode):
        return statement.expression
    return None


def _resolved_expression_inputs(
    expression: ExpressionNode | None,
    *,
    calculation: str,
    calculation_names: set[str],
    local_names: set[str],
) -> list[str]:
    if expression is None:
        return []
    inputs: list[str] = []
    for reference in sorted(_expression_identifiers(expression)):
        if reference in calculation_names and reference not in local_names:
            inputs.append(f"{reference}.state.result")
        elif reference in local_names:
            inputs.append(f"{calculation}.state.{reference}")
        else:
            inputs.append(reference)
    return inputs


def _expression_identifiers(expression: ExpressionNode | Any) -> set[str]:
    value = expression.expression if isinstance(expression, ExpressionNode) else expression
    found: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, IdentifierNode):
            found.add(item.name)
            return
        if isinstance(item, QualifiedIdentifierNode):
            return
        if isinstance(item, RuntimeNamespaceNode):
            return
        if isinstance(item, RuntimeCallExpressionNode):
            for argument in item.arguments:
                visit(argument)
            return
        if isinstance(item, UnaryExpressionNode):
            visit(item.operand)
            return
        if isinstance(
            item,
            (
                BinaryExpressionNode,
                ComparisonExpressionNode,
                LogicalExpressionNode,
            ),
        ):
            visit(item.left)
            visit(item.right)
            return
        if isinstance(item, ParenthesizedExpressionNode):
            visit(item.expression)
            return
        if isinstance(item, MemberAccessNode):
            visit(item.object)
            return
        if isinstance(item, CallExpressionNode):
            visit(item.callee)
            for argument in item.arguments:
                visit(argument)
            return
        if isinstance(item, StructLiteralNode):
            for field in item.fields:
                visit(field.expression)
            return
        if isinstance(item, (ArrayLiteralNode, TupleLiteralNode, SetLiteralNode)):
            for element in item.elements:
                visit(element)
            return
        if isinstance(item, MapLiteralNode):
            for entry in item.entries:
                visit(entry.key)
                visit(entry.value)
            return
        if isinstance(item, IndexAccessNode):
            visit(item.collection)
            visit(item.index)
            return
        if isinstance(item, SomeExpressionNode):
            visit(item.value)

    visit(value)
    return found


def _walk_runtime_calls(value: Any):
    if isinstance(value, RuntimeCallExpressionNode):
        yield value
        for argument in value.arguments:
            yield from _walk_runtime_calls(argument)
        return
    if isinstance(value, tuple):
        for item in value:
            yield from _walk_runtime_calls(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from _walk_runtime_calls(item)
        return
    if hasattr(value, "__dataclass_fields__"):
        for field in value.__dataclass_fields__:
            yield from _walk_runtime_calls(getattr(value, field))


def compile_program(program: ProgramNode) -> tuple[dict[str, Any], ...]:
    return tuple(compile_semantic(module) for module in project_program(program))


def execution_plan_for(reason_ir: dict[str, Any]) -> dict[str, Any]:
    steps = [
        {
            "step_id": f"step-{index}",
            "transition_id": transition["transition_id"],
            "source": transition["source"],
            "target": transition["target"],
        }
        for index, transition in enumerate(reason_ir["transitions"], 1)
    ]
    return {
        "selected_steps": steps,
        "alternative_paths": [],
        "expected_cost": sum(
            transition["expected_cost"] for transition in reason_ir["transitions"]
        ),
        "evidence_refs": [],
        "planner_version": "language-surface-validation/0.1",
    }


def _expression_relation(expression: ExpressionNode) -> str:
    value = expression.expression
    if isinstance(value, BinaryExpressionNode):
        return {
            BinaryOperator.ADD: "AddTransition",
            BinaryOperator.SUBTRACT: "SubtractTransition",
            BinaryOperator.MULTIPLY: "MultiplyTransition",
            BinaryOperator.DIVIDE: "DivideTransition",
            BinaryOperator.MODULO: "ModuloTransition",
        }[value.operator]
    if isinstance(value, ComparisonExpressionNode):
        return "CompareTransition"
    if isinstance(value, LogicalExpressionNode):
        return "LogicalTransition"
    if isinstance(value, UnaryExpressionNode):
        return "UnaryTransition"
    if isinstance(value, MemberAccessNode):
        return "MemberAccessTransition"
    if isinstance(value, IndexAccessNode):
        return "IndexAccessTransition"
    if isinstance(value, StructLiteralNode):
        return "StructLiteralTransition"
    if isinstance(value, ArrayLiteralNode):
        return "ArrayTransition"
    if isinstance(value, TupleLiteralNode):
        return "TupleTransition"
    if isinstance(value, SetLiteralNode):
        return "SetTransition"
    if isinstance(value, MapLiteralNode):
        return "MapTransition"
    if isinstance(value, SomeExpressionNode):
        return "SomeTransition"
    if isinstance(value, NoneLiteralNode):
        return "NoneTransition"
    if isinstance(value, CallExpressionNode):
        return "CallTransition"
    if isinstance(value, RuntimeCallExpressionNode):
        return {
            RuntimeCallKind.INPUT: "InputOperation",
            RuntimeCallKind.PRINT: "PrintOperation",
            RuntimeCallKind.SEARCH: "RuntimeSearchOperation",
            RuntimeCallKind.SIMULATION: "RuntimeSimulateOperation",
            RuntimeCallKind.PREDICTION: "RuntimePredictOperation",
            RuntimeCallKind.PLANNING: "RuntimePlanOperation",
        }[value.kind]
    return "ExpressionTransition"


def _runtime_source_state(argument: Any) -> str:
    if isinstance(argument, IdentifierNode):
        return argument.name
    if isinstance(argument, QualifiedIdentifierNode):
        return "::".join((*argument.path, argument.symbol))
    return str(to_json_value(argument))


def _statement_projection(
    statement: Any, index: int
) -> tuple[str, dict[str, Any], str]:
    if isinstance(statement, LetStatementNode):
        return (
            statement.identifier,
            to_json_value(statement),
            _expression_relation(statement.expression),
        )
    if isinstance(statement, ConstStatementNode):
        return (
            statement.identifier,
            to_json_value(statement),
            _expression_relation(statement.expression),
        )
    if isinstance(statement, AssignmentStatementNode):
        return (
            statement.target,
            to_json_value(statement),
            "StateUpdateTransition",
        )
    if isinstance(statement, FieldAssignmentStatementNode):
        return (
            "field_assignment",
            to_json_value(statement),
            "FieldAssignmentTransition",
        )
    if isinstance(statement, IndexAssignmentStatementNode):
        return (
            "index_assignment",
            to_json_value(statement),
            "IndexAssignmentTransition",
        )
    if isinstance(statement, ResultStatementNode):
        return (
            "result",
            to_json_value(statement),
            "ResultTransition",
        )
    if isinstance(statement, ReturnStatementNode):
        return (
            "return",
            to_json_value(statement),
            "ReturnTransition",
        )
    if isinstance(statement, ExpressionStatementNode):
        return (
            f"expression_{index}",
            to_json_value(statement),
            "CallTransition",
        )
    if isinstance(statement, ForStatementNode):
        return (f"for_{index}", to_json_value(statement), "ForTransition")
    if isinstance(statement, WhileStatementNode):
        return (f"while_{index}", to_json_value(statement), "WhileTransition")
    if isinstance(statement, LoopStatementNode):
        return (f"loop_{index}", to_json_value(statement), "LoopTransition")
    if isinstance(statement, BreakStatementNode):
        return (f"break_{index}", to_json_value(statement), "BreakTransition")
    if isinstance(statement, ContinueStatementNode):
        return (f"continue_{index}", to_json_value(statement), "ContinueTransition")
    if isinstance(statement, IfStatementNode):
        return (f"if_{index}", to_json_value(statement), "DecisionTransition")
    return (
        f"match_{index}",
        to_json_value(statement),
        "DecisionTransition",
    )


def _terminates_with_result(statement: Any) -> bool:
    if isinstance(statement, ResultStatementNode):
        return True
    if isinstance(statement, IfStatementNode):
        if statement.else_branch is None:
            return False
        branches = [statement.body]
        branches.extend(branch.body for branch in statement.elif_branches)
        branches.append(statement.else_branch.body)
        return all(
            body and _terminates_with_result(body[-1]) for body in branches
        )
    if hasattr(statement, "arms"):
        return bool(statement.arms) and all(
            arm.body and _terminates_with_result(arm.body[-1])
            for arm in statement.arms
        )
    return False
