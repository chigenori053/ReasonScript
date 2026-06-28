"""Validation rules AST-V001 through AST-V007."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, fields, is_dataclass
from typing import Any

from .expressions import MAX_PATTERN_DEPTH, ExpressionSyntaxError, parse_expression
from .nodes import (
    ActionNode,
    ArrayLiteralNode,
    ArrayTypeNode,
    AssignmentStatementNode,
    AttributeNode,
    BreakStatementNode,
    CalculationNode,
    BinaryExpressionNode,
    BinaryOperator,
    BooleanLiteralNode,
    CallExpressionNode,
    ComparisonExpressionNode,
    ComparisonOperator,
    ConceptNode,
    ConstraintNode,
    ConstDeclarationNode,
    ConstStatementNode,
    ContinueStatementNode,
    DefaultPatternNode,
    EnumDeclarationNode,
    EnumValueNode,
    EnumValuePatternNode,
    ElseIfStatementNode,
    ElseStatementNode,
    EventNode,
    ExecutionPlanDeclarationNode,
    ExpressionStatementNode,
    ExpressionNode,
    FieldAssignmentStatementNode,
    FloatLiteralNode,
    ForStatementNode,
    FunctionDeclarationNode,
    GoalNode,
    GoalStatementNode,
    IfStatementNode,
    IdentifierNode,
    IdentifierPatternNode,
    ImportNode,
    ImportResolutionNode,
    IndexAccessNode,
    IndexAssignmentStatementNode,
    IntegerLiteralNode,
    LetStatementNode,
    LiteralPatternNode,
    LogicalExpressionNode,
    LoopStatementNode,
    LogicalOperator,
    MapEntryNode,
    MapLiteralNode,
    MapTypeNode,
    MatchArmNode,
    MatchStatementNode,
    MemberAccessNode,
    ModuleNode,
    NamedTypeNode,
    NoneLiteralNode,
    ObjectNode,
    OptionalPatternNode,
    OptionalValuePatternNode,
    OptionalTypeNode,
    OrPatternNode,
    NullLiteralNode,
    PackageDeclarationNode,
    ParenthesizedExpressionNode,
    PatternNode,
    PlanStepNode,
    PrimitiveKind,
    PrimitiveTypeNode,
    ProgramNode,
    QualifiedPatternNode,
    QualifiedIdentifierNode,
    ReachStatementNode,
    ReasonGraphDeclarationNode,
    ReasonGraphTransitionNode,
    RelationNode,
    RelationType,
    RequireStatementNode,
    ResultStatementNode,
    ReturnStatementNode,
    RuntimeCallExpressionNode,
    RuntimeCallKind,
    RuntimeNamespaceNode,
    SetLiteralNode,
    SetTypeNode,
    SomeExpressionNode,
    StringLiteralNode,
    StateDeclarationNode,
    StateKind,
    StateTypeNode,
    StructDeclarationNode,
    StructBindingPatternNode,
    StructFieldPatternNode,
    StructFieldNode,
    StructLiteralFieldNode,
    StructLiteralNode,
    StructPatternNode,
    TupleLiteralNode,
    TupleTypeNode,
    TransitionNode,
    UnaryExpressionNode,
    UnaryOperator,
    Visibility,
    WhileStatementNode,
    WildcardPatternNode,
)
from .namespace import ModuleNamespace, NamespaceResolutionError, resolve_program
from .semantic_patterns import StructPatternSemanticError, resolve_struct_pattern


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
QUALIFIED_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
RESERVED_IDENTIFIERS = {
    "bool",
    "true",
    "false",
    "if",
    "for",
    "while",
    "loop",
    "break",
    "continue",
    "in",
    "struct",
    "enum",
    "set",
    "map",
    "optional",
    "some",
    "none",
    "else",
    "match",
    "runtime",
}
DECLARATION_NODES = (
    ConceptNode,
    ObjectNode,
    EventNode,
    ActionNode,
    AttributeNode,
    GoalNode,
    ConstraintNode,
    StateDeclarationNode,
    ReasonGraphDeclarationNode,
    ExecutionPlanDeclarationNode,
    StructDeclarationNode,
    EnumDeclarationNode,
    ConstDeclarationNode,
    CalculationNode,
    FunctionDeclarationNode,
    TransitionNode,
)
KNOWN_NODE_TYPES = (
    ProgramNode,
    PackageDeclarationNode,
    ModuleNode,
    ImportNode,
    ImportResolutionNode,
    StateDeclarationNode,
    ReasonGraphTransitionNode,
    ReasonGraphDeclarationNode,
    PlanStepNode,
    ExecutionPlanDeclarationNode,
    *DECLARATION_NODES,
    RelationNode,
    StructFieldNode,
    EnumValueNode,
    LetStatementNode,
    ConstStatementNode,
    AssignmentStatementNode,
    FieldAssignmentStatementNode,
    IndexAssignmentStatementNode,
    ResultStatementNode,
    ReturnStatementNode,
    ForStatementNode,
    WhileStatementNode,
    LoopStatementNode,
    BreakStatementNode,
    ContinueStatementNode,
    RequireStatementNode,
    GoalStatementNode,
    ReachStatementNode,
    ExpressionStatementNode,
    IfStatementNode,
    ElseIfStatementNode,
    ElseStatementNode,
    MatchStatementNode,
    MatchArmNode,
    ExpressionNode,
    PatternNode,
    IntegerLiteralNode,
    FloatLiteralNode,
    BooleanLiteralNode,
    StringLiteralNode,
    NullLiteralNode,
    IdentifierNode,
    QualifiedIdentifierNode,
    RuntimeNamespaceNode,
    RuntimeCallExpressionNode,
    UnaryExpressionNode,
    BinaryExpressionNode,
    ComparisonExpressionNode,
    LogicalExpressionNode,
    ParenthesizedExpressionNode,
    MemberAccessNode,
    CallExpressionNode,
    NamedTypeNode,
    ArrayTypeNode,
    TupleTypeNode,
    SetTypeNode,
    MapTypeNode,
    StructLiteralFieldNode,
    StructLiteralNode,
    ArrayLiteralNode,
    TupleLiteralNode,
    SetLiteralNode,
    MapEntryNode,
    MapLiteralNode,
    IndexAccessNode,
    OptionalTypeNode,
    SomeExpressionNode,
    NoneLiteralNode,
    OptionalPatternNode,
    OptionalValuePatternNode,
    OrPatternNode,
    StructBindingPatternNode,
    StructFieldPatternNode,
    StructPatternNode,
    IdentifierPatternNode,
    QualifiedPatternNode,
    EnumValuePatternNode,
    WildcardPatternNode,
    DefaultPatternNode,
    LiteralPatternNode,
    PrimitiveTypeNode,
    StateTypeNode,
)


class SurfaceValidationError(ValueError):
    pass


_CURRENT_NAMESPACE: ModuleNamespace | None = None
_CURRENT_FUNCTION: str | None = None
RUNTIME_RESULT_TYPES = {
    "SearchResult",
    "SimulationResult",
    "PredictionResult",
    "PlanningResult",
}


@dataclass(frozen=True)
class _Binding:
    type_node: Any
    mutable: bool


def validate(program: ProgramNode) -> None:
    global _CURRENT_NAMESPACE
    if not isinstance(program, ProgramNode):
        raise SurfaceValidationError("AST-V001 root must be ProgramNode")
    if not program.modules:
        raise SurfaceValidationError("ProgramNode requires at least one module")
    if program.package is not None:
        if program.package.name == "runtime":
            raise SurfaceValidationError("RV-1 ReservedRuntimeNamespace")
        _identifier(program.package.name, "PV-1 PackageDeclarationNode.name")
    try:
        resolved_program, namespaces = resolve_program(program, strict=False)
    except NamespaceResolutionError as error:
        raise SurfaceValidationError(str(error)) from error
    module_names: set[str] = set()
    for module in resolved_program.modules:
        namespace_name = (
            f"{resolved_program.package.name}.{module.name}"
            if resolved_program.package is not None
            else module.name
        )
        _CURRENT_NAMESPACE = namespaces[namespace_name]
        _validate_node_types(module)
        if module.name == "runtime":
            raise SurfaceValidationError("RV-1 ReservedRuntimeNamespace")
        _identifier(module.name, "NS-V001 ModuleNode.name")
        if module.name in module_names:
            raise SurfaceValidationError(f"M-002 duplicate module name: {module.name}")
        module_names.add(module.name)
        if not isinstance(module.visibility, Visibility):
            raise SurfaceValidationError("AST-V001 invalid module visibility")
        _validate_module(module)
    _CURRENT_NAMESPACE = None


def _validate_module(module: ModuleNode) -> None:
    symbols: dict[str, Any] = {}
    for node in module.body:
        if isinstance(node, ImportNode):
            if not node.path:
                raise SurfaceValidationError("I-001 import path must not be empty")
            if node.path[0] == "runtime":
                raise SurfaceValidationError("RV-2 RuntimeNamespaceCannotBeImported")
            for part in node.path:
                _identifier(part, "AST-V002 ImportNode.path")
            if node.alias is not None:
                if node.alias == "runtime":
                    raise SurfaceValidationError(
                        "RV-3 RuntimeNamespaceCannotBeShadowed"
                    )
                _identifier(node.alias, "AST-V002 ImportNode.alias")
            continue
        if isinstance(node, ConstDeclarationNode):
            _identifier(node.name, "PV-7 ConstDeclarationNode.name")
            if name := node.name:
                if name in symbols:
                    raise SurfaceValidationError(
                        f"AST-V003 duplicate module symbol: {name}"
                    )
                symbols[name] = node
            if node.type_annotation is not None:
                _validate_type_node(node.type_annotation)
            _validate_calculation_expression(node.expression, symbols, {})
            continue
        if isinstance(node, DECLARATION_NODES):
            name = node.name
            _identifier(name, f"AST-V002 {type(node).__name__}.name")
            if name in symbols:
                code = "FN-001" if isinstance(node, FunctionDeclarationNode) else "AST-V003"
                raise SurfaceValidationError(f"{code} duplicate module symbol: {name}")
            symbols[name] = node
        if isinstance(
            node,
            (
                LetStatementNode,
                ConstStatementNode,
                AssignmentStatementNode,
                FieldAssignmentStatementNode,
                IndexAssignmentStatementNode,
                ResultStatementNode,
                ReturnStatementNode,
                ForStatementNode,
                WhileStatementNode,
                LoopStatementNode,
                BreakStatementNode,
                ContinueStatementNode,
                RequireStatementNode,
                GoalStatementNode,
                ReachStatementNode,
                ExpressionStatementNode,
                IfStatementNode,
                MatchStatementNode,
            ),
        ):
            raise SurfaceValidationError(
                f"ST-V002 {type(node).__name__} is invalid in module body"
            )

    for node in module.body:
        if isinstance(node, RelationNode):
            if node.source not in symbols:
                raise SurfaceValidationError(
                    f"AST-V004 unresolved relation source: {node.source}"
                )
            if node.target not in symbols:
                raise SurfaceValidationError(
                    f"AST-V004 unresolved relation target: {node.target}"
                )
        if isinstance(node, TransitionNode):
            _validate_transition(node, symbols)
        elif isinstance(node, StructDeclarationNode):
            _validate_struct(node, symbols)
        elif isinstance(node, EnumDeclarationNode):
            _validate_enum(node)
        elif isinstance(node, ReasonGraphDeclarationNode):
            _validate_reason_graph_declaration(node)
        elif isinstance(node, ExecutionPlanDeclarationNode):
            _validate_execution_plan_declaration(node, symbols)
        elif isinstance(node, CalculationNode):
            _validate_calculation(node, symbols)
        elif isinstance(node, FunctionDeclarationNode):
            _validate_function(node, symbols)
        else:
            _validate_ast_node(node)
    _validate_calculation_dependency_graph(module)


def _validate_ast_node(node: Any) -> None:
    if isinstance(node, RelationNode):
        _identifier(node.source, "R-001 RelationNode.source")
        _identifier(node.target, "R-002 RelationNode.target")
        if not isinstance(node.relation, RelationType):
            raise SurfaceValidationError("R-003 RelationNode.relation is invalid")
    elif isinstance(node, TransitionNode):
        _identifier(node.name, "T-001 TransitionNode.name")
        _identifier(node.from_state, "T-002 TransitionNode.from_state")
        _identifier(node.to_state, "T-003 TransitionNode.to_state")
    elif isinstance(node, CalculationNode):
        _identifier(node.name, "CAL-V001 CalculationNode.name")
        if not isinstance(node.visibility, Visibility):
            raise SurfaceValidationError("CAL-V001 invalid calculation visibility")
        if node.return_type is not None:
            _validate_type_node(node.return_type)
    elif isinstance(node, FunctionDeclarationNode):
        _identifier(node.name, "FN-001 FunctionDeclarationNode.name")
        if not isinstance(node.visibility, Visibility):
            raise SurfaceValidationError("FN-001 invalid function visibility")
        if node.return_type is not None:
            _validate_type_node(node.return_type)
        seen: set[str] = set()
        for parameter in node.parameters:
            name = _function_parameter_name(parameter)
            parameter_type = _function_parameter_type(parameter)
            _identifier(name, "FN-002 FunctionDeclarationNode.parameter")
            if parameter_type is not None:
                _validate_type_node(parameter_type)
            if name in seen:
                raise SurfaceValidationError(f"FN-006 duplicate parameter: {name}")
            seen.add(name)
    elif isinstance(node, StructDeclarationNode):
        _identifier(node.name, "TV-1 StructDeclarationNode.name")
        if not isinstance(node.visibility, Visibility):
            raise SurfaceValidationError("PV-6 invalid struct visibility")
    elif isinstance(node, StateDeclarationNode):
        _identifier(node.name, "RI4-2 StateDeclarationNode.name")
    elif isinstance(node, ReasonGraphTransitionNode):
        _identifier(node.source, "RI4-4 ReasonGraphTransitionNode.source")
        _identifier(node.target, "RI4-4 ReasonGraphTransitionNode.target")
    elif isinstance(node, ReasonGraphDeclarationNode):
        _identifier(node.name, "RI4-4 ReasonGraphDeclarationNode.name")
    elif isinstance(node, PlanStepNode):
        _identifier(node.source, "RI4-5 PlanStepNode.source")
        _identifier(node.target, "RI4-5 PlanStepNode.target")
    elif isinstance(node, ExecutionPlanDeclarationNode):
        _identifier(node.name, "RI4-6 ExecutionPlanDeclarationNode.name")
    elif isinstance(node, StructFieldNode):
        _identifier(node.name, "TV-3 StructFieldNode.name")
        _validate_type_node(node.field_type)
    elif isinstance(node, EnumDeclarationNode):
        _identifier(node.name, "TV-2 EnumDeclarationNode.name")
        if not isinstance(node.visibility, Visibility):
            raise SurfaceValidationError("PV-6 invalid enum visibility")
    elif isinstance(node, EnumValueNode):
        _identifier(node.name, "TV-7 EnumValueNode.name")
    elif isinstance(node, LetStatementNode):
        _identifier(node.identifier, "ST-001 LetStatementNode.identifier")
        _expression(node.expression, "ST-002 LetStatementNode.expression")
        if node.type_annotation is not None:
            _validate_type_node(node.type_annotation)
    elif isinstance(node, ConstStatementNode):
        _identifier(node.identifier, "ST-001 ConstStatementNode.identifier")
        _expression(node.expression, "ST-002 ConstStatementNode.expression")
        if node.type_annotation is not None:
            _validate_type_node(node.type_annotation)
    elif isinstance(node, AssignmentStatementNode):
        _identifier(node.target, "AssignmentStatementNode.target")
        _expression(node.expression, "AssignmentStatementNode.expression")
    elif isinstance(node, FieldAssignmentStatementNode):
        _expression(node.target, "TV-10 FieldAssignmentStatementNode.target")
        _expression(node.expression, "TV-10 FieldAssignmentStatementNode.expression")
    elif isinstance(node, IndexAssignmentStatementNode):
        _expression(node.target, "CV5-9 IndexAssignmentStatementNode.target")
        _expression(node.expression, "CV5-9 IndexAssignmentStatementNode.expression")
    elif isinstance(node, ResultStatementNode):
        _expression(node.expression, "ST-020 ResultStatementNode.expression")
    elif isinstance(node, ReturnStatementNode):
        _expression(node.expression, "FN-020 ReturnStatementNode.expression")
    elif isinstance(node, RequireStatementNode):
        _identifier(node.constraint, "RequireStatementNode.constraint")
    elif isinstance(node, (GoalStatementNode, ReachStatementNode)):
        _identifier(node.goal, f"{type(node).__name__}.goal")
    elif isinstance(node, ExpressionStatementNode):
        _expression(node.expression, "ExpressionStatementNode.expression")
        if not isinstance(
            node.expression.expression, (CallExpressionNode, RuntimeCallExpressionNode)
        ):
            raise SurfaceValidationError(
                "ST-060 ExpressionStatementNode root must be CallExpressionNode"
            )
    elif isinstance(node, ForStatementNode):
        _identifier(node.iterator, "IV-1 ForStatementNode.iterator")
        _expression(node.iterable, "IV-8 ForStatementNode.iterable")
    elif isinstance(node, WhileStatementNode):
        _expression(node.condition, "IV-3 WhileStatementNode.condition")
    elif isinstance(node, LoopStatementNode):
        return
    elif isinstance(node, (BreakStatementNode, ContinueStatementNode)):
        return
    elif isinstance(node, IfStatementNode):
        _expression(node.condition, "IfNode.condition")
        if not node.body:
            raise SurfaceValidationError("ST-071 IfStatementNode body is required")
    elif isinstance(node, MatchStatementNode):
        _expression(node.expression, "MT-001 MatchNode.expression")
        if not node.arms:
            raise SurfaceValidationError("MT-002 MatchNode requires at least one arm")
        arm_keys: set[tuple[str, Any]] = set()
        precomputed_keys = [
            key
            for arm in node.arms
            if arm.guard is None
            for key in _pattern_keys(arm.pattern)
        ]
        if sum(1 for key in precomputed_keys if key[0] == "default") > 1:
            raise SurfaceValidationError("PT-003 MSI-003 multiple default")
        if sum(1 for key in precomputed_keys if key[0] == "wildcard") > 1:
            raise SurfaceValidationError("PT-006 duplicate wildcard")
        for index, arm in enumerate(node.arms):
            _pattern(arm.pattern)
            if arm.guard is not None:
                _expression(arm.guard, "PG-001 MatchArmNode.guard")
            keys = _pattern_keys(arm.pattern)
            if arm.guard is not None:
                continue
            if any(key[0] == "default" for key in keys):
                if index != len(node.arms) - 1:
                    raise SurfaceValidationError("PT-002 MSI-002 default not last")
            elif any(key[0] == "wildcard" for key in keys):
                if index != len(node.arms) - 1:
                    raise SurfaceValidationError("PT-007 unreachable pattern")
            for key in keys:
                if key in arm_keys:
                    raise SurfaceValidationError("PT-001 MSI-001 duplicate pattern")
                arm_keys.add(key)
    elif isinstance(node, ConstraintNode):
        _identifier(node.name, "AST-V002 ConstraintNode.name")
        _validate_constraint_expression(node)
    elif isinstance(node, DECLARATION_NODES):
        _identifier(node.name, f"AST-V002 {type(node).__name__}.name")
    elif isinstance(node, ImportNode):
        pass
    else:
        raise SurfaceValidationError(
            f"AST-V001 unsupported node type: {type(node).__name__}"
        )


def _validate_transition(node: TransitionNode, symbols: dict[str, Any]) -> None:
    _validate_ast_node(node)
    _validate_statement_list(
        node.body, placement="transition", symbols=symbols, allow_result=False
    )


def _validate_struct(node: StructDeclarationNode, symbols: dict[str, Any]) -> None:
    _validate_ast_node(node)
    field_names: set[str] = set()
    for field in node.fields:
        _validate_ast_node(field)
        if field.name in field_names:
            raise SurfaceValidationError(f"TV-3 duplicate struct field: {field.name}")
        field_names.add(field.name)
        _resolve_type(field.field_type, symbols)
        if isinstance(field.field_type, NamedTypeNode) and field.field_type.name == node.name:
            raise SurfaceValidationError("TV-8 RecursiveStructDefinition")
    _reject_indirect_struct_recursion(node, symbols)


def _validate_reason_graph_declaration(node: ReasonGraphDeclarationNode) -> None:
    _validate_ast_node(node)
    states: set[str] = set()
    for state in node.states:
        _validate_ast_node(state)
        if state.name in states:
            raise SurfaceValidationError(f"RI4-2 duplicate state in graph: {state.name}")
        states.add(state.name)
    for transition in node.transitions:
        _validate_ast_node(transition)
        if transition.source not in states or transition.target not in states:
            raise SurfaceValidationError("InvalidReasonGraphTransition")


def _validate_constraint_expression(node: ConstraintNode) -> None:
    if node.expression is None:
        return
    try:
        expression = parse_expression(node.expression)
        expression_type = _expression_type(expression.expression, {}, {})
    except (ExpressionSyntaxError, SurfaceValidationError) as error:
        raise SurfaceValidationError("InvalidConstraintExpression") from error
    if expression_type != PrimitiveTypeNode(PrimitiveKind.BOOL):
        raise SurfaceValidationError("InvalidConstraintExpression")


def _validate_execution_plan_declaration(
    node: ExecutionPlanDeclarationNode, symbols: dict[str, Any]
) -> None:
    _validate_ast_node(node)
    known_states = {
        name
        for name, symbol in symbols.items()
        if isinstance(symbol, StateDeclarationNode)
    }
    for graph in (
        symbol for symbol in symbols.values() if isinstance(symbol, ReasonGraphDeclarationNode)
    ):
        known_states.update(state.name for state in graph.states)
    for step in node.steps:
        _validate_ast_node(step)
        if step.source not in known_states or step.target not in known_states:
            raise SurfaceValidationError("InvalidExecutionPlanStep")


def _validate_enum(node: EnumDeclarationNode) -> None:
    _validate_ast_node(node)
    values: set[str] = set()
    for value in node.values:
        _validate_ast_node(value)
        if value.name in values:
            raise SurfaceValidationError(f"TV-7 duplicate enum value: {value.name}")
        values.add(value.name)


def _validate_calculation(node: CalculationNode, symbols: dict[str, Any]) -> None:
    _validate_ast_node(node)
    if node.goal_annotation is not None:
        _identifier(node.goal_annotation, "CAL-V008 CalculationNode.goal_annotation")
        goal = symbols.get(node.goal_annotation)
        if goal is None:
            raise SurfaceValidationError(
                f"CAL-V008 goal annotation does not exist: {node.goal_annotation}"
            )
        if not isinstance(goal, GoalNode):
            raise SurfaceValidationError(
                f"CAL-V008 annotation is not a Goal: {node.goal_annotation}"
            )
    if node.return_type is not None:
        _resolve_type(node.return_type, symbols)
    _validate_calculation_statements(
        node.body,
        symbols=symbols,
        bindings={},
        allow_terminal_result=True,
        return_type=node.return_type,
        loop_depth=0,
    )
    if not _statement_list_terminates_with_result(node.body):
        raise SurfaceValidationError(
            "CAL-010 calculation requires a terminal ResultStatementNode"
        )


def _validate_calculation_dependency_graph(module: ModuleNode) -> None:
    calculations = {
        node.name: node for node in module.body if isinstance(node, CalculationNode)
    }
    if not calculations:
        return
    dependencies = {
        name: _calculation_dependencies(node, set(calculations))
        for name, node in calculations.items()
    }
    ready = sorted(name for name, required in dependencies.items() if not required)
    while ready:
        name = ready.pop(0)
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


def _calculation_dependencies(
    calculation: CalculationNode, calculation_names: set[str]
) -> set[str]:
    local_names: set[str] = set()
    dependencies: set[str] = set()
    for statement in calculation.body:
        expression = _calculation_statement_expression(statement)
        if expression is not None:
            dependencies.update(
                reference
                for reference in _calculation_expression_identifiers(expression)
                if reference in calculation_names and reference not in local_names
            )
        if isinstance(statement, (LetStatementNode, ConstStatementNode)):
            local_names.add(statement.identifier)
        elif isinstance(statement, AssignmentStatementNode):
            local_names.add(statement.target)
    dependencies.discard(calculation.name)
    return dependencies


def _calculation_statement_expression(statement: Any) -> ExpressionNode | None:
    if isinstance(
        statement,
        (
            LetStatementNode,
            ConstStatementNode,
            AssignmentStatementNode,
            ResultStatementNode,
            ExpressionStatementNode,
            FieldAssignmentStatementNode,
            IndexAssignmentStatementNode,
        ),
    ):
        return statement.expression
    return None


def _calculation_expression_identifiers(expression: ExpressionNode | Any) -> set[str]:
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


def _validate_function(node: FunctionDeclarationNode, symbols: dict[str, Any]) -> None:
    global _CURRENT_FUNCTION
    _validate_ast_node(node)
    if node.return_type is not None:
        _resolve_type(node.return_type, symbols)
    bindings = {
        _function_parameter_name(parameter): _Binding(
            _function_parameter_type(parameter) or _UNKNOWN_TYPE,
            mutable=False,
        )
        for parameter in node.parameters
    }
    previous_function = _CURRENT_FUNCTION
    _CURRENT_FUNCTION = node.name
    try:
        _validate_function_statements(
            node.body,
            symbols=symbols,
            bindings=bindings,
            allow_terminal_return=True,
            loop_depth=0,
            return_type=node.return_type,
        )
    finally:
        _CURRENT_FUNCTION = previous_function
    _validate_function_control_flow(node.body)
    if not _statement_list_terminates_with_return(node.body):
        raise SurfaceValidationError("FCF-001 Not all execution paths return")


def _function_parameter_name(parameter: Any) -> str:
    if isinstance(parameter, dict):
        return str(parameter.get("name", ""))
    return str(parameter)


def _function_parameter_type(parameter: Any) -> Any:
    if isinstance(parameter, dict):
        return parameter.get("type")
    return None


def _validate_statement_list(
    statements: tuple[Any, ...],
    *,
    placement: str,
    symbols: dict[str, Any],
    allow_result: bool,
) -> None:
    allowed = {
        "transition": (
            RequireStatementNode,
            GoalStatementNode,
            ReachStatementNode,
            IfStatementNode,
            MatchStatementNode,
            ExpressionStatementNode,
        ),
        "calculation": (
            LetStatementNode,
            ConstStatementNode,
            AssignmentStatementNode,
            FieldAssignmentStatementNode,
            IndexAssignmentStatementNode,
            ForStatementNode,
            WhileStatementNode,
            LoopStatementNode,
            IfStatementNode,
            MatchStatementNode,
            ExpressionStatementNode,
            ResultStatementNode,
        ),
    }[placement]
    bindings: set[str] = set()
    for statement in statements:
        if not isinstance(statement, allowed):
            raise SurfaceValidationError(
                f"ST-V002 {type(statement).__name__} is invalid in {placement} body"
            )
        if isinstance(statement, ResultStatementNode) and not allow_result:
            raise SurfaceValidationError("ST-V002 result is invalid in this body")
        if isinstance(statement, ReturnStatementNode):
            raise SurfaceValidationError("ST-V002 return is invalid in this body")
        _validate_ast_node(statement)
        if isinstance(statement, (LetStatementNode, ConstStatementNode)):
            if statement.identifier in bindings:
                raise SurfaceValidationError(
                    f"ST-003 duplicate binding: {statement.identifier}"
                )
            bindings.add(statement.identifier)
        elif isinstance(statement, RequireStatementNode):
            reference = symbols.get(statement.constraint)
            if reference is None:
                raise SurfaceValidationError(
                    f"ST-030 constraint does not exist: {statement.constraint}"
                )
            if not isinstance(reference, ConstraintNode):
                raise SurfaceValidationError(
                    "ST-031 TYPE-010 TYPE-V008 require must reference Constraint: "
                    f"{statement.constraint}"
                )
        elif isinstance(statement, (GoalStatementNode, ReachStatementNode)):
            reference = symbols.get(statement.goal)
            if reference is None:
                code = "ST-040" if isinstance(statement, GoalStatementNode) else "ST-051"
                raise SurfaceValidationError(
                    f"{code} goal does not exist: {statement.goal}"
                )
            if not isinstance(reference, GoalNode):
                code = "ST-041" if isinstance(statement, GoalStatementNode) else "ST-051"
                raise SurfaceValidationError(
                    f"TYPE-011 TYPE-V007 {code} reference is not a Goal: "
                    f"{statement.goal}"
                )
        elif isinstance(statement, IfStatementNode):
            _validate_statement_list(
                statement.body,
                placement=placement,
                symbols=symbols,
                allow_result=False,
            )
            for branch in statement.elif_branches:
                _expression(branch.condition, "ElseIfStatementNode.condition")
                _validate_statement_list(
                    branch.body,
                    placement=placement,
                    symbols=symbols,
                    allow_result=False,
                )
            if statement.else_branch:
                _validate_statement_list(
                    statement.else_branch.body,
                    placement=placement,
                    symbols=symbols,
                    allow_result=False,
                )
        elif isinstance(statement, MatchStatementNode):
            for arm in statement.arms:
                if not arm.body:
                    raise SurfaceValidationError(
                        "ST-081 MatchArmNode body is required"
                    )
                _validate_statement_list(
                    arm.body,
                    placement=placement,
                    symbols=symbols,
                    allow_result=False,
                )


def _validate_calculation_statements(
    statements: tuple[Any, ...],
    *,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
    allow_terminal_result: bool,
    return_type: Any = None,
    loop_depth: int = 0,
) -> None:
    allowed = (
        LetStatementNode,
        ConstStatementNode,
        AssignmentStatementNode,
        FieldAssignmentStatementNode,
        IndexAssignmentStatementNode,
        ForStatementNode,
        WhileStatementNode,
        LoopStatementNode,
        BreakStatementNode,
        ContinueStatementNode,
        IfStatementNode,
        MatchStatementNode,
        ExpressionStatementNode,
        ResultStatementNode,
    )
    direct_results = sum(
        isinstance(statement, ResultStatementNode) for statement in statements
    )
    if direct_results > 1:
        raise SurfaceValidationError(
            "CAL-011 calculation path contains multiple ResultStatementNode values"
        )
    local_bindings = dict(bindings)
    for index, statement in enumerate(statements):
        if not isinstance(statement, allowed):
            raise SurfaceValidationError(
                f"CAL-001 {type(statement).__name__} is invalid in calculation body"
            )
        _validate_ast_node(statement)
        is_last = index == len(statements) - 1
        if isinstance(statement, (LetStatementNode, ConstStatementNode)):
            if statement.identifier in local_bindings:
                raise SurfaceValidationError(
                    f"CAL-021 duplicate binding: {statement.identifier}"
                )
            _validate_calculation_expression(
                statement.expression, symbols, local_bindings
            )
            expression_type = _expression_type(
                statement.expression.expression, symbols, local_bindings
            )
            if statement.type_annotation is None and _contains_uncontextual_none_literal(
                statement.expression.expression,
                symbols,
            ):
                raise SurfaceValidationError("OV-1 OptionalTypeRequired")
            if statement.type_annotation is not None:
                _resolve_type(statement.type_annotation, symbols)
                _require_compatible(
                    statement.type_annotation,
                    expression_type,
                    statement.expression,
                    symbols,
                    "TYPE-V003 assignment mismatch",
                )
                binding_type = statement.type_annotation
            else:
                binding_type = expression_type
            local_bindings[statement.identifier] = _Binding(
                binding_type,
                mutable=isinstance(statement, LetStatementNode),
            )
        elif isinstance(statement, AssignmentStatementNode):
            if (
                statement.target not in local_bindings
                and statement.target not in symbols
            ):
                raise SurfaceValidationError(
                    f"CAL-020 undefined assignment target: {statement.target}"
                )
            if (
                statement.target in local_bindings
                and not local_bindings[statement.target].mutable
            ):
                raise SurfaceValidationError(
                    f"CONST-001 cannot assign to constant: {statement.target}"
                )
            _validate_calculation_expression(
                statement.expression, symbols, local_bindings
            )
            if statement.target in local_bindings:
                _require_compatible(
                    local_bindings[statement.target].type_node,
                    _expression_type(
                        statement.expression.expression, symbols, local_bindings
                    ),
                    statement.expression,
                    symbols,
                    "TYPE-V003 assignment mismatch",
                )
        elif isinstance(statement, FieldAssignmentStatementNode):
            _validate_field_assignment(statement, symbols, local_bindings)
        elif isinstance(statement, IndexAssignmentStatementNode):
            _validate_index_assignment(statement, symbols, local_bindings)
        elif isinstance(statement, ExpressionStatementNode):
            if _contains_uncontextual_none_literal(statement.expression.expression, symbols):
                raise SurfaceValidationError("OV-1 OptionalTypeRequired")
            _validate_calculation_expression(
                statement.expression, symbols, local_bindings
            )
        elif isinstance(statement, ResultStatementNode):
            if not allow_terminal_result or not is_last:
                raise SurfaceValidationError(
                    "CAL-012 ResultStatementNode must be the final statement"
                )
            _validate_calculation_expression(
                statement.expression, symbols, local_bindings
            )
            if return_type is None and _contains_uncontextual_none_literal(
                statement.expression.expression,
                symbols,
            ):
                raise SurfaceValidationError("OV-1 OptionalTypeRequired")
            if return_type is not None:
                _require_compatible(
                    return_type,
                    _expression_type(
                        statement.expression.expression, symbols, local_bindings
                    ),
                    statement.expression,
                    symbols,
                    "TYPE-V003 calculation return mismatch",
                )
        elif isinstance(statement, BreakStatementNode):
            if loop_depth <= 0:
                raise SurfaceValidationError("IV-4 BreakOutsideLoop")
        elif isinstance(statement, ContinueStatementNode):
            if loop_depth <= 0:
                raise SurfaceValidationError("IV-5 ContinueOutsideLoop")
        elif isinstance(statement, ForStatementNode):
            if statement.iterator in local_bindings:
                raise SurfaceValidationError(
                    f"IV-1 duplicate iteration variable: {statement.iterator}"
                )
            _validate_calculation_expression(
                statement.iterable, symbols, local_bindings
            )
            _require_iterable(statement.iterable, symbols, local_bindings)
            loop_bindings = dict(local_bindings)
            loop_bindings[statement.iterator] = _Binding(
                _UNKNOWN_TYPE,
                mutable=False,
            )
            _validate_calculation_statements(
                statement.body,
                symbols=symbols,
                bindings=loop_bindings,
                allow_terminal_result=True,
                return_type=return_type,
                loop_depth=loop_depth + 1,
            )
        elif isinstance(statement, WhileStatementNode):
            _validate_calculation_expression(
                statement.condition, symbols, local_bindings
            )
            _require_bool_condition(statement.condition, symbols, local_bindings)
            _validate_calculation_statements(
                statement.body,
                symbols=symbols,
                bindings=local_bindings,
                allow_terminal_result=True,
                return_type=return_type,
                loop_depth=loop_depth + 1,
            )
        elif isinstance(statement, LoopStatementNode):
            _validate_calculation_statements(
                statement.body,
                symbols=symbols,
                bindings=local_bindings,
                allow_terminal_result=True,
                return_type=return_type,
                loop_depth=loop_depth + 1,
            )
        elif isinstance(statement, IfStatementNode):
            _validate_calculation_expression(
                statement.condition, symbols, local_bindings
            )
            _require_bool_condition(statement.condition, symbols, local_bindings)
            _validate_calculation_statements(
                statement.body,
                symbols=symbols,
                bindings=local_bindings,
                allow_terminal_result=is_last,
                return_type=return_type,
                loop_depth=loop_depth,
            )
            for branch in statement.elif_branches:
                _validate_calculation_expression(
                    branch.condition, symbols, local_bindings
                )
                _require_bool_condition(branch.condition, symbols, local_bindings)
                _validate_calculation_statements(
                    branch.body,
                    symbols=symbols,
                    bindings=local_bindings,
                    allow_terminal_result=is_last,
                    return_type=return_type,
                    loop_depth=loop_depth,
                )
            if statement.else_branch:
                _validate_calculation_statements(
                    statement.else_branch.body,
                    symbols=symbols,
                    bindings=local_bindings,
                    allow_terminal_result=is_last,
                    return_type=return_type,
                    loop_depth=loop_depth,
                )
        elif isinstance(statement, MatchStatementNode):
            _validate_calculation_expression(
                statement.expression, symbols, local_bindings
            )
            _validate_match_patterns(statement, symbols, local_bindings)
            _validate_enum_match_exhaustiveness(statement, symbols, local_bindings)
            _validate_optional_match_exhaustiveness(
                statement, symbols, local_bindings
            )
            _validate_bool_match_exhaustiveness(statement, symbols, local_bindings)
            _validate_struct_match_exhaustiveness(statement, symbols, local_bindings)
            for arm in statement.arms:
                arm_bindings = _match_arm_bindings(
                    statement, arm.pattern, symbols, local_bindings
                )
                _validate_match_guard(
                    arm, symbols, {**local_bindings, **arm_bindings}
                )
                _validate_calculation_statements(
                    arm.body,
                    symbols=symbols,
                    bindings={**local_bindings, **arm_bindings},
                    allow_terminal_result=is_last,
                    return_type=return_type,
                    loop_depth=loop_depth,
                )


def _statement_list_terminates_with_result(statements: tuple[Any, ...]) -> bool:
    if not statements:
        return False
    final = statements[-1]
    if isinstance(final, ResultStatementNode):
        return True
    if isinstance(final, IfStatementNode):
        if final.else_branch is None:
            return False
        branches = [final.body]
        branches.extend(branch.body for branch in final.elif_branches)
        branches.append(final.else_branch.body)
        return all(_statement_list_terminates_with_result(body) for body in branches)
    if isinstance(final, MatchStatementNode):
        return bool(final.arms) and all(
            _statement_list_terminates_with_result(arm.body) for arm in final.arms
        )
    return False


def _validate_function_statements(
    statements: tuple[Any, ...],
    *,
    symbols: dict[str, Any],
    bindings: dict[str, _Binding],
    allow_terminal_return: bool,
    loop_depth: int = 0,
    return_type: Any = None,
) -> None:
    allowed = (
        LetStatementNode,
        ConstStatementNode,
        AssignmentStatementNode,
        FieldAssignmentStatementNode,
        IndexAssignmentStatementNode,
        ForStatementNode,
        WhileStatementNode,
        LoopStatementNode,
        BreakStatementNode,
        ContinueStatementNode,
        IfStatementNode,
        MatchStatementNode,
        ExpressionStatementNode,
        ReturnStatementNode,
    )
    local_bindings = dict(bindings)
    for index, statement in enumerate(statements):
        if not isinstance(statement, allowed):
            raise SurfaceValidationError(
                f"FN-001 {type(statement).__name__} is invalid in function body"
            )
        _validate_ast_node(statement)
        is_last = index == len(statements) - 1
        if isinstance(statement, (LetStatementNode, ConstStatementNode)):
            if statement.identifier in local_bindings:
                raise SurfaceValidationError(
                    f"FN-021 duplicate binding: {statement.identifier}"
                )
            _validate_calculation_expression(
                statement.expression, symbols, local_bindings
            )
            expression_type = _expression_type(
                statement.expression.expression, symbols, local_bindings
            )
            if statement.type_annotation is None and _contains_uncontextual_none_literal(
                statement.expression.expression,
                symbols,
            ):
                raise SurfaceValidationError("OV-1 OptionalTypeRequired")
            if statement.type_annotation is not None:
                _resolve_type(statement.type_annotation, symbols)
                _require_compatible(
                    statement.type_annotation,
                    expression_type,
                    statement.expression,
                    symbols,
                    "TYPE-V003 assignment mismatch",
                )
                expression_type = statement.type_annotation
            local_bindings[statement.identifier] = _Binding(
                expression_type,
                mutable=isinstance(statement, LetStatementNode),
            )
        elif isinstance(statement, AssignmentStatementNode):
            if statement.target not in local_bindings:
                raise SurfaceValidationError(
                    f"FN-020 undefined assignment target: {statement.target}"
                )
            if not local_bindings[statement.target].mutable:
                raise SurfaceValidationError(
                    f"CONST-001 cannot assign to constant: {statement.target}"
                )
            _validate_calculation_expression(
                statement.expression, symbols, local_bindings
            )
            _require_compatible(
                local_bindings[statement.target].type_node,
                _expression_type(
                    statement.expression.expression, symbols, local_bindings
                ),
                statement.expression,
                symbols,
                "TYPE-V003 assignment mismatch",
            )
        elif isinstance(statement, FieldAssignmentStatementNode):
            _validate_field_assignment(statement, symbols, local_bindings)
        elif isinstance(statement, IndexAssignmentStatementNode):
            _validate_index_assignment(statement, symbols, local_bindings)
        elif isinstance(statement, ExpressionStatementNode):
            if _contains_uncontextual_none_literal(statement.expression.expression, symbols):
                raise SurfaceValidationError("OV-1 OptionalTypeRequired")
            _validate_calculation_expression(
                statement.expression, symbols, local_bindings
            )
        elif isinstance(statement, ReturnStatementNode):
            if not allow_terminal_return:
                raise SurfaceValidationError(
                    "FCF-002 unreachable statement"
                )
            _validate_calculation_expression(
                statement.expression, symbols, local_bindings
            )
            if return_type is None and _contains_uncontextual_none_literal(
                statement.expression.expression,
                symbols,
            ):
                raise SurfaceValidationError("OV-1 OptionalTypeRequired")
            if return_type is not None:
                _require_compatible(
                    return_type,
                    _expression_type(
                        statement.expression.expression, symbols, local_bindings
                    ),
                    statement.expression,
                    symbols,
                    "FN-005 function return mismatch",
                )
        elif isinstance(statement, BreakStatementNode):
            if loop_depth <= 0:
                raise SurfaceValidationError("IV-4 BreakOutsideLoop")
        elif isinstance(statement, ContinueStatementNode):
            if loop_depth <= 0:
                raise SurfaceValidationError("IV-5 ContinueOutsideLoop")
        elif isinstance(statement, ForStatementNode):
            if statement.iterator in local_bindings:
                raise SurfaceValidationError(
                    f"IV-1 duplicate iteration variable: {statement.iterator}"
                )
            _validate_calculation_expression(
                statement.iterable, symbols, local_bindings
            )
            _require_iterable(statement.iterable, symbols, local_bindings)
            loop_bindings = dict(local_bindings)
            loop_bindings[statement.iterator] = _Binding(
                _UNKNOWN_TYPE,
                mutable=False,
            )
            _validate_function_statements(
                statement.body,
                symbols=symbols,
                bindings=loop_bindings,
                allow_terminal_return=True,
                loop_depth=loop_depth + 1,
                return_type=return_type,
            )
        elif isinstance(statement, WhileStatementNode):
            _validate_calculation_expression(
                statement.condition, symbols, local_bindings
            )
            _require_function_bool_condition(statement.condition, symbols, local_bindings)
            _validate_function_statements(
                statement.body,
                symbols=symbols,
                bindings=local_bindings,
                allow_terminal_return=True,
                loop_depth=loop_depth + 1,
                return_type=return_type,
            )
        elif isinstance(statement, LoopStatementNode):
            _validate_function_statements(
                statement.body,
                symbols=symbols,
                bindings=local_bindings,
                allow_terminal_return=True,
                loop_depth=loop_depth + 1,
                return_type=return_type,
            )
        elif isinstance(statement, IfStatementNode):
            _validate_calculation_expression(
                statement.condition, symbols, local_bindings
            )
            _require_function_bool_condition(statement.condition, symbols, local_bindings)
            _validate_function_statements(
                statement.body,
                symbols=symbols,
                bindings=local_bindings,
                allow_terminal_return=True,
                loop_depth=loop_depth,
                return_type=return_type,
            )
            for branch in statement.elif_branches:
                _validate_calculation_expression(
                    branch.condition, symbols, local_bindings
                )
                _require_function_bool_condition(branch.condition, symbols, local_bindings)
                _validate_function_statements(
                    branch.body,
                    symbols=symbols,
                    bindings=local_bindings,
                    allow_terminal_return=True,
                    loop_depth=loop_depth,
                    return_type=return_type,
                )
            if statement.else_branch:
                _validate_function_statements(
                    statement.else_branch.body,
                    symbols=symbols,
                    bindings=local_bindings,
                    allow_terminal_return=True,
                    loop_depth=loop_depth,
                    return_type=return_type,
                )
        elif isinstance(statement, MatchStatementNode):
            _validate_calculation_expression(
                statement.expression, symbols, local_bindings
            )
            _validate_match_patterns(statement, symbols, local_bindings)
            _validate_enum_match_exhaustiveness(statement, symbols, local_bindings)
            _validate_optional_match_exhaustiveness(
                statement, symbols, local_bindings
            )
            _validate_bool_match_exhaustiveness(statement, symbols, local_bindings)
            _validate_struct_match_exhaustiveness(statement, symbols, local_bindings)
            for arm in statement.arms:
                arm_bindings = _match_arm_bindings(
                    statement, arm.pattern, symbols, local_bindings
                )
                _validate_match_guard(
                    arm, symbols, {**local_bindings, **arm_bindings}
                )
                _validate_function_statements(
                    arm.body,
                    symbols=symbols,
                    bindings={**local_bindings, **arm_bindings},
                    allow_terminal_return=True,
                    loop_depth=loop_depth,
                    return_type=return_type,
                )


def _statement_list_terminates_with_return(statements: tuple[Any, ...]) -> bool:
    if not statements:
        return False
    reachable = True
    for statement in statements:
        if not reachable:
            return True
        if _statement_terminates_with_return(statement):
            reachable = False
    return not reachable


def _statement_terminates_with_return(statement: Any) -> bool:
    if isinstance(statement, ReturnStatementNode):
        return True
    if isinstance(statement, IfStatementNode):
        if statement.else_branch is None:
            return False
        branches = [statement.body]
        branches.extend(branch.body for branch in statement.elif_branches)
        branches.append(statement.else_branch.body)
        return all(_statement_list_terminates_with_return(body) for body in branches)
    if isinstance(statement, MatchStatementNode):
        return bool(statement.arms) and all(
            _statement_list_terminates_with_return(arm.body) for arm in statement.arms
        )
    return False


def _validate_function_control_flow(statements: tuple[Any, ...]) -> None:
    reachable = True
    for statement in statements:
        if not reachable:
            raise SurfaceValidationError("FCF-002 unreachable statement")
        if isinstance(statement, IfStatementNode):
            _validate_function_control_flow(statement.body)
            for branch in statement.elif_branches:
                _validate_function_control_flow(branch.body)
            if statement.else_branch is not None:
                _validate_function_control_flow(statement.else_branch.body)
        elif isinstance(statement, MatchStatementNode):
            for arm in statement.arms:
                _validate_function_control_flow(arm.body)
        elif isinstance(statement, (ForStatementNode, WhileStatementNode, LoopStatementNode)):
            _validate_function_control_flow(statement.body)
        if _statement_terminates_with_return(statement):
            reachable = False


def _validate_calculation_expression(
    expression: ExpressionNode,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    def visit(value: Any, *, callee: bool = False) -> None:
        if isinstance(value, IdentifierNode):
            imported = None
            if (
                value.name not in bindings
                and value.name not in symbols
                and _CURRENT_NAMESPACE is not None
            ):
                imported = _CURRENT_NAMESPACE.imported(value.name)
            if (
                not callee
                and value.name not in bindings
                and value.name not in symbols
                and imported is None
            ):
                if _is_unqualified_enum_variant(value.name, symbols):
                    raise SurfaceValidationError(
                        "ESR-003 enum variants must be qualified"
                    )
                raise SurfaceValidationError(
                    f"CAL-020 undefined variable: {value.name}"
                )
        elif isinstance(value, QualifiedIdentifierNode):
            if _CURRENT_NAMESPACE is None:
                raise SurfaceValidationError("NS-V005 namespace is unavailable")
            _CURRENT_NAMESPACE.resolve_qualified(value)
        elif isinstance(value, RuntimeNamespaceNode):
            raise SurfaceValidationError("RV-3 RuntimeNamespaceCannotBeShadowed")
        elif isinstance(value, RuntimeCallExpressionNode):
            _validate_runtime_call(value)
            for argument in value.arguments:
                visit(argument)
            _validate_runtime_reasoning_argument(value, symbols)
        elif isinstance(value, UnaryExpressionNode):
            visit(value.operand)
        elif isinstance(
            value,
            (
                BinaryExpressionNode,
                ComparisonExpressionNode,
                LogicalExpressionNode,
            ),
        ):
            visit(value.left)
            visit(value.right)
        elif isinstance(value, ParenthesizedExpressionNode):
            visit(value.expression)
        elif isinstance(value, SomeExpressionNode):
            visit(value.value)
        elif isinstance(value, MemberAccessNode):
            if isinstance(value.object, RuntimeNamespaceNode):
                raise SurfaceValidationError("RV-4 UnknownRuntimeMethod")
            enum_reference = _enum_variant_reference(value, symbols)
            if enum_reference is not None:
                return
            parts = _member_access_parts(value)
            if (
                len(parts) == 2
                and parts[0] not in bindings
                and parts[0] not in symbols
                and _looks_like_type_name(parts[0])
            ):
                raise SurfaceValidationError("ESR-002 unknown enum")
            if (
                len(parts) >= 2
                and parts[0] not in bindings
                and parts[0] not in symbols
                and _CURRENT_NAMESPACE is not None
            ):
                _CURRENT_NAMESPACE.resolve_qualified(
                    QualifiedIdentifierNode(tuple(parts[:-1]), parts[-1])
                )
                return
            visit(value.object)
        elif isinstance(value, CallExpressionNode):
            visit(value.callee, callee=True)
            for argument in value.arguments:
                visit(argument)
        elif isinstance(value, StructLiteralNode):
            for field in value.fields:
                visit(field.expression.expression)
        elif isinstance(value, (ArrayLiteralNode, TupleLiteralNode, SetLiteralNode)):
            for element in value.elements:
                visit(element.expression)
        elif isinstance(value, MapLiteralNode):
            for entry in value.entries:
                visit(entry.key.expression)
                visit(entry.value.expression)
        elif isinstance(value, IndexAccessNode):
            visit(value.collection)
            visit(value.index)

    _expression(expression, "CAL-V006 expression")
    visit(expression.expression)
    _expression_type(expression.expression, symbols, bindings)


def _member_access_parts(value: Any) -> tuple[str, ...]:
    if isinstance(value, IdentifierNode):
        return (value.name,)
    if isinstance(value, MemberAccessNode):
        parts = _member_access_parts(value.object)
        if parts:
            return (*parts, value.member)
    return ()


def _validate_runtime_call(value: RuntimeCallExpressionNode) -> None:
    if value.namespace.name != "runtime":
        raise SurfaceValidationError("RV-1 ReservedRuntimeNamespace")
    supported = {
        "input": RuntimeCallKind.INPUT,
        "print": RuntimeCallKind.PRINT,
        "search": RuntimeCallKind.SEARCH,
        "simulate": RuntimeCallKind.SIMULATION,
        "predict": RuntimeCallKind.PREDICTION,
        "plan": RuntimeCallKind.PLANNING,
    }
    if supported.get(value.method) != value.kind:
        raise SurfaceValidationError("RV-4 UnknownRuntimeMethod")
    expected_arguments = {
        RuntimeCallKind.INPUT: 0,
        RuntimeCallKind.PRINT: 1,
        RuntimeCallKind.SEARCH: 1,
        RuntimeCallKind.SIMULATION: 1,
        RuntimeCallKind.PREDICTION: 1,
        RuntimeCallKind.PLANNING: 1,
    }[value.kind]
    if len(value.arguments) != expected_arguments:
        raise SurfaceValidationError("RV-5 RuntimeCallArgumentCountMismatch")


def _validate_runtime_reasoning_argument(
    value: RuntimeCallExpressionNode, symbols: dict[str, Any]
) -> None:
    if value.kind in {RuntimeCallKind.INPUT, RuntimeCallKind.PRINT}:
        return
    argument = value.arguments[0]
    declaration: Any | None = None
    if isinstance(argument, IdentifierNode):
        declaration = symbols.get(argument.name)
    elif isinstance(argument, QualifiedIdentifierNode) and _CURRENT_NAMESPACE is not None:
        try:
            declaration = _CURRENT_NAMESPACE.resolve_qualified(argument).node
        except NamespaceResolutionError as error:
            raise SurfaceValidationError(str(error)) from error
    if declaration is None:
        return
    allowed = {
        RuntimeCallKind.SEARCH: (
            GoalNode,
            StateDeclarationNode,
            ConstraintNode,
            ReasonGraphDeclarationNode,
        ),
        RuntimeCallKind.SIMULATION: (
            ExecutionPlanDeclarationNode,
            ReasonGraphDeclarationNode,
        ),
        RuntimeCallKind.PREDICTION: (
            StateDeclarationNode,
            ReasonGraphDeclarationNode,
        ),
        RuntimeCallKind.PLANNING: (
            GoalNode,
            ConstraintNode,
            ReasonGraphDeclarationNode,
        ),
    }[value.kind]
    if not isinstance(declaration, allowed):
        raise SurfaceValidationError("RuntimeReasoningTypeMismatch")


_UNKNOWN_TYPE = object()


def _expression_type(
    value: Any,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> Any:
    if isinstance(value, IntegerLiteralNode):
        return PrimitiveTypeNode(PrimitiveKind.INT)
    if isinstance(value, FloatLiteralNode):
        return PrimitiveTypeNode(PrimitiveKind.FLOAT)
    if isinstance(value, BooleanLiteralNode):
        return PrimitiveTypeNode(PrimitiveKind.BOOL)
    if isinstance(value, StringLiteralNode):
        return PrimitiveTypeNode(PrimitiveKind.STRING)
    if isinstance(value, NullLiteralNode):
        return PrimitiveTypeNode(PrimitiveKind.NULL)
    if isinstance(value, NoneLiteralNode):
        return OptionalTypeNode(_UNKNOWN_TYPE)
    if isinstance(value, RuntimeCallExpressionNode):
        _validate_runtime_call(value)
        if value.kind == RuntimeCallKind.INPUT:
            return NamedTypeNode("InputState")
        if value.kind == RuntimeCallKind.PRINT:
            return NamedTypeNode("OutputEvent")
        inner = {
            RuntimeCallKind.SEARCH: "SearchResult",
            RuntimeCallKind.SIMULATION: "SimulationResult",
            RuntimeCallKind.PREDICTION: "PredictionResult",
            RuntimeCallKind.PLANNING: "PlanningResult",
        }[value.kind]
        return OptionalTypeNode(NamedTypeNode(inner))
    if isinstance(value, RuntimeNamespaceNode):
        raise SurfaceValidationError("RV-3 RuntimeNamespaceCannotBeShadowed")
    if isinstance(value, SomeExpressionNode):
        return OptionalTypeNode(_expression_type(value.value, symbols, bindings))
    if isinstance(value, IdentifierNode):
        if value.name in bindings:
            binding = bindings[value.name]
            return binding.type_node if isinstance(binding, _Binding) else binding
        declaration = symbols.get(value.name)
        if declaration is None and _CURRENT_NAMESPACE is not None:
            imported = _CURRENT_NAMESPACE.imported(value.name)
            declaration = imported.node if imported is not None else None
        state_kind = {
            ConceptNode: StateKind.CONCEPT,
            ObjectNode: StateKind.OBJECT,
            EventNode: StateKind.EVENT,
            ActionNode: StateKind.ACTION,
            GoalNode: StateKind.GOAL,
            ConstraintNode: StateKind.CONSTRAINT,
        }.get(type(declaration))
        return StateTypeNode(state_kind) if state_kind is not None else _UNKNOWN_TYPE
    if isinstance(value, QualifiedIdentifierNode):
        if _CURRENT_NAMESPACE is None:
            return _UNKNOWN_TYPE
        symbol = _CURRENT_NAMESPACE.resolve_qualified(value)
        declaration = symbol.node
        state_kind = {
            ConceptNode: StateKind.CONCEPT,
            ObjectNode: StateKind.OBJECT,
            EventNode: StateKind.EVENT,
            ActionNode: StateKind.ACTION,
            GoalNode: StateKind.GOAL,
            ConstraintNode: StateKind.CONSTRAINT,
        }.get(type(declaration))
        return StateTypeNode(state_kind) if state_kind is not None else _UNKNOWN_TYPE
    if isinstance(value, StructLiteralNode):
        _validate_struct_literal(value, symbols, bindings)
        return NamedTypeNode(value.type_name)
    if isinstance(value, ArrayLiteralNode):
        return ArrayTypeNode(_homogeneous_type(value.elements, symbols, bindings, "CV5-1"))
    if isinstance(value, TupleLiteralNode):
        return TupleTypeNode(
            tuple(_expression_type(item.expression, symbols, bindings) for item in value.elements)
        )
    if isinstance(value, SetLiteralNode):
        _validate_set_literal(value, symbols, bindings)
        return SetTypeNode(_homogeneous_type(value.elements, symbols, bindings, "CV5-3"))
    if isinstance(value, MapLiteralNode):
        _validate_map_literal(value, symbols, bindings)
        if not value.entries:
            return MapTypeNode(_UNKNOWN_TYPE, _UNKNOWN_TYPE)
        key_type = _homogeneous_type(
            tuple(entry.key for entry in value.entries), symbols, bindings, "CV5-4"
        )
        value_type = _homogeneous_type(
            tuple(entry.value for entry in value.entries), symbols, bindings, "CV5-10"
        )
        return MapTypeNode(key_type, value_type)
    if isinstance(value, ParenthesizedExpressionNode):
        return _expression_type(value.expression, symbols, bindings)
    if isinstance(value, UnaryExpressionNode):
        operand = _expression_type(value.operand, symbols, bindings)
        if isinstance(operand, OptionalTypeNode):
            raise SurfaceValidationError("OV-4 CannotUseOptionalAsValue")
        expected = (
            PrimitiveTypeNode(PrimitiveKind.BOOL)
            if value.operator == UnaryOperator.NOT
            else None
        )
        if expected is not None and operand is not _UNKNOWN_TYPE and operand != expected:
            raise SurfaceValidationError("TYPE-V006 logical operand must be Bool")
        if value.operator == UnaryOperator.NEGATE:
            if operand is not _UNKNOWN_TYPE and operand not in {
                PrimitiveTypeNode(PrimitiveKind.INT),
                PrimitiveTypeNode(PrimitiveKind.FLOAT),
            }:
                raise SurfaceValidationError(
                    "TYPE-V004 arithmetic operand must be Int or Float"
                )
        return operand
    if isinstance(value, BinaryExpressionNode):
        left = _expression_type(value.left, symbols, bindings)
        right = _expression_type(value.right, symbols, bindings)
        if isinstance(left, OptionalTypeNode) or isinstance(right, OptionalTypeNode):
            raise SurfaceValidationError("OV-4 CannotUseOptionalAsValue")
        if left is _UNKNOWN_TYPE or right is _UNKNOWN_TYPE:
            return _UNKNOWN_TYPE
        numeric = {
            PrimitiveTypeNode(PrimitiveKind.INT),
            PrimitiveTypeNode(PrimitiveKind.FLOAT),
        }
        if left not in numeric or right not in numeric or left != right:
            raise SurfaceValidationError(
                "TYPE-V004 TYPE-001 mixed or non-numeric arithmetic invalid"
            )
        return left
    if isinstance(value, ComparisonExpressionNode):
        left = _expression_type(value.left, symbols, bindings)
        right = _expression_type(value.right, symbols, bindings)
        if isinstance(left, OptionalTypeNode) or isinstance(right, OptionalTypeNode):
            if value.operator in {
                ComparisonOperator.EQUAL,
                ComparisonOperator.NOT_EQUAL,
            } and _types_compatible(left, right):
                return PrimitiveTypeNode(PrimitiveKind.BOOL)
            raise SurfaceValidationError("OV-4 CannotUseOptionalAsValue")
        if left is _UNKNOWN_TYPE or right is _UNKNOWN_TYPE:
            return PrimitiveTypeNode(PrimitiveKind.BOOL)
        if left != right:
            raise SurfaceValidationError(
                "TYPE-V005 comparison operands must have the same type"
            )
        numeric = {
            PrimitiveTypeNode(PrimitiveKind.INT),
            PrimitiveTypeNode(PrimitiveKind.FLOAT),
        }
        if value.operator not in {
            ComparisonOperator.EQUAL,
            ComparisonOperator.NOT_EQUAL,
        } and left not in numeric:
            raise SurfaceValidationError(
                "CV-2 comparison operands must be comparable"
            )
        return PrimitiveTypeNode(PrimitiveKind.BOOL)
    if isinstance(value, LogicalExpressionNode):
        bool_type = PrimitiveTypeNode(PrimitiveKind.BOOL)
        left = _expression_type(value.left, symbols, bindings)
        right = _expression_type(value.right, symbols, bindings)
        if isinstance(left, OptionalTypeNode) or isinstance(right, OptionalTypeNode):
            raise SurfaceValidationError("OV-4 CannotUseOptionalAsValue")
        if any(item is not _UNKNOWN_TYPE and item != bool_type for item in (left, right)):
            raise SurfaceValidationError("TYPE-V006 logical operands must be Bool")
        return bool_type
    if isinstance(value, MemberAccessNode):
        enum_type = _enum_value_type(value, symbols)
        if enum_type is not None:
            return enum_type
        object_type = _expression_type(value.object, symbols, bindings)
        if isinstance(object_type, TupleTypeNode) and value.member.isdigit():
            index = int(value.member)
            if index >= len(object_type.element_types):
                raise SurfaceValidationError("CV5-2 tuple index out of range")
            return object_type.element_types[index]
        if isinstance(object_type, (ArrayTypeNode, SetTypeNode, MapTypeNode, TupleTypeNode)) and value.member == "length":
            return PrimitiveTypeNode(PrimitiveKind.INT)
        if isinstance(object_type, NamedTypeNode):
            struct = symbols.get(object_type.name)
            if isinstance(struct, StructDeclarationNode):
                field_type = _struct_field_type(struct, value.member)
                if field_type is None:
                    raise SurfaceValidationError(
                        f"TV-9 unknown field {value.member} on {object_type.name}"
                    )
                return field_type
        if object_type is _UNKNOWN_TYPE:
            return _UNKNOWN_TYPE
        if isinstance(object_type, OptionalTypeNode):
            raise SurfaceValidationError("OV-4 CannotUseOptionalAsValue")
        raise SurfaceValidationError("TV-9 field access requires valid field")
    if isinstance(value, IndexAccessNode):
        collection_type = _expression_type(value.collection, symbols, bindings)
        index_type = _expression_type(value.index, symbols, bindings)
        if isinstance(collection_type, OptionalTypeNode):
            raise SurfaceValidationError("OV-4 CannotUseOptionalAsValue")
        if isinstance(collection_type, ArrayTypeNode):
            if index_type != PrimitiveTypeNode(PrimitiveKind.INT):
                raise SurfaceValidationError("CV5-6 index expression must be int")
            return collection_type.element_type
        if isinstance(collection_type, MapTypeNode):
            _require_map_key_type(index_type)
            _require_type_equal(collection_type.key_type, index_type, "CV5-8 map key mismatch")
            return collection_type.value_type
        if collection_type is _UNKNOWN_TYPE:
            return _UNKNOWN_TYPE
        raise SurfaceValidationError("CV5-7 index access requires collection type")
    if isinstance(value, CallExpressionNode):
        if isinstance(value.callee, IdentifierNode):
            if value.callee.name == _CURRENT_FUNCTION:
                raise SurfaceValidationError("FN-007 recursive function calls are rejected")
            function = symbols.get(value.callee.name)
            if isinstance(function, FunctionDeclarationNode):
                if len(value.arguments) != len(function.parameters):
                    raise SurfaceValidationError(
                        f"FN-005 function argument count mismatch: {value.callee.name}"
                    )
                for argument, parameter in zip(value.arguments, function.parameters):
                    expected_type = _function_parameter_type(parameter)
                    argument_expression = (
                        argument if isinstance(argument, ExpressionNode) else ExpressionNode(argument)
                    )
                    actual_type = _expression_type(
                        argument_expression.expression,
                        symbols,
                        bindings,
                    )
                    if expected_type is not None:
                        _require_compatible(
                            expected_type,
                            actual_type,
                            argument_expression,
                            symbols,
                            "FN-005 function argument mismatch",
                        )
                return function.return_type or _UNKNOWN_TYPE
        return _UNKNOWN_TYPE
    return _UNKNOWN_TYPE


def _require_compatible(
    expected: Any,
    actual: Any,
    expression: ExpressionNode,
    symbols: dict[str, Any],
    location: str,
) -> None:
    if expected == actual:
        return
    if isinstance(expected, OptionalTypeNode):
        if isinstance(actual, OptionalTypeNode):
            _require_type_equal(expected.inner_type, actual.inner_type, location)
            return
        if actual is _UNKNOWN_TYPE:
            return
        raise SurfaceValidationError(
            f"OV-3 OptionalAssignmentTypeMismatch: expected {_type_name(expected)}, received {_type_name(actual)}"
        )
    if isinstance(actual, OptionalTypeNode):
        raise SurfaceValidationError("OV-4 CannotUseOptionalAsValue")
    if isinstance(expected, ArrayTypeNode) and isinstance(actual, ArrayTypeNode):
        _require_type_equal(expected.element_type, actual.element_type, location)
        return
    if isinstance(expected, SetTypeNode) and isinstance(actual, SetTypeNode):
        _require_type_equal(expected.element_type, actual.element_type, location)
        return
    if isinstance(expected, TupleTypeNode) and isinstance(actual, TupleTypeNode):
        if len(expected.element_types) != len(actual.element_types):
            raise SurfaceValidationError("CV5-2 tuple size mismatch")
        for left, right in zip(expected.element_types, actual.element_types):
            _require_type_equal(left, right, location)
        return
    if isinstance(expected, MapTypeNode) and isinstance(actual, MapTypeNode):
        _require_type_equal(expected.key_type, actual.key_type, location)
        _require_type_equal(expected.value_type, actual.value_type, location)
        return
    if isinstance(expected, StateTypeNode):
        value = expression.expression
        if isinstance(value, IdentifierNode):
            declaration = symbols.get(value.name)
            expected_node = {
                StateKind.CONCEPT: ConceptNode,
                StateKind.OBJECT: ObjectNode,
                StateKind.EVENT: EventNode,
                StateKind.ACTION: ActionNode,
                StateKind.ATTRIBUTE: AttributeNode,
                StateKind.GOAL: GoalNode,
                StateKind.CONSTRAINT: ConstraintNode,
            }[expected.kind]
            if isinstance(declaration, expected_node):
                return
            if declaration is None:
                raise SurfaceValidationError(
                    f"TYPE-V002 unresolved typed reference: {value.name}"
                )
            if expected.kind == StateKind.GOAL:
                raise SurfaceValidationError(
                    f"TYPE-V007 TYPE-011 Goal type integrity failed: {value.name}"
                )
            if expected.kind == StateKind.CONSTRAINT:
                raise SurfaceValidationError(
                    f"TYPE-V008 TYPE-010 Constraint type integrity failed: {value.name}"
                )
    if actual is _UNKNOWN_TYPE:
        return
    if actual == PrimitiveTypeNode(PrimitiveKind.NULL):
        return
    raise SurfaceValidationError(
        f"{location}: expected {_type_name(expected)}, received {_type_name(actual)}"
    )


def _validate_type_node(value: Any) -> None:
    if isinstance(value, PrimitiveTypeNode):
        if not isinstance(value.kind, PrimitiveKind):
            raise SurfaceValidationError("TYPE-V001 unknown primitive type")
        return
    if isinstance(value, StateTypeNode):
        if not isinstance(value.kind, StateKind):
            raise SurfaceValidationError("TYPE-V001 unknown state type")
        return
    if isinstance(value, NamedTypeNode):
        _identifier(value.name, "TV-4 NamedTypeNode.name")
        return
    if isinstance(value, OptionalTypeNode):
        _validate_type_node(value.inner_type)
        return
    if isinstance(value, ArrayTypeNode):
        _validate_type_node(value.element_type)
        return
    if isinstance(value, TupleTypeNode):
        if not value.element_types:
            raise SurfaceValidationError("CV5-2 tuple type requires elements")
        for element_type in value.element_types:
            _validate_type_node(element_type)
        return
    if isinstance(value, SetTypeNode):
        _validate_type_node(value.element_type)
        return
    if isinstance(value, MapTypeNode):
        _validate_type_node(value.key_type)
        _validate_type_node(value.value_type)
        return
    raise SurfaceValidationError("TYPE-V002 invalid TypeNode")


def _type_name(value: Any) -> str:
    if isinstance(value, (PrimitiveTypeNode, StateTypeNode)):
        return value.kind.value
    if isinstance(value, NamedTypeNode):
        return value.name
    if isinstance(value, OptionalTypeNode):
        return f"optional<{_type_name(value.inner_type)}>"
    if isinstance(value, ArrayTypeNode):
        return f"[{_type_name(value.element_type)}]"
    if isinstance(value, TupleTypeNode):
        return f"({', '.join(_type_name(item) for item in value.element_types)})"
    if isinstance(value, SetTypeNode):
        return f"set<{_type_name(value.element_type)}>"
    if isinstance(value, MapTypeNode):
        return f"map<{_type_name(value.key_type)},{_type_name(value.value_type)}>"
    return "Unknown"


def _require_bool_condition(
    expression: ExpressionNode,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    expression_type = _expression_type(expression.expression, symbols, bindings)
    bool_type = PrimitiveTypeNode(PrimitiveKind.BOOL)
    if expression_type is _UNKNOWN_TYPE or expression_type != bool_type:
        raise SurfaceValidationError("CV-1 ConditionMustBeBoolean")


def _require_function_bool_condition(
    expression: ExpressionNode,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    try:
        _require_bool_condition(expression, symbols, bindings)
    except SurfaceValidationError as error:
        if "ConditionMustBeBoolean" in str(error):
            raise SurfaceValidationError("FCF-004 condition must be Bool") from error
        raise


def _require_iterable(
    expression: ExpressionNode,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    expression_type = _expression_type(expression.expression, symbols, bindings)
    if isinstance(expression_type, (ArrayTypeNode, SetTypeNode, MapTypeNode)):
        return
    if expression_type is _UNKNOWN_TYPE:
        return
    if isinstance(expression_type, PrimitiveTypeNode) or isinstance(
        expression_type, (NamedTypeNode, TupleTypeNode)
    ):
        raise SurfaceValidationError("IV-8 iteration source must be iterable")


def _homogeneous_type(
    elements: tuple[ExpressionNode, ...],
    symbols: dict[str, Any],
    bindings: dict[str, Any],
    code: str,
) -> Any:
    if not elements:
        return _UNKNOWN_TYPE
    first = _expression_type(elements[0].expression, symbols, bindings)
    for element in elements[1:]:
        current = _expression_type(element.expression, symbols, bindings)
        if first is _UNKNOWN_TYPE:
            first = current
            continue
        if current is not _UNKNOWN_TYPE and not _types_compatible(first, current):
            raise SurfaceValidationError(f"{code} collection element type mismatch")
        first = _merge_type(first, current)
    return first


def _merge_type(left: Any, right: Any) -> Any:
    if left is _UNKNOWN_TYPE:
        return right
    if right is _UNKNOWN_TYPE:
        return left
    if isinstance(left, OptionalTypeNode) and isinstance(right, OptionalTypeNode):
        return OptionalTypeNode(_merge_type(left.inner_type, right.inner_type))
    return left


def _contains_none_literal(value: Any) -> bool:
    if isinstance(value, NoneLiteralNode):
        return True
    if is_dataclass(value) and not isinstance(value, type):
        return any(_contains_none_literal(getattr(value, field.name)) for field in fields(value))
    if isinstance(value, (tuple, list)):
        return any(_contains_none_literal(item) for item in value)
    return False


def _contains_uncontextual_none_literal(
    value: Any,
    symbols: dict[str, Any] | None = None,
) -> bool:
    if isinstance(value, NoneLiteralNode):
        return True
    if (
        symbols is not None
        and isinstance(value, CallExpressionNode)
        and isinstance(value.callee, IdentifierNode)
    ):
        function = symbols.get(value.callee.name)
        if isinstance(function, FunctionDeclarationNode):
            for argument, parameter in zip(value.arguments, function.parameters):
                expected_type = _function_parameter_type(parameter)
                argument_value = (
                    argument.expression if isinstance(argument, ExpressionNode) else argument
                )
                if isinstance(argument_value, NoneLiteralNode) and isinstance(
                    expected_type,
                    OptionalTypeNode,
                ):
                    continue
                if _contains_uncontextual_none_literal(argument_value, symbols):
                    return True
            return False
    if isinstance(value, StructLiteralNode):
        return False
    if is_dataclass(value) and not isinstance(value, type):
        return any(
            _contains_uncontextual_none_literal(getattr(value, field.name), symbols)
            for field in fields(value)
        )
    if isinstance(value, (tuple, list)):
        return any(_contains_uncontextual_none_literal(item, symbols) for item in value)
    return False


def _literal_key(value: ExpressionNode) -> Any:
    expression = value.expression
    if isinstance(expression, (IntegerLiteralNode, FloatLiteralNode, BooleanLiteralNode, StringLiteralNode)):
        return (type(expression).__name__, expression.value)
    if isinstance(expression, MemberAccessNode) and isinstance(expression.object, IdentifierNode):
        return ("enum", expression.object.name, expression.member)
    return None


def _validate_set_literal(
    value: SetLiteralNode,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    keys = [_literal_key(element) for element in value.elements]
    known = [key for key in keys if key is not None]
    if len(known) != len(set(known)):
        raise SurfaceValidationError("CV5-3 DuplicateSetElement")
    for element in value.elements:
        _require_hashable_type(_expression_type(element.expression, symbols, bindings))


def _validate_map_literal(
    value: MapLiteralNode,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    keys = [_literal_key(entry.key) for entry in value.entries]
    known = [key for key in keys if key is not None]
    if len(known) != len(set(known)):
        raise SurfaceValidationError("CV5-5 duplicate map key")
    for entry in value.entries:
        _require_map_key_type(_expression_type(entry.key.expression, symbols, bindings))


def _require_hashable_type(value: Any) -> None:
    if value is _UNKNOWN_TYPE:
        return
    if isinstance(value, PrimitiveTypeNode):
        return
    if isinstance(value, NamedTypeNode):
        declaration = _CURRENT_NAMESPACE.symbols.get(value.name).node if _CURRENT_NAMESPACE and value.name in _CURRENT_NAMESPACE.symbols else None
        if isinstance(declaration, EnumDeclarationNode):
            return
    raise SurfaceValidationError("CV5-3 set elements must be hashable")


def _require_map_key_type(value: Any) -> None:
    if value is _UNKNOWN_TYPE:
        return
    if isinstance(value, PrimitiveTypeNode):
        return
    if isinstance(value, NamedTypeNode):
        declaration = _CURRENT_NAMESPACE.symbols.get(value.name).node if _CURRENT_NAMESPACE and value.name in _CURRENT_NAMESPACE.symbols else None
        if isinstance(declaration, EnumDeclarationNode):
            return
    raise SurfaceValidationError("CV5-4 map keys must be valid key types")


def _require_type_equal(expected: Any, actual: Any, location: str) -> None:
    if expected is _UNKNOWN_TYPE or actual is _UNKNOWN_TYPE or expected == actual:
        return
    if isinstance(expected, OptionalTypeNode) and isinstance(actual, OptionalTypeNode):
        _require_type_equal(expected.inner_type, actual.inner_type, location)
        return
    if isinstance(expected, ArrayTypeNode) and isinstance(actual, ArrayTypeNode):
        _require_type_equal(expected.element_type, actual.element_type, location)
        return
    if isinstance(expected, SetTypeNode) and isinstance(actual, SetTypeNode):
        _require_type_equal(expected.element_type, actual.element_type, location)
        return
    if isinstance(expected, MapTypeNode) and isinstance(actual, MapTypeNode):
        _require_type_equal(expected.key_type, actual.key_type, location)
        _require_type_equal(expected.value_type, actual.value_type, location)
        return
    if isinstance(expected, TupleTypeNode) and isinstance(actual, TupleTypeNode):
        if len(expected.element_types) != len(actual.element_types):
            raise SurfaceValidationError("CV5-2 tuple size mismatch")
        for left, right in zip(expected.element_types, actual.element_types):
            _require_type_equal(left, right, location)
        return
    raise SurfaceValidationError(
        f"{location}: expected {_type_name(expected)}, received {_type_name(actual)}"
    )


def _types_compatible(left: Any, right: Any) -> bool:
    if left is _UNKNOWN_TYPE or right is _UNKNOWN_TYPE or left == right:
        return True
    if isinstance(left, OptionalTypeNode) and isinstance(right, OptionalTypeNode):
        return _types_compatible(left.inner_type, right.inner_type)
    if isinstance(left, ArrayTypeNode) and isinstance(right, ArrayTypeNode):
        return _types_compatible(left.element_type, right.element_type)
    if isinstance(left, SetTypeNode) and isinstance(right, SetTypeNode):
        return _types_compatible(left.element_type, right.element_type)
    if isinstance(left, MapTypeNode) and isinstance(right, MapTypeNode):
        return _types_compatible(left.key_type, right.key_type) and _types_compatible(
            left.value_type, right.value_type
        )
    if isinstance(left, TupleTypeNode) and isinstance(right, TupleTypeNode):
        return len(left.element_types) == len(right.element_types) and all(
            _types_compatible(left_item, right_item)
            for left_item, right_item in zip(left.element_types, right.element_types)
        )
    return False


def _resolve_type(value: Any, symbols: dict[str, Any]) -> None:
    if isinstance(value, (PrimitiveTypeNode, StateTypeNode)):
        return
    if isinstance(value, NamedTypeNode):
        if value.name in RUNTIME_RESULT_TYPES:
            return
        declaration = symbols.get(value.name)
        if not isinstance(declaration, (StructDeclarationNode, EnumDeclarationNode)):
            raise SurfaceValidationError(
                f"TYPE-V001 TV-4 unresolved composite type: {value.name}"
            )
        return
    if isinstance(value, OptionalTypeNode):
        _resolve_type(value.inner_type, symbols)
        return
    if isinstance(value, ArrayTypeNode):
        _resolve_type(value.element_type, symbols)
        return
    if isinstance(value, TupleTypeNode):
        for element_type in value.element_types:
            _resolve_type(element_type, symbols)
        return
    if isinstance(value, SetTypeNode):
        _resolve_type(value.element_type, symbols)
        _require_hashable_type(value.element_type)
        return
    if isinstance(value, MapTypeNode):
        _resolve_type(value.key_type, symbols)
        _resolve_type(value.value_type, symbols)
        _require_map_key_type(value.key_type)
        return
    raise SurfaceValidationError("TYPE-V002 invalid TypeNode")


def _reject_indirect_struct_recursion(
    node: StructDeclarationNode,
    symbols: dict[str, Any],
) -> None:
    def visit(type_name: str, seen: set[str]) -> bool:
        target = symbols.get(type_name)
        if not isinstance(target, StructDeclarationNode):
            return False
        for field in target.fields:
            if isinstance(field.field_type, NamedTypeNode):
                if field.field_type.name == node.name:
                    return True
                if field.field_type.name not in seen and visit(
                    field.field_type.name,
                    seen | {field.field_type.name},
                ):
                    return True
        return False

    for field in node.fields:
        if isinstance(field.field_type, NamedTypeNode) and visit(
            field.field_type.name,
            {node.name, field.field_type.name},
        ):
            raise SurfaceValidationError("TV-8 RecursiveStructDefinition")


def _validate_struct_literal(
    value: StructLiteralNode,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    declaration = symbols.get(value.type_name)
    if not isinstance(declaration, StructDeclarationNode):
        raise SurfaceValidationError(f"TV-4 unknown struct type: {value.type_name}")
    expected = {field.name: field for field in declaration.fields}
    actual = {field.name: field for field in value.fields}
    if len(actual) != len(value.fields):
        raise SurfaceValidationError("TV-6 duplicate struct literal field")
    missing = set(expected) - set(actual)
    if missing:
        raise SurfaceValidationError(
            f"TV-5 MissingFieldInitialization: {sorted(missing)[0]}"
        )
    unknown = set(actual) - set(expected)
    if unknown:
        raise SurfaceValidationError(f"TV-6 unknown field: {sorted(unknown)[0]}")
    for name, field in actual.items():
        _require_compatible(
            expected[name].field_type,
            _expression_type(field.expression.expression, symbols, bindings),
            field.expression,
            symbols,
            "TYPE-V003 struct field mismatch",
        )


def _enum_value_type(value: MemberAccessNode, symbols: dict[str, Any]) -> Any:
    reference = _enum_variant_reference(value, symbols)
    if reference is None:
        return None
    return NamedTypeNode(reference["enum_name"])


def _enum_variant_reference(
    value: MemberAccessNode,
    symbols: dict[str, Any],
) -> dict[str, str] | None:
    if not isinstance(value.object, IdentifierNode):
        return None
    enum_name = value.object.name
    enum = symbols.get(enum_name)
    if enum is None:
        if _CURRENT_NAMESPACE is not None:
            try:
                imported = _CURRENT_NAMESPACE.imported(enum_name)
            except NamespaceResolutionError as error:
                raise SurfaceValidationError("PT-011 qualified symbol is ambiguous") from error
            if imported is not None and isinstance(imported.node, EnumDeclarationNode):
                enum = imported.node
        if isinstance(enum, EnumDeclarationNode):
            variants = {item.name for item in enum.values}
            if value.member not in variants:
                raise SurfaceValidationError(
                    "ESR-001 ESR-004 unknown enum variant"
                )
            return {
                "enum_name": enum_name,
                "variant_name": value.member,
                "qualified_name": f"{enum_name}.{value.member}",
            }
        if _looks_like_type_name(enum_name):
            raise SurfaceValidationError("ESR-002 unknown enum")
        return None
    if not isinstance(enum, EnumDeclarationNode):
        return None
    variants = {item.name for item in enum.values}
    if value.member not in variants:
        raise SurfaceValidationError(
            "ESR-001 ESR-004 unknown enum variant"
        )
    return {
        "enum_name": enum.name,
        "variant_name": value.member,
        "qualified_name": f"{enum.name}.{value.member}",
    }


def _is_unqualified_enum_variant(name: str, symbols: dict[str, Any]) -> bool:
    return any(
        isinstance(node, EnumDeclarationNode)
        and any(value.name == name for value in node.values)
        for node in symbols.values()
    )


def _looks_like_type_name(name: str) -> bool:
    return bool(name) and name[0].isupper()


def _struct_field_type(struct: StructDeclarationNode, field_name: str) -> Any:
    for field in struct.fields:
        if field.name == field_name:
            return field.field_type
    return None


def _validate_field_assignment(
    statement: FieldAssignmentStatementNode,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    target = statement.target.expression
    if not isinstance(target, MemberAccessNode):
        raise SurfaceValidationError("TV-10 field assignment target required")
    root = _member_root(target)
    if (
        root is None
        or root not in bindings
        or not isinstance(bindings[root], _Binding)
    ):
        raise SurfaceValidationError(f"TV-10 unknown field assignment target: {root}")
    if not bindings[root].mutable:
        raise SurfaceValidationError(f"TV-10 CannotModifyConstant: {root}")
    expected = _expression_type(target, symbols, bindings)
    actual = _expression_type(statement.expression.expression, symbols, bindings)
    _require_compatible(
        expected,
        actual,
        statement.expression,
        symbols,
        "TYPE-V003 field assignment mismatch",
    )


def _validate_index_assignment(
    statement: IndexAssignmentStatementNode,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    target = statement.target.expression
    if not isinstance(target, IndexAccessNode):
        raise SurfaceValidationError("CV5-9 index assignment target required")
    root = _member_root(target.collection)
    if (
        root is None
        or root not in bindings
        or not isinstance(bindings[root], _Binding)
    ):
        raise SurfaceValidationError(f"CV5-9 unknown collection assignment target: {root}")
    if not bindings[root].mutable:
        raise SurfaceValidationError(f"CV5-9 CannotModifyConstant: {root}")
    expected = _expression_type(target, symbols, bindings)
    actual = _expression_type(statement.expression.expression, symbols, bindings)
    _require_compatible(
        expected,
        actual,
        statement.expression,
        symbols,
        "TYPE-V003 collection assignment mismatch",
    )


def _member_root(value: Any) -> str | None:
    if isinstance(value, IndexAccessNode):
        return _member_root(value.collection)
    current = value
    while isinstance(current, MemberAccessNode):
        current = current.object
    return current.name if isinstance(current, IdentifierNode) else None


def _validate_enum_match_exhaustiveness(
    node: MatchStatementNode,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    enum_type = _expression_type(node.expression.expression, symbols, bindings)
    if not isinstance(enum_type, NamedTypeNode):
        return
    enum = symbols.get(enum_type.name)
    if not isinstance(enum, EnumDeclarationNode):
        return
    keys = {
        key
        for arm in node.arms
        if arm.guard is None
        for key in _pattern_keys(arm.pattern)
    }
    variants = {value.name for value in enum.values}
    for key in keys:
        if key[0] == "enum_value" and key[1] == enum.name and key[2] not in variants:
            raise SurfaceValidationError("ESR-001 ESR-004 unknown enum variant")
    if _match_has_default(keys):
        return
    matched: set[str] = set()
    for key in keys:
        if key[0] == "identifier":
            matched.add(key[1])
        elif key[0] == "enum_value" and key[1] == enum.name:
            matched.add(key[2])
        elif key[0] == "qualified" and key[1] == enum.name:
            matched.add(key[2])
    missing = [value.name for value in enum.values if value.name not in matched]
    if missing:
        missing_values = ", ".join(f"{enum.name}.{value}" for value in missing)
        raise SurfaceValidationError(
            f"TV-7 NonExhaustiveMatch Missing: {missing_values}"
        )


def _validate_match_patterns(
    node: MatchStatementNode,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    match_type = _expression_type(node.expression.expression, symbols, bindings)
    for arm in node.arms:
        for pattern_node in _pattern_alternatives(arm.pattern):
            _validate_match_pattern(pattern_node.pattern, match_type, symbols, bindings)


def _validate_match_pattern(
    pattern: Any,
    match_type: Any,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    if isinstance(pattern, LiteralPatternNode):
        literal_type = _expression_type(pattern.value, symbols, bindings)
        if (
            match_type is not _UNKNOWN_TYPE
            and literal_type is not _UNKNOWN_TYPE
            and not _types_compatible(match_type, literal_type)
        ):
            raise SurfaceValidationError("PT-005 literal type mismatch")
        return
    if isinstance(pattern, IdentifierPatternNode):
        _validate_identifier_pattern(pattern, match_type, symbols)
        return
    if isinstance(pattern, QualifiedPatternNode):
        _qualified_pattern_reference(pattern, symbols)
        return
    if isinstance(pattern, EnumValuePatternNode):
        return
    if isinstance(pattern, StructPatternNode):
        try:
            semantic = resolve_struct_pattern(pattern, symbols, _CURRENT_NAMESPACE)
            if not isinstance(match_type, NamedTypeNode):
                raise StructPatternSemanticError("SP-104 field type mismatch")
            if semantic.struct_symbol != match_type.name:
                raise StructPatternSemanticError("SP-104 field type mismatch")
        except StructPatternSemanticError as error:
            raise SurfaceValidationError(str(error)) from error
        return
    if isinstance(pattern, OptionalPatternNode):
        if not isinstance(match_type, OptionalTypeNode):
            code = "OPM-002" if pattern.kind == "Some" else "OPM-003"
            raise SurfaceValidationError(f"{code} optional pattern requires optional match value")
        return
    if isinstance(pattern, OptionalValuePatternNode):
        if not isinstance(match_type, OptionalTypeNode):
            raise SurfaceValidationError("OPM-002 optional pattern requires optional match value")
        _validate_match_pattern(pattern.pattern, match_type.inner_type, symbols, bindings)
        return


def _validate_identifier_pattern(
    pattern: IdentifierPatternNode,
    match_type: Any,
    symbols: dict[str, Any],
) -> None:
    if pattern.name == "default":
        return
    if match_type is _UNKNOWN_TYPE:
        return
    if isinstance(match_type, NamedTypeNode):
        enum = symbols.get(match_type.name)
        if isinstance(enum, EnumDeclarationNode):
            if pattern.name in {value.name for value in enum.values}:
                raise SurfaceValidationError("ESR-003 enum variants must be qualified")
            raise SurfaceValidationError("PT-004 undefined identifier pattern")
    if isinstance(match_type, OptionalTypeNode) and pattern.name in {"Some", "None"}:
        return
    declaration = symbols.get(pattern.name)
    if isinstance(declaration, ConstDeclarationNode):
        return
    raise SurfaceValidationError("PT-004 undefined identifier pattern")


def _qualified_pattern_reference(
    pattern: QualifiedPatternNode,
    symbols: dict[str, Any],
) -> dict[str, str]:
    enum_name = pattern.namespace
    enum = symbols.get(enum_name)
    symbol_id = f"{enum_name}.{pattern.identifier}"
    if not isinstance(enum, EnumDeclarationNode) and _CURRENT_NAMESPACE is not None:
        try:
            imported = _CURRENT_NAMESPACE.imported(enum_name)
        except NamespaceResolutionError as error:
            raise SurfaceValidationError("PT-011 qualified symbol is ambiguous") from error
        if imported is not None and isinstance(imported.node, EnumDeclarationNode):
            enum = imported.node
            enum_name = imported.name
            symbol_id = f"{imported.qualified_name}.{pattern.identifier}"
    if not isinstance(enum, EnumDeclarationNode):
        raise SurfaceValidationError("PT-009 undefined namespace")
    if pattern.identifier not in {value.name for value in enum.values}:
        raise SurfaceValidationError("PT-010 ESR-001 undefined enum variant")
    return {
        "enum_name": enum.name,
        "variant_name": pattern.identifier,
        "qualified_name": f"{enum.name}.{pattern.identifier}",
        "symbol_id": symbol_id,
    }


def _validate_optional_match_exhaustiveness(
    node: MatchStatementNode,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    optional_type = _expression_type(node.expression.expression, symbols, bindings)
    if not isinstance(optional_type, OptionalTypeNode):
        return
    keys = {
        key
        for arm in node.arms
        if arm.guard is None
        for key in _pattern_keys(arm.pattern)
    }
    if _match_has_default(keys):
        return
    matched = {key[1] for key in keys if key[0] in {"optional", "optional_value"}}
    matched.update(key[1] for key in keys if key[0] == "identifier" and key[1] in {"Some", "None"})
    if {"Some", "None"} - matched:
        raise SurfaceValidationError("OV-5 NonExhaustiveOptionalMatch")


def _validate_bool_match_exhaustiveness(
    node: MatchStatementNode,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    match_type = _expression_type(node.expression.expression, symbols, bindings)
    if match_type != PrimitiveTypeNode(PrimitiveKind.BOOL):
        return
    keys = {
        key
        for arm in node.arms
        if arm.guard is None
        for key in _pattern_keys(arm.pattern)
    }
    if _match_has_default(keys):
        return
    matched = {key[2] for key in keys if key[0] == "literal" and key[1] == "BooleanLiteralNode"}
    if matched != {True, False}:
        missing = ["true" if value else "false" for value in (True, False) if value not in matched]
        raise SurfaceValidationError(
            f"TV-7 NonExhaustiveMatch Missing: {', '.join(missing)}"
        )


def _validate_match_guard(
    arm: MatchArmNode,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    if arm.guard is None:
        return
    try:
        _validate_calculation_expression(arm.guard, symbols, bindings)
    except SurfaceValidationError as error:
        if "undefined variable" in str(error):
            raise SurfaceValidationError(str(error).replace("CAL-020", "PG-003")) from error
        raise
    guard_type = _expression_type(arm.guard.expression, symbols, bindings)
    if guard_type != PrimitiveTypeNode(PrimitiveKind.BOOL):
        raise SurfaceValidationError("PG-001 guard expression must be Bool")


def _validate_struct_match_exhaustiveness(
    node: MatchStatementNode,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    match_type = _expression_type(node.expression.expression, symbols, bindings)
    if not isinstance(match_type, NamedTypeNode):
        return
    struct = symbols.get(match_type.name)
    if not isinstance(struct, StructDeclarationNode):
        return
    keys = {
        key
        for arm in node.arms
        if arm.guard is None
        for key in _pattern_keys(arm.pattern)
    }
    if _match_has_default(keys):
        return
    for arm in node.arms:
        if arm.guard is not None:
            continue
        for pattern_node in _pattern_alternatives(arm.pattern):
            pattern = pattern_node.pattern
            if not isinstance(pattern, StructPatternNode):
                continue
            try:
                semantic = resolve_struct_pattern(pattern, symbols, _CURRENT_NAMESPACE)
            except StructPatternSemanticError as error:
                raise SurfaceValidationError(str(error)) from error
            if semantic.struct_symbol != struct.name:
                continue
            if _struct_pattern_is_exhaustive(pattern):
                return
    raise SurfaceValidationError("TV-8 NonExhaustiveStructMatch")


def _struct_pattern_is_exhaustive(pattern: StructPatternNode) -> bool:
    if not pattern.fields:
        return True
    return all(_struct_field_pattern_is_exhaustive(field.pattern) for field in pattern.fields)


def _struct_field_pattern_is_exhaustive(pattern: Any) -> bool:
    if isinstance(pattern, (StructBindingPatternNode, IdentifierPatternNode, WildcardPatternNode)):
        return True
    if isinstance(pattern, StructPatternNode):
        return _struct_pattern_is_exhaustive(pattern)
    if isinstance(pattern, OrPatternNode):
        return any(_struct_field_pattern_is_exhaustive(item) for item in pattern.alternatives)
    return False


def _match_arm_bindings(
    node: MatchStatementNode,
    pattern: PatternNode,
    symbols: dict[str, Any],
    bindings: dict[str, Any],
) -> dict[str, _Binding]:
    match_type = _expression_type(node.expression.expression, symbols, bindings)
    pattern_value = pattern.pattern
    if isinstance(pattern_value, OrPatternNode):
        alternatives = [
            _match_arm_bindings(node, PatternNode(alternative), symbols, bindings)
            for alternative in pattern_value.alternatives
        ]
        if not alternatives:
            return {}
        names = set(alternatives[0])
        if any(set(item) != names for item in alternatives[1:]):
            raise SurfaceValidationError("OP-002 IncompatibleBindingEnvironment")
        return alternatives[0]
    if (
        isinstance(match_type, OptionalTypeNode)
        and isinstance(pattern_value, OptionalPatternNode)
        and pattern_value.kind == "Some"
        and pattern_value.binding is not None
    ):
        return {pattern_value.binding: _Binding(match_type.inner_type, mutable=False)}
    if isinstance(pattern_value, StructPatternNode):
        return _struct_pattern_bindings(pattern_value, match_type, symbols)
    return {}


def _struct_pattern_bindings(
    pattern: StructPatternNode,
    match_type: Any,
    symbols: dict[str, Any],
) -> dict[str, _Binding]:
    if not isinstance(match_type, NamedTypeNode):
        return {}
    struct = symbols.get(match_type.name)
    if not isinstance(struct, StructDeclarationNode):
        return {}
    bindings: dict[str, _Binding] = {}
    field_types = {field.name: field.field_type for field in struct.fields}
    for field in pattern.fields:
        field_type = field_types.get(field.field_name)
        if field_type is None:
            continue
        field_pattern = field.pattern
        if isinstance(field_pattern, StructBindingPatternNode):
            bindings[field_pattern.binding] = _Binding(field_type, mutable=False)
        elif isinstance(field_pattern, IdentifierPatternNode):
            bindings[field_pattern.name] = _Binding(field_type, mutable=False)
        elif isinstance(field_pattern, StructPatternNode):
            bindings.update(_struct_pattern_bindings(field_pattern, field_type, symbols))
        elif isinstance(field_pattern, OrPatternNode):
            alternative_bindings = [
                _struct_pattern_field_bindings(alternative, field_type, symbols)
                for alternative in field_pattern.alternatives
            ]
            if alternative_bindings:
                names = set(alternative_bindings[0])
                if any(set(item) != names for item in alternative_bindings[1:]):
                    raise SurfaceValidationError("OP-002 IncompatibleBindingEnvironment")
                bindings.update(alternative_bindings[0])
    return bindings


def _struct_pattern_field_bindings(
    pattern: Any,
    field_type: Any,
    symbols: dict[str, Any],
) -> dict[str, _Binding]:
    if isinstance(pattern, StructBindingPatternNode):
        return {pattern.binding: _Binding(field_type, mutable=False)}
    if isinstance(pattern, IdentifierPatternNode):
        return {pattern.name: _Binding(field_type, mutable=False)}
    if isinstance(pattern, StructPatternNode):
        return _struct_pattern_bindings(pattern, field_type, symbols)
    return {}


def _match_has_default(keys: set[tuple[str, Any]]) -> bool:
    return any(key[0] in {"wildcard", "default"} for key in keys)


def _validate_node_types(value: Any) -> None:
    if is_dataclass(value) and not isinstance(value, type):
        if not isinstance(value, KNOWN_NODE_TYPES):
            raise SurfaceValidationError(
                f"AST-V001 unsupported node type: {type(value).__name__}"
            )
        for field in fields(value):
            _validate_node_types(getattr(value, field.name))
    elif isinstance(value, (tuple, list)):
        for item in value:
            _validate_node_types(item)


def _identifier(value: Any, location: str) -> None:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise SurfaceValidationError(f"{location} is not a valid identifier")
    if value in RESERVED_IDENTIFIERS:
        raise SurfaceValidationError(f"{location} is a reserved keyword: {value}")


def _qualified_identifier(value: Any, location: str) -> None:
    if not isinstance(value, str) or not QUALIFIED_IDENTIFIER.fullmatch(value):
        raise SurfaceValidationError(f"{location} is not a valid qualified identifier")
    for part in value.split("."):
        if part in RESERVED_IDENTIFIERS:
            raise SurfaceValidationError(f"{location} contains a reserved keyword: {part}")


def _expression(value: ExpressionNode, location: str) -> None:
    if not isinstance(value, ExpressionNode):
        raise SurfaceValidationError(f"{location} is required")
    _expression_value(value.expression)


def _expression_value(value: Any) -> None:
    if isinstance(value, IdentifierNode):
        _identifier(value.name, "EX-001 IdentifierNode.name")
    elif isinstance(value, RuntimeNamespaceNode):
        if value.name != "runtime":
            raise SurfaceValidationError("RV-1 ReservedRuntimeNamespace")
    elif isinstance(value, RuntimeCallExpressionNode):
        _validate_runtime_call(value)
        for argument in value.arguments:
            _expression_value(argument)
    elif isinstance(value, QualifiedIdentifierNode):
        if not value.path:
            raise SurfaceValidationError("NS-030 qualified path is required")
        for part in value.path:
            _identifier(part, "NS-V001 QualifiedIdentifierNode.path")
        _identifier(value.symbol, "NS-V001 QualifiedIdentifierNode.symbol")
        if value.resolved_name is not None and "::" not in value.resolved_name:
            raise SurfaceValidationError(
                "NS-V005 QualifiedIdentifierNode.resolved_name is invalid"
            )
    elif isinstance(value, IntegerLiteralNode):
        if (
            isinstance(value.value, bool)
            or not isinstance(value.value, int)
            or not -(2**63) <= value.value < 2**63
        ):
            raise SurfaceValidationError(
                "EX-V001 IntegerLiteralNode.value must fit int64"
            )
    elif isinstance(
        value, (BooleanLiteralNode, StringLiteralNode, NullLiteralNode, NoneLiteralNode)
    ):
        return
    elif isinstance(value, SomeExpressionNode):
        _expression_value(value.value)
    elif isinstance(value, FloatLiteralNode):
        if not isinstance(value.value, float) or not math.isfinite(value.value):
            raise SurfaceValidationError("EX-V001 FloatLiteralNode.value is invalid")
    elif isinstance(value, UnaryExpressionNode):
        if not isinstance(value.operator, UnaryOperator):
            raise SurfaceValidationError("EX-V002 invalid unary operator")
        _expression_value(value.operand)
    elif isinstance(value, BinaryExpressionNode):
        if not isinstance(value.operator, BinaryOperator):
            raise SurfaceValidationError("EX-V002 invalid binary operator")
        _expression_value(value.left)
        _expression_value(value.right)
    elif isinstance(value, ComparisonExpressionNode):
        if not isinstance(value.operator, ComparisonOperator):
            raise SurfaceValidationError("EX-V002 invalid comparison operator")
        _expression_value(value.left)
        _expression_value(value.right)
    elif isinstance(value, LogicalExpressionNode):
        if not isinstance(value.operator, LogicalOperator):
            raise SurfaceValidationError("EX-V002 invalid logical operator")
        _expression_value(value.left)
        _expression_value(value.right)
    elif isinstance(value, ParenthesizedExpressionNode):
        _expression_value(value.expression)
    elif isinstance(value, MemberAccessNode):
        _expression_value(value.object)
        if not value.member.isdigit():
            _identifier(value.member, "EX-V005 MemberAccessNode.member")
    elif isinstance(value, CallExpressionNode):
        _expression_value(value.callee)
        for argument in value.arguments:
            _expression_value(argument)
    elif isinstance(value, StructLiteralNode):
        _qualified_identifier(value.type_name, "TV-4 StructLiteralExpressionNode.type_name")
        names: set[str] = set()
        for field in value.fields:
            _expression_value(field)
            if field.name in names:
                raise SurfaceValidationError("TV-6 duplicate struct literal field")
            names.add(field.name)
    elif isinstance(value, StructLiteralFieldNode):
        _identifier(value.name, "TV-6 StructLiteralFieldNode.name")
        _expression(value.expression, "TV-6 StructLiteralFieldNode.expression")
    elif isinstance(value, (ArrayLiteralNode, TupleLiteralNode, SetLiteralNode)):
        for element in value.elements:
            _expression(element, f"{type(value).__name__}.element")
    elif isinstance(value, MapLiteralNode):
        for entry in value.entries:
            _expression_value(entry)
    elif isinstance(value, MapEntryNode):
        _expression(value.key, "MapEntryNode.key")
        _expression(value.value, "MapEntryNode.value")
    elif isinstance(value, IndexAccessNode):
        _expression_value(value.collection)
        _expression_value(value.index)
    else:
        raise SurfaceValidationError(
            f"EX-V001 unknown expression type: {type(value).__name__}"
        )


def _pattern(value: PatternNode) -> None:
    _validate_pattern_depth(value)
    if not isinstance(value, PatternNode):
        raise SurfaceValidationError("PT-V001 pattern is required")
    pattern = value.pattern
    if isinstance(pattern, WildcardPatternNode):
        return
    if isinstance(pattern, DefaultPatternNode):
        return
    if isinstance(pattern, IdentifierPatternNode):
        _identifier(pattern.name, "PT-V004 IdentifierPatternNode.name")
        if pattern.name == "_":
            raise SurfaceValidationError("PT-V002 wildcard must use WildcardPatternNode")
        return
    if isinstance(pattern, QualifiedPatternNode):
        _identifier(pattern.namespace, "PT-009 QualifiedPatternNode.namespace")
        _identifier(pattern.identifier, "PT-010 QualifiedPatternNode.identifier")
        return
    if isinstance(pattern, LiteralPatternNode):
        if not isinstance(
            pattern.value,
            (
                IntegerLiteralNode,
                FloatLiteralNode,
                BooleanLiteralNode,
                StringLiteralNode,
                NullLiteralNode,
            ),
        ):
            raise SurfaceValidationError("PT-V003 invalid literal pattern")
        _expression_value(pattern.value)
        return
    if isinstance(pattern, EnumValuePatternNode):
        _identifier(pattern.enum_name, "TV-7 EnumValuePatternNode.enum_name")
        _identifier(pattern.value_name, "TV-7 EnumValuePatternNode.value_name")
        return
    if isinstance(pattern, OptionalPatternNode):
        if pattern.kind == "Some":
            if pattern.binding is None:
                raise SurfaceValidationError("OV-6 SomePatternBindingRequired")
            _identifier(pattern.binding, "OV-6 OptionalPatternNode.binding")
            return
        if pattern.kind == "None":
            if pattern.binding is not None:
                raise SurfaceValidationError("OV-6 NonePatternCannotBind")
            return
        raise SurfaceValidationError("OV-6 invalid optional pattern")
    if isinstance(pattern, OptionalValuePatternNode):
        if pattern.kind != "Some":
            raise SurfaceValidationError("OV-6 invalid optional pattern")
        _pattern(PatternNode(pattern.pattern))
        return
    if isinstance(pattern, OrPatternNode):
        if len(pattern.alternatives) < 2:
            raise SurfaceValidationError("OP-001 OrPattern requires alternatives")
        keys: set[tuple[str, Any]] = set()
        binding_names: tuple[str, ...] | None = None
        pattern_kind: str | None = None
        for alternative in pattern.alternatives:
            alternative_node = PatternNode(alternative)
            _pattern(alternative_node)
            key = _pattern_key(alternative_node)
            if key in keys:
                raise SurfaceValidationError("OP-004 DuplicateOrPattern")
            keys.add(key)
            names = _pattern_binding_names(alternative)
            if binding_names is None:
                binding_names = names
            elif names != binding_names:
                raise SurfaceValidationError("OP-002 IncompatibleBindingEnvironment")
            alternative_kind = _or_pattern_kind(alternative)
            if pattern_kind is None:
                pattern_kind = alternative_kind
            elif alternative_kind != pattern_kind:
                raise SurfaceValidationError("OP-003 incompatible or-pattern alternatives")
        return
    if isinstance(pattern, StructBindingPatternNode):
        _identifier(pattern.field, "SPM-005 StructBindingPatternNode.field")
        _identifier(pattern.binding, "SPM-005 StructBindingPatternNode.binding")
        return
    if isinstance(pattern, StructPatternNode):
        _identifier(pattern.type_name.split(".")[-1], "SP-002 StructPatternNode.type_name")
        field_names: set[str] = set()
        for field in pattern.fields:
            if not isinstance(field, StructFieldPatternNode):
                raise SurfaceValidationError("SP-002 invalid struct pattern syntax")
            _identifier(field.field_name, "SP-002 StructFieldPatternNode.field_name")
            if field.field_name in field_names:
                raise SurfaceValidationError("SP-001 duplicate struct field")
            field_names.add(field.field_name)
            _pattern(PatternNode(field.pattern))
        return
    raise SurfaceValidationError(
        f"PT-V001 unknown pattern type: {type(pattern).__name__}"
    )


def _validate_pattern_depth(value: PatternNode, depth: int = 0) -> None:
    if depth > MAX_PATTERN_DEPTH:
        raise SurfaceValidationError("NP-010 nested pattern depth exceeded")
    if not isinstance(value, PatternNode):
        return
    pattern = value.pattern
    if isinstance(pattern, StructPatternNode):
        for field in pattern.fields:
            _validate_pattern_depth(PatternNode(field.pattern), depth + 1)
        return
    if isinstance(pattern, OrPatternNode):
        for alternative in pattern.alternatives:
            _validate_pattern_depth(PatternNode(alternative), depth + 1)
        return
    if isinstance(pattern, OptionalValuePatternNode):
        _validate_pattern_depth(PatternNode(pattern.pattern), depth + 1)


def _pattern_alternatives(value: PatternNode) -> tuple[PatternNode, ...]:
    pattern = value.pattern
    if isinstance(pattern, OrPatternNode):
        return tuple(PatternNode(alternative) for alternative in pattern.alternatives)
    return (value,)


def _pattern_keys(value: PatternNode) -> tuple[tuple[str, Any], ...]:
    return tuple(_pattern_key(alternative) for alternative in _pattern_alternatives(value))


def _pattern_binding_names(pattern: Any) -> tuple[str, ...]:
    names: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, OptionalPatternNode) and value.kind == "Some" and value.binding:
            names.append(value.binding)
        elif isinstance(value, StructBindingPatternNode):
            names.append(value.binding)
        elif isinstance(value, IdentifierPatternNode):
            names.append(value.name)
        elif isinstance(value, StructPatternNode):
            for field in value.fields:
                collect(field.pattern)
        elif isinstance(value, OptionalValuePatternNode):
            collect(value.pattern)
        elif isinstance(value, OrPatternNode) and value.alternatives:
            for name in _pattern_binding_names(value.alternatives[0]):
                names.append(name)

    collect(pattern)
    return tuple(sorted(names))


def _or_pattern_kind(pattern: Any) -> str:
    if isinstance(pattern, (WildcardPatternNode, DefaultPatternNode)):
        return "catch_all"
    if isinstance(pattern, IdentifierPatternNode) and pattern.name == "default":
        return "catch_all"
    if isinstance(pattern, (OptionalPatternNode, OptionalValuePatternNode)):
        return "optional"
    if isinstance(pattern, (QualifiedPatternNode, EnumValuePatternNode)):
        return "enum"
    if isinstance(pattern, LiteralPatternNode):
        return "literal"
    if isinstance(pattern, StructPatternNode):
        return "struct"
    if isinstance(pattern, StructBindingPatternNode):
        return "binding"
    if isinstance(pattern, IdentifierPatternNode):
        return "identifier"
    if isinstance(pattern, OrPatternNode) and pattern.alternatives:
        return _or_pattern_kind(pattern.alternatives[0])
    return type(pattern).__name__


def _pattern_key(value: PatternNode) -> tuple[str, Any]:
    pattern = value.pattern
    if isinstance(pattern, WildcardPatternNode):
        return ("wildcard", "_")
    if isinstance(pattern, DefaultPatternNode):
        return ("default", "default")
    if isinstance(pattern, IdentifierPatternNode):
        if pattern.name == "default":
            return ("default", "default")
        return ("identifier", pattern.name)
    if isinstance(pattern, QualifiedPatternNode):
        return ("qualified", pattern.namespace, pattern.identifier)
    if isinstance(pattern, EnumValuePatternNode):
        return ("enum_value", pattern.enum_name, pattern.value_name)
    if isinstance(pattern, LiteralPatternNode):
        literal = pattern.value
        if isinstance(literal, NullLiteralNode):
            return ("literal", "Null", None)
        return (
            "literal",
            type(literal).__name__,
            getattr(literal, "value", None),
        )
    if isinstance(pattern, OptionalPatternNode):
        return ("optional", pattern.kind, pattern.binding)
    if isinstance(pattern, OptionalValuePatternNode):
        return ("optional_value", pattern.kind, _pattern_key(PatternNode(pattern.pattern)))
    if isinstance(pattern, OrPatternNode):
        return ("or", tuple(_pattern_key(PatternNode(item)) for item in pattern.alternatives))
    if isinstance(pattern, StructBindingPatternNode):
        return ("struct_binding", pattern.field, pattern.binding)
    if isinstance(pattern, StructPatternNode):
        return (
            "struct",
            pattern.type_name,
            tuple(
                (field.field_name, _pattern_key(PatternNode(field.pattern)))
                for field in pattern.fields
            ),
        )
    return ("unknown", type(pattern).__name__)
