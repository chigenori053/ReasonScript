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
    BooleanLiteralNode,
    BreakStatementNode,
    CallExpressionNode,
    ComparisonExpressionNode,
    ComparisonOperator,
    ConstDeclarationNode,
    ConstStatementNode,
    ContinueStatementNode,
    DefaultPatternNode,
    EnumDeclarationNode,
    EnumValuePatternNode,
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
    IdentifierPatternNode,
    ImportNode,
    IfStatementNode,
    IndexAccessNode,
    IndexAssignmentStatementNode,
    IntegerLiteralNode,
    FloatLiteralNode,
    LetStatementNode,
    LiteralPatternNode,
    LogicalExpressionNode,
    LoopStatementNode,
    MapLiteralNode,
    MatchStatementNode,
    MemberAccessNode,
    NamedTypeNode,
    NoneLiteralNode,
    ModuleNode,
    PatternNode,
    ParenthesizedExpressionNode,
    ProgramNode,
    QualifiedPatternNode,
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
    StringLiteralNode,
    StateDeclarationNode,
    StructDeclarationNode,
    StructLiteralNode,
    TransitionNode,
    TupleLiteralNode,
    UnaryExpressionNode,
    Visibility,
    WhileStatementNode,
    WildcardPatternNode,
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
    function_call_dependencies = _function_call_dependencies(module)
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
                "semantic_functions": _semantic_function_nodes(module, namespace),
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
                f"{namespace}-semantic-functions",
                "semantic_functions",
                _semantic_function_nodes(module, namespace),
            ),
            semantic.MetadataNode(
                f"{namespace}-function-symbols",
                "function_symbols",
                _function_symbols(module, namespace),
            ),
            semantic.MetadataNode(
                f"{namespace}-function-ir",
                "function_ir",
                _function_ir_nodes(module, namespace),
            ),
            semantic.MetadataNode(
                f"{namespace}-function-calls",
                "function_calls",
                _function_call_ir_nodes(module, namespace),
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
                f"{namespace}-enum-symbols",
                "enum_symbols",
                _enum_symbols(module),
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
                ]
                + [
                    {"source": source, "target": target}
                    for target in sorted(function_call_dependencies)
                    for source in sorted(function_call_dependencies[target])
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
    functions = {
        node.name: node for node in module.body if isinstance(node, FunctionDeclarationNode)
    }
    emitted_function_returns: set[str] = set()
    for node in calculations:
        local_names: set[str] = set()
        current_sources = [current]
        for index, statement in enumerate(node.body, 1):
            identifier, statement_data, relation = _statement_projection(
                statement, index
            )
            expression = _statement_expression(statement)
            for function_name in _expression_function_calls(expression):
                function = functions.get(function_name)
                if function is None or function_name in emitted_function_returns:
                    continue
                return_paths = _function_return_paths(function, module)
                arguments = _function_call_arguments(expression, function_name)
                evaluation_context = _function_evaluation_context(function, arguments)
                next_sources: list[str] = []
                for source in current_sources:
                    for return_path in return_paths:
                        transition_index += 1
                        target = _function_return_target(function_name, return_path["label"])
                        declarations.append(
                            semantic.TransitionNode(
                                f"{namespace}-function-{transition_index}",
                                target,
                                source,
                                "FunctionReturnTransition",
                                target,
                                effect={
                                    "function": f"{namespace}.{function_name}",
                                    "node_type": "FunctionIRNode",
                                    "return_path": return_path["label"],
                                    "return": to_json_value(return_path["expression"]),
                                    "return_value": _ir_value(return_path["expression"]),
                                    "branch_conditions": return_path.get("branch_conditions", []),
                                    "match_conditions": return_path.get("match_conditions", []),
                                    "evaluation_context": evaluation_context,
                                },
                            )
                        )
                        next_sources.append(target)
                current_sources = next_sources or current_sources
                emitted_function_returns.add(function_name)
            if isinstance(statement, (LetStatementNode, ConstStatementNode)):
                local_names.add(statement.identifier)
            if _terminates_with_result(statement):
                identifier = "result"
            target = (
                f"{node.name}.state.result"
                if identifier == "result"
                else f"{node.name}.state.{identifier}"
            )
            for source in current_sources:
                transition_index += 1
                declarations.append(
                    semantic.TransitionNode(
                        f"{namespace}-calculation-{transition_index}",
                        f"{node.name}-{index}-{identifier}-{transition_index}",
                        source,
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
                            "function_calls": [
                                {
                                    "node_type": "FunctionCallIRNode",
                                    "function": f"{namespace}.{function_name}",
                                    "arguments": [
                                        to_json_value(argument)
                                        for argument in _function_call_arguments(expression, function_name)
                                    ],
                                    "return_type": _type_label(
                                        functions[function_name].return_type
                                        if function_name in functions
                                        else None
                                    ),
                                }
                                for function_name in _expression_function_calls(expression)
                            ],
                            **(
                                {"expression": statement_data["expression"]}
                                if "expression" in statement_data
                                else {}
                            ),
                        },
                    )
                )
            current = target
            current_sources = [target]
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


def _function_symbols(module: ModuleNode, namespace: str) -> list[dict[str, Any]]:
    return [
        {
            "node_type": "FunctionSymbol",
            "name": node.name,
            "qualified_name": f"{namespace}.{node.name}",
            "parameters": [
                {
                    "name": _function_parameter_name(parameter),
                    "type": _type_label(_function_parameter_type(parameter)),
                }
                for parameter in node.parameters
            ],
            "return_type": _type_label(node.return_type),
        }
        for node in module.body
        if isinstance(node, FunctionDeclarationNode)
    ]


def _semantic_function_nodes(module: ModuleNode, namespace: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for node in module.body:
        if not isinstance(node, FunctionDeclarationNode):
            continue
        return_paths = _function_return_paths(node, module)
        result.append(
            {
                "node_type": "SemanticFunctionNode",
                "name": node.name,
                "qualified_name": f"{namespace}.{node.name}",
                "parameters": [
                    {
                        "name": _function_parameter_name(parameter),
                        "type": _type_label(_function_parameter_type(parameter)),
                    }
                    for parameter in node.parameters
                ],
                "return_type": _type_label(node.return_type),
                "body_type": (
                    _type_label(node.return_type) if return_paths else None
                ),
                "return_guaranteed": bool(return_paths),
                "return_paths": [path["label"] for path in return_paths],
                "pure": True,
            }
        )
    return result


def _function_ir_nodes(module: ModuleNode, namespace: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for node in module.body:
        if not isinstance(node, FunctionDeclarationNode):
            continue
        result.append(
            {
                "node_type": "FunctionIRNode",
                "id": f"{namespace}.{node.name}",
                "name": node.name,
                "return_type": _type_label(node.return_type),
                "pure": True,
                "parameters": [
                    {
                        "name": _function_parameter_name(parameter),
                        "type": _type_label(_function_parameter_type(parameter)),
                    }
                    for parameter in node.parameters
                ],
                "body": _function_control_flow_ir(node, module),
            }
        )
    return result


def _function_call_ir_nodes(module: ModuleNode, namespace: str) -> list[dict[str, Any]]:
    functions = {
        node.name: node for node in module.body if isinstance(node, FunctionDeclarationNode)
    }
    result: list[dict[str, Any]] = []
    for calculation in [node for node in module.body if isinstance(node, CalculationNode)]:
        for statement in calculation.body:
            expression = _statement_expression(statement)
            for function_name in _expression_function_calls(expression):
                function = functions.get(function_name)
                result.append(
                    {
                        "node_type": "FunctionCallIRNode",
                        "function": f"{namespace}.{function_name}",
                        "caller": calculation.name,
                        "arguments": [
                            _ir_value(argument)
                            for argument in _function_call_arguments(expression, function_name)
                        ],
                        "return_type": _type_label(
                            function.return_type if function is not None else None
                        ),
                    }
                )
    return result


def _function_call_dependencies(module: ModuleNode) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    functions = {
        node.name for node in module.body if isinstance(node, FunctionDeclarationNode)
    }
    for calculation in [node for node in module.body if isinstance(node, CalculationNode)]:
        dependencies: set[str] = set()
        for statement in calculation.body:
            dependencies.update(
                name
                for name in _expression_function_calls(_statement_expression(statement))
                if name in functions
            )
        result[calculation.name] = dependencies
    return result


def _function_parameter_name(parameter: Any) -> str:
    if isinstance(parameter, dict):
        return str(parameter.get("name", ""))
    return str(parameter)


def _function_parameter_type(parameter: Any) -> Any:
    if isinstance(parameter, dict):
        return parameter.get("type")
    return None


def _function_return_statement(function: FunctionDeclarationNode) -> ReturnStatementNode | None:
    for statement in reversed(function.body):
        if isinstance(statement, ReturnStatementNode):
            return statement
    return None


def _function_return_paths(
    function: FunctionDeclarationNode,
    module: ModuleNode | None = None,
) -> list[dict[str, Any]]:
    paths: list[dict[str, Any]] = []
    named_labels = _has_nested_if(function.body)

    def walk(
        statements: tuple[Any, ...],
        prefixes: list[tuple[str, ...]],
        branch_conditions: list[tuple[dict[str, Any], ...]],
        match_conditions: list[tuple[dict[str, Any], ...]],
    ) -> list[tuple[tuple[str, ...], tuple[dict[str, Any], ...]]]:
        active = prefixes
        active_conditions = branch_conditions
        active_match_conditions = match_conditions
        for statement in statements:
            if not active:
                return []
            if isinstance(statement, ReturnStatementNode):
                for prefix, conditions, matches in zip(
                    active,
                    active_conditions,
                    active_match_conditions,
                ):
                    paths.append(
                        {
                            "label": _return_path_label(prefix, len(paths) + 1),
                            "expression": statement.expression,
                            "branch_conditions": list(conditions),
                            "match_conditions": list(matches),
                        }
                    )
                return []
            if isinstance(statement, IfStatementNode):
                next_active: list[tuple[str, ...]] = []
                next_conditions: list[tuple[dict[str, Any], ...]] = []
                next_match_conditions: list[tuple[dict[str, Any], ...]] = []
                branches = [(True, statement.condition, statement.body)]
                branches.extend(
                    (True, branch.condition, branch.body)
                    for index, branch in enumerate(statement.elif_branches, 1)
                )
                for prefix, conditions, matches in zip(
                    active,
                    active_conditions,
                    active_match_conditions,
                ):
                    for branch_value, condition, body in branches:
                        label = _branch_label(condition, branch_value, named_labels)
                        branch_prefix = (*prefix, label)
                        branch_condition = _branch_condition(condition, branch_value)
                        if walk(
                            body,
                            [branch_prefix],
                            [(*conditions, branch_condition)],
                            [matches],
                        ):
                            next_active.append(branch_prefix)
                            next_conditions.append((*conditions, branch_condition))
                            next_match_conditions.append(matches)
                    if statement.else_branch is not None:
                        else_label = _branch_label(statement.condition, False, named_labels)
                        else_prefix = (*prefix, else_label)
                        branch_condition = _branch_condition(statement.condition, False)
                        if walk(
                            statement.else_branch.body,
                            [else_prefix],
                            [(*conditions, branch_condition)],
                            [matches],
                        ):
                            next_active.append(else_prefix)
                            next_conditions.append((*conditions, branch_condition))
                            next_match_conditions.append(matches)
                    else:
                        branch_condition = _branch_condition(statement.condition, False)
                        next_active.append((*prefix, _branch_label(statement.condition, False, named_labels)))
                        next_conditions.append((*conditions, branch_condition))
                        next_match_conditions.append(matches)
                active = next_active
                active_conditions = next_conditions
                active_match_conditions = next_match_conditions
                continue
            if isinstance(statement, MatchStatementNode):
                enum = _match_enum_declaration(statement, function, module) if module is not None else None
                next_active = []
                next_conditions = []
                next_match_conditions = []
                for prefix, conditions, matches in zip(
                    active,
                    active_conditions,
                    active_match_conditions,
                ):
                    for arm in statement.arms:
                        label = _match_case_label(arm.pattern, enum)
                        branch_prefix = (*prefix, label)
                        match_condition = _match_condition(statement, arm, label, enum)
                        if walk(
                            arm.body,
                            [branch_prefix],
                            [conditions],
                            [(*matches, match_condition)],
                        ):
                            next_active.append(branch_prefix)
                            next_conditions.append(conditions)
                            next_match_conditions.append((*matches, match_condition))
                active = next_active
                active_conditions = next_conditions
                active_match_conditions = next_match_conditions
                continue
        return list(zip(active, active_conditions))

    walk(function.body, [()], [()], [()])
    return paths


def _return_path_label(prefix: tuple[str, ...], index: int) -> str:
    if not prefix:
        return f"path_{index}"
    if all(not item.endswith(("_true", "_false")) for item in prefix):
        return "_and_".join(prefix)
    separator = "_" if any("_" in item for item in prefix) else "."
    return separator.join(prefix)


def _function_return_target(function_name: str, label: str) -> str:
    if label.startswith("match."):
        return f"{function_name}.{label}"
    return f"{function_name}.return" if label == "path_1" else f"{function_name}.return.{label}"


def _function_control_flow_ir(
    function: FunctionDeclarationNode,
    module: ModuleNode,
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    return_targets = {
        path["label"]: _function_return_target(function.name, path["label"])
        for path in _function_return_paths(function, module)
    }
    named_labels = _has_nested_if(function.body)

    def add_branch_nodes(statements: tuple[Any, ...], prefix: tuple[str, ...] = ()) -> None:
        for statement in statements:
            if isinstance(statement, MatchStatementNode):
                coverage = _match_coverage(statement, function, module)
                enum = _match_enum_declaration(statement, function, module)
                nodes.append(
                    {
                        "node_type": "MatchExpressionIRNode",
                        "value": _match_value_name(statement.expression),
                        "expression": to_json_value(statement.expression),
                        "cases": [
                            {
                                "node_type": "MatchCaseIRNode",
                                "pattern": _match_pattern_value(arm.pattern, enum),
                                "target": _function_return_target(
                                    function.name,
                                    _return_path_label(
                                        (*prefix, _match_case_label(arm.pattern, enum)),
                                        1,
                                    ),
                                ),
                            }
                            for arm in statement.arms
                        ],
                        **({"coverage": coverage} if coverage is not None else {}),
                    }
                )
                nodes.append(
                    {
                        "node_type": "PatternDecisionNode",
                        "input": _match_value_name(statement.expression),
                        "expression": to_json_value(statement.expression),
                        "arms": [
                            {
                                "branch_index": index,
                                "pattern": _pattern_decision_value(arm.pattern, enum),
                                "target_transition": _function_return_target(
                                    function.name,
                                    _return_path_label(
                                        (*prefix, _match_case_label(arm.pattern, enum)),
                                        1,
                                    ),
                                ),
                            }
                            for index, arm in enumerate(statement.arms)
                        ],
                        "selected_arm": None,
                    }
                )
                for arm in statement.arms:
                    label = _return_path_label(
                        (*prefix, _match_case_label(arm.pattern, enum)),
                        1,
                    )
                    nodes.append(
                        {
                            "node_type": "MatchSelectionIRNode",
                            "value": _match_value_name(statement.expression),
                            "pattern": _match_pattern_value(arm.pattern, enum),
                            "target": _function_return_target(function.name, label),
                        }
                    )
                    add_branch_nodes(
                        arm.body,
                        (*prefix, _match_case_label(arm.pattern, enum)),
                    )
                continue
            if not isinstance(statement, IfStatementNode):
                continue
            true_prefix = (*prefix, _branch_label(statement.condition, True, named_labels))
            false_prefix = (*prefix, _branch_label(statement.condition, False, named_labels))
            true_label = _first_return_label(statement.body, _return_path_label(true_prefix, 1))
            false_label = (
                _first_return_label(statement.else_branch.body, _return_path_label(false_prefix, 1))
                if statement.else_branch is not None
                else _return_path_label(false_prefix, 1)
            )
            nodes.append(
                {
                    "node_type": "ConditionalBranchIRNode",
                    "condition": to_json_value(statement.condition),
                    "condition_type": "Bool",
                    "true_target": return_targets.get(
                        true_label, _function_return_target(function.name, true_label)
                    ),
                    "false_target": return_targets.get(false_label, "fallthrough"),
                }
            )
            add_branch_nodes(statement.body, true_prefix)
            if statement.else_branch is not None:
                add_branch_nodes(statement.else_branch.body, false_prefix)

    add_branch_nodes(function.body)
    for path in _function_return_paths(function, module):
        nodes.append(
            {
                "node_type": "ReturnIRNode",
                "id": _function_return_target(function.name, path["label"]),
                "path": path["label"],
                "expression": to_json_value(path["expression"]),
                "return_value": _ir_value(path["expression"]),
                **(
                    {"semantic_reference": _enum_variant_reference(path["expression"].expression)}
                    if isinstance(path["expression"], ExpressionNode)
                    and _enum_variant_reference(path["expression"].expression) is not None
                    else {}
                ),
            }
        )
    if any(isinstance(statement, (IfStatementNode, MatchStatementNode)) for statement in function.body):
        nodes.append({"node_type": "MergeIRNode", "id": f"{function.name}.merge.return"})
    return nodes


def _first_return_label(statements: tuple[Any, ...], default: str) -> str:
    for statement in statements:
        if isinstance(statement, ReturnStatementNode):
            return default
    return default


def _has_nested_if(statements: tuple[Any, ...], *, inside_if: bool = False) -> bool:
    for statement in statements:
        if not isinstance(statement, IfStatementNode):
            continue
        if inside_if:
            return True
        if _has_nested_if(statement.body, inside_if=True):
            return True
        if statement.else_branch is not None and _has_nested_if(
            statement.else_branch.body,
            inside_if=True,
        ):
            return True
    return False


def _branch_label(condition: ExpressionNode, value: bool, named_labels: bool) -> str:
    suffix = "true" if value else "false"
    if not named_labels:
        return suffix
    name = _condition_name(condition)
    if name and _is_comparison_condition(condition):
        return name if value else f"not_{name}"
    return f"{name}_{suffix}" if name else suffix


def _branch_condition(condition: ExpressionNode, expected_value: bool) -> dict[str, Any]:
    result = {
        "condition": _condition_name(condition) or _condition_literal_name(condition),
        "condition_type": "Bool",
        "expected_value": expected_value,
        "expression": to_json_value(condition),
    }
    comparison = _comparison_ir(condition)
    if comparison is not None:
        result["comparison"] = comparison
    return result


def _match_condition(
    statement: MatchStatementNode,
    arm: Any,
    label: str,
    enum: EnumDeclarationNode | None = None,
) -> dict[str, Any]:
    return {
        "node_type": "MatchSelectionIRNode",
        "value": _match_value_name(statement.expression),
        "expression": to_json_value(statement.expression),
        "pattern": _match_pattern_value(arm.pattern, enum),
        "target": label,
    }


def _match_value_name(expression: ExpressionNode) -> str:
    value = expression.expression
    if isinstance(value, IdentifierNode):
        return value.name
    return _condition_operand_name(_comparison_operand(expression))


def _match_case_label(
    pattern: PatternNode,
    enum: EnumDeclarationNode | None = None,
) -> str:
    return f"match.{_match_pattern_label(pattern, enum)}"


def _match_pattern_label(
    pattern: PatternNode,
    enum: EnumDeclarationNode | None = None,
) -> str:
    value = _match_pattern_value(pattern, enum)
    if value == "default":
        return "default"
    if isinstance(value, bool):
        return "true" if value else "false"
    if _is_enum_value_pattern(value):
        return f"{value['enum_name']}.{value['value_name']}"
    return str(value).replace("-", "neg_").replace(".", "_")


def _match_pattern_value(
    pattern: PatternNode,
    enum: EnumDeclarationNode | None = None,
) -> Any:
    value = pattern.pattern
    if isinstance(value, WildcardPatternNode):
        return "wildcard"
    if isinstance(value, DefaultPatternNode) or (
        isinstance(value, IdentifierPatternNode) and value.name == "default"
    ):
        return "default"
    if isinstance(value, LiteralPatternNode):
        literal = value.value
        if isinstance(literal, (BooleanLiteralNode, IntegerLiteralNode, FloatLiteralNode)):
            return literal.value
        if isinstance(literal, StringLiteralNode):
            return literal.value
    if isinstance(value, QualifiedPatternNode):
        return {
            "node_type": "EnumValuePatternNode",
            "enum_name": value.namespace,
            "value_name": value.identifier,
        }
    if isinstance(value, EnumValuePatternNode):
        return {
            "node_type": "EnumValuePatternNode",
            "enum_name": value.enum_name,
            "value_name": value.value_name,
        }
    return to_json_value(pattern)


def _pattern_decision_value(
    pattern: PatternNode,
    enum: EnumDeclarationNode | None = None,
) -> Any:
    value = pattern.pattern
    if isinstance(value, QualifiedPatternNode):
        return {
            "node_type": "EnumVariantReferenceNode",
            "enum": value.namespace,
            "variant": value.identifier,
            "symbol_id": f"{value.namespace}.{value.identifier}",
        }
    return _match_pattern_value(pattern, enum)


def _match_coverage(
    statement: MatchStatementNode,
    function: FunctionDeclarationNode,
    module: ModuleNode,
) -> dict[str, Any] | None:
    enum = _match_enum_declaration(statement, function, module)
    if enum is None:
        return None
    explicit: list[str] = []
    for arm in statement.arms:
        pattern = arm.pattern.pattern
        if isinstance(pattern, EnumValuePatternNode) and pattern.enum_name == enum.name:
            explicit.append(f"{pattern.enum_name}.{pattern.value_name}")
        elif isinstance(pattern, QualifiedPatternNode) and pattern.namespace == enum.name:
            explicit.append(f"{pattern.namespace}.{pattern.identifier}")
    default_present = any(
        _pattern_key in {"default", "wildcard"}
        for _pattern_key in (_match_pattern_kind(arm.pattern) for arm in statement.arms)
    )
    all_variants = [f"{enum.name}.{value.name}" for value in enum.values]
    covered = all_variants if default_present else [item for item in all_variants if item in explicit]
    return {
        "enum_name": enum.name,
        "explicit_variants": explicit,
        "default_present": default_present,
        "covered_variants": covered,
        "missing_variants": [item for item in all_variants if item not in covered],
    }


def _match_enum_declaration(
    statement: MatchStatementNode,
    function: FunctionDeclarationNode,
    module: ModuleNode,
) -> EnumDeclarationNode | None:
    expression = statement.expression.expression
    if not isinstance(expression, IdentifierNode):
        return None
    parameter_type = None
    for parameter in function.parameters:
        if _function_parameter_name(parameter) == expression.name:
            parameter_type = _function_parameter_type(parameter)
            break
    if not isinstance(parameter_type, NamedTypeNode):
        return None
    for node in module.body:
        if isinstance(node, EnumDeclarationNode) and node.name == parameter_type.name:
            return node
    return None


def _match_pattern_kind(pattern: PatternNode) -> str:
    value = pattern.pattern
    if isinstance(value, WildcardPatternNode):
        return "wildcard"
    if isinstance(value, DefaultPatternNode) or (
        isinstance(value, IdentifierPatternNode) and value.name == "default"
    ):
        return "default"
    return "pattern"


def _is_enum_value_pattern(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("node_type") == "EnumValuePatternNode"
        and isinstance(value.get("enum_name"), str)
        and isinstance(value.get("value_name"), str)
    )


def _condition_name(condition: ExpressionNode) -> str | None:
    expression = condition.expression
    if isinstance(expression, IdentifierNode):
        return expression.name
    if isinstance(expression, ParenthesizedExpressionNode) and isinstance(
        expression.expression,
        IdentifierNode,
    ):
        return expression.expression.name
    comparison = _comparison_ir(condition)
    if comparison is not None:
        return _comparison_condition_name(comparison)
    return None


def _condition_literal_name(condition: ExpressionNode) -> str:
    expression = condition.expression
    if isinstance(expression, BooleanLiteralNode):
        return "true" if expression.value else "false"
    return "<unsupported>"


_COMPARISON_OPERATOR_SYMBOLS = {
    ComparisonOperator.EQUAL: "==",
    ComparisonOperator.NOT_EQUAL: "!=",
    ComparisonOperator.GREATER_THAN: ">",
    ComparisonOperator.GREATER_THAN_OR_EQUAL: ">=",
    ComparisonOperator.LESS_THAN: "<",
    ComparisonOperator.LESS_THAN_OR_EQUAL: "<=",
}


_COMPARISON_OPERATOR_NAMES = {
    "==": "eq",
    "!=": "ne",
    ">": "gt",
    ">=": "gte",
    "<": "lt",
    "<=": "lte",
}


def _is_comparison_condition(condition: ExpressionNode) -> bool:
    return _comparison_ir(condition) is not None


def _comparison_ir(condition: ExpressionNode) -> dict[str, Any] | None:
    value = condition.expression
    if isinstance(value, ParenthesizedExpressionNode):
        value = value.expression.expression
    if not isinstance(value, ComparisonExpressionNode):
        return None
    return {
        "node_type": "ComparisonExpressionIRNode",
        "operator": _COMPARISON_OPERATOR_SYMBOLS[value.operator],
        "left": _comparison_operand(value.left),
        "right": _comparison_operand(value.right),
        "result_type": "Bool",
    }


def _comparison_operand(expression: ExpressionNode) -> Any:
    value = expression.expression if isinstance(expression, ExpressionNode) else expression
    if isinstance(value, IdentifierNode):
        return value.name
    if isinstance(value, BooleanLiteralNode):
        return value.value
    if value.__class__.__name__ in {"IntegerLiteralNode", "FloatLiteralNode"}:
        return value.value
    return to_json_value(expression)


def _comparison_condition_name(comparison: dict[str, Any]) -> str:
    left = _condition_operand_name(comparison.get("left"))
    right = _condition_operand_name(comparison.get("right"))
    operator = _COMPARISON_OPERATOR_NAMES.get(str(comparison.get("operator")), "cmp")
    return f"{left}_{operator}_{right}"


def _condition_operand_name(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value).replace("-", "neg_").replace(".", "_")
    if isinstance(value, str):
        return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_") or "value"
    return "value"


def _function_evaluation_context(
    function: FunctionDeclarationNode,
    arguments: tuple[Any, ...],
) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for parameter, argument in zip(function.parameters, arguments):
        context[_function_parameter_name(parameter)] = _literal_value(argument)
    return context


def _literal_value(expression: Any) -> Any:
    value = expression.expression if isinstance(expression, ExpressionNode) else expression
    if isinstance(value, BooleanLiteralNode):
        return value.value
    if value.__class__.__name__ == "IntegerLiteralNode":
        return value.value
    if value.__class__.__name__ == "FloatLiteralNode":
        return value.value
    enum_value = _enum_variant_ir(value)
    if enum_value is not None:
        return {
            "enum": enum_value["enum_name"],
            "variant": enum_value["variant_name"],
        }
    return to_json_value(expression)


def _ir_value(expression: Any) -> Any:
    value = expression.expression if isinstance(expression, ExpressionNode) else expression
    enum_value = _enum_variant_ir(value)
    if enum_value is not None:
        return enum_value
    return to_json_value(expression)


def _enum_variant_ir(value: Any) -> dict[str, Any] | None:
    if isinstance(value, MemberAccessNode) and isinstance(value.object, IdentifierNode):
        return {
            "node_type": "EnumVariantIRNode",
            "enum_name": value.object.name,
            "variant_name": value.member,
        }
    if isinstance(value, EnumValuePatternNode):
        return {
            "node_type": "EnumVariantIRNode",
            "enum_name": value.enum_name,
            "variant_name": value.value_name,
        }
    return None


def _enum_variant_reference(value: Any) -> dict[str, Any] | None:
    enum_value = _enum_variant_ir(value)
    if enum_value is None:
        return None
    return {
        "node_type": "EnumVariantReferenceNode",
        "enum_name": enum_value["enum_name"],
        "variant_name": enum_value["variant_name"],
        "qualified_name": f"{enum_value['enum_name']}.{enum_value['variant_name']}",
    }


def _enum_symbols(module: ModuleNode) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for node in module.body:
        if not isinstance(node, EnumDeclarationNode):
            continue
        result.append(
            {
                "symbol_type": "EnumSymbol",
                "enum_name": node.name,
                "qualified_name": node.name,
            }
        )
        for value in node.values:
            result.append(
                {
                    "symbol_type": "EnumVariantSymbol",
                    "enum_name": node.name,
                    "variant_name": value.name,
                    "qualified_name": f"{node.name}.{value.name}",
                }
            )
    return result


def _type_label(value: Any) -> str | None:
    if value is None:
        return None
    encoded = to_json_value(value)
    if isinstance(encoded, dict):
        if encoded.get("node_type") == "PrimitiveTypeNode":
            return str(encoded.get("kind", "")).lower()
        if encoded.get("node_type") == "NamedTypeNode":
            return str(encoded.get("name"))
    return str(encoded)


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


def _expression_function_calls(expression: ExpressionNode | Any | None) -> list[str]:
    if expression is None:
        return []
    value = expression.expression if isinstance(expression, ExpressionNode) else expression
    found: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, CallExpressionNode):
            if isinstance(item.callee, IdentifierNode) and item.callee.name not in found:
                found.append(item.callee.name)
            visit(item.callee)
            for argument in item.arguments:
                visit(argument)
            return
        if isinstance(item, ExpressionNode):
            visit(item.expression)
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


def _function_call_arguments(
    expression: ExpressionNode | Any | None,
    function_name: str,
) -> list[ExpressionNode]:
    if expression is None:
        return []
    value = expression.expression if isinstance(expression, ExpressionNode) else expression
    found: list[ExpressionNode] = []

    def visit(item: Any) -> None:
        if isinstance(item, CallExpressionNode):
            if isinstance(item.callee, IdentifierNode) and item.callee.name == function_name:
                found.extend(item.arguments)
            for argument in item.arguments:
                visit(argument)
            return
        if isinstance(item, ExpressionNode):
            visit(item.expression)
            return
        if isinstance(item, (UnaryExpressionNode, ParenthesizedExpressionNode, SomeExpressionNode)):
            visit(getattr(item, "operand", getattr(item, "expression", getattr(item, "value", None))))
            return
        if isinstance(item, (BinaryExpressionNode, ComparisonExpressionNode, LogicalExpressionNode)):
            visit(item.left)
            visit(item.right)
            return
        if isinstance(item, MemberAccessNode):
            visit(item.object)
            return
        if isinstance(item, RuntimeCallExpressionNode):
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
