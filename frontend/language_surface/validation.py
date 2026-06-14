"""Validation rules AST-V001 through AST-V007."""

from __future__ import annotations

import re
import math
from dataclasses import fields, is_dataclass
from typing import Any

from .nodes import (
    ActionNode,
    AssignmentStatementNode,
    AttributeNode,
    CalculationNode,
    BinaryExpressionNode,
    BinaryOperator,
    BooleanLiteralNode,
    CallExpressionNode,
    ComparisonExpressionNode,
    ComparisonOperator,
    ConceptNode,
    ConstraintNode,
    ElseIfStatementNode,
    ElseStatementNode,
    EventNode,
    ExpressionStatementNode,
    ExpressionNode,
    FloatLiteralNode,
    GoalNode,
    GoalStatementNode,
    IfStatementNode,
    IdentifierNode,
    IdentifierPatternNode,
    ImportNode,
    IntegerLiteralNode,
    LetStatementNode,
    LiteralPatternNode,
    LogicalExpressionNode,
    LogicalOperator,
    MatchArmNode,
    MatchStatementNode,
    MemberAccessNode,
    ModuleNode,
    ObjectNode,
    NullLiteralNode,
    ParenthesizedExpressionNode,
    PatternNode,
    ProgramNode,
    ReachStatementNode,
    RelationNode,
    RelationType,
    RequireStatementNode,
    ResultStatementNode,
    StringLiteralNode,
    TransitionNode,
    UnaryExpressionNode,
    UnaryOperator,
    Visibility,
    WildcardPatternNode,
)


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DECLARATION_NODES = (
    ConceptNode,
    ObjectNode,
    EventNode,
    ActionNode,
    AttributeNode,
    GoalNode,
    ConstraintNode,
    CalculationNode,
    TransitionNode,
)
KNOWN_NODE_TYPES = (
    ProgramNode,
    ModuleNode,
    ImportNode,
    *DECLARATION_NODES,
    RelationNode,
    LetStatementNode,
    AssignmentStatementNode,
    ResultStatementNode,
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
    UnaryExpressionNode,
    BinaryExpressionNode,
    ComparisonExpressionNode,
    LogicalExpressionNode,
    ParenthesizedExpressionNode,
    MemberAccessNode,
    CallExpressionNode,
    IdentifierPatternNode,
    WildcardPatternNode,
    LiteralPatternNode,
)


class SurfaceValidationError(ValueError):
    pass


def validate(program: ProgramNode) -> None:
    if not isinstance(program, ProgramNode):
        raise SurfaceValidationError("AST-V001 root must be ProgramNode")
    if not program.modules:
        raise SurfaceValidationError("ProgramNode requires at least one module")
    module_names: set[str] = set()
    for module in program.modules:
        _validate_node_types(module)
        _identifier(module.name, "M-001 ModuleNode.name")
        if module.name in module_names:
            raise SurfaceValidationError(f"M-002 duplicate module name: {module.name}")
        module_names.add(module.name)
        if not isinstance(module.visibility, Visibility):
            raise SurfaceValidationError("AST-V001 invalid module visibility")
        _validate_module(module)


def _validate_module(module: ModuleNode) -> None:
    symbols: dict[str, Any] = {}
    for node in module.body:
        if isinstance(node, ImportNode):
            if not node.path:
                raise SurfaceValidationError("I-001 import path must not be empty")
            for part in node.path:
                _identifier(part, "AST-V002 ImportNode.path")
            if node.alias is not None:
                _identifier(node.alias, "AST-V002 ImportNode.alias")
            continue
        if isinstance(node, DECLARATION_NODES):
            name = node.name
            _identifier(name, f"AST-V002 {type(node).__name__}.name")
            if name in symbols:
                raise SurfaceValidationError(
                    f"AST-V003 duplicate module symbol: {name}"
                )
            symbols[name] = node
        if isinstance(
            node,
            (
                LetStatementNode,
                AssignmentStatementNode,
                ResultStatementNode,
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
        elif isinstance(node, CalculationNode):
            _validate_calculation(node, symbols)
        else:
            _validate_ast_node(node)


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
    elif isinstance(node, LetStatementNode):
        _identifier(node.identifier, "ST-001 LetStatementNode.identifier")
        _expression(node.expression, "ST-002 LetStatementNode.expression")
    elif isinstance(node, AssignmentStatementNode):
        _identifier(node.target, "AssignmentStatementNode.target")
        _expression(node.expression, "AssignmentStatementNode.expression")
    elif isinstance(node, ResultStatementNode):
        _expression(node.expression, "ST-020 ResultStatementNode.expression")
    elif isinstance(node, RequireStatementNode):
        _identifier(node.constraint, "RequireStatementNode.constraint")
    elif isinstance(node, (GoalStatementNode, ReachStatementNode)):
        _identifier(node.goal, f"{type(node).__name__}.goal")
    elif isinstance(node, ExpressionStatementNode):
        _expression(node.expression, "ExpressionStatementNode.expression")
        if not isinstance(node.expression.expression, CallExpressionNode):
            raise SurfaceValidationError(
                "ST-060 ExpressionStatementNode root must be CallExpressionNode"
            )
    elif isinstance(node, IfStatementNode):
        _expression(node.condition, "IfNode.condition")
        if not node.body:
            raise SurfaceValidationError("ST-071 IfStatementNode body is required")
    elif isinstance(node, MatchStatementNode):
        _expression(node.expression, "MT-001 MatchNode.expression")
        if not node.arms:
            raise SurfaceValidationError("MT-002 MatchNode requires at least one arm")
        for arm in node.arms:
            _pattern(arm.pattern)
    elif isinstance(node, ConstraintNode):
        _identifier(node.name, "AST-V002 ConstraintNode.name")
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
    _validate_calculation_statements(
        node.body,
        symbols=symbols,
        bindings=set(),
        allow_terminal_result=True,
    )
    if not _statement_list_terminates_with_result(node.body):
        raise SurfaceValidationError(
            "CAL-010 calculation requires a terminal ResultStatementNode"
        )


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
            AssignmentStatementNode,
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
        _validate_ast_node(statement)
        if isinstance(statement, LetStatementNode):
            if statement.identifier in bindings:
                raise SurfaceValidationError(
                    f"ST-003 duplicate immutable binding: {statement.identifier}"
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
                    f"ST-031 reference is not a Constraint: {statement.constraint}"
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
                    f"{code} reference is not a Goal: {statement.goal}"
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
    bindings: set[str],
    allow_terminal_result: bool,
) -> None:
    allowed = (
        LetStatementNode,
        AssignmentStatementNode,
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
    local_bindings = set(bindings)
    for index, statement in enumerate(statements):
        if not isinstance(statement, allowed):
            raise SurfaceValidationError(
                f"CAL-001 {type(statement).__name__} is invalid in calculation body"
            )
        _validate_ast_node(statement)
        is_last = index == len(statements) - 1
        if isinstance(statement, LetStatementNode):
            if statement.identifier in local_bindings:
                raise SurfaceValidationError(
                    f"CAL-021 duplicate let binding: {statement.identifier}"
                )
            _validate_calculation_expression(
                statement.expression, symbols, local_bindings
            )
            local_bindings.add(statement.identifier)
        elif isinstance(statement, AssignmentStatementNode):
            if (
                statement.target not in local_bindings
                and statement.target not in symbols
            ):
                raise SurfaceValidationError(
                    f"CAL-020 undefined assignment target: {statement.target}"
                )
            _validate_calculation_expression(
                statement.expression, symbols, local_bindings
            )
        elif isinstance(statement, ExpressionStatementNode):
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
        elif isinstance(statement, IfStatementNode):
            _validate_calculation_expression(
                statement.condition, symbols, local_bindings
            )
            _validate_calculation_statements(
                statement.body,
                symbols=symbols,
                bindings=local_bindings,
                allow_terminal_result=is_last,
            )
            for branch in statement.elif_branches:
                _validate_calculation_expression(
                    branch.condition, symbols, local_bindings
                )
                _validate_calculation_statements(
                    branch.body,
                    symbols=symbols,
                    bindings=local_bindings,
                    allow_terminal_result=is_last,
                )
            if statement.else_branch:
                _validate_calculation_statements(
                    statement.else_branch.body,
                    symbols=symbols,
                    bindings=local_bindings,
                    allow_terminal_result=is_last,
                )
        elif isinstance(statement, MatchStatementNode):
            _validate_calculation_expression(
                statement.expression, symbols, local_bindings
            )
            for arm in statement.arms:
                _validate_calculation_statements(
                    arm.body,
                    symbols=symbols,
                    bindings=local_bindings,
                    allow_terminal_result=is_last,
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


def _validate_calculation_expression(
    expression: ExpressionNode,
    symbols: dict[str, Any],
    bindings: set[str],
) -> None:
    def visit(value: Any, *, callee: bool = False) -> None:
        if isinstance(value, IdentifierNode):
            if not callee and value.name not in bindings and value.name not in symbols:
                raise SurfaceValidationError(
                    f"CAL-020 undefined variable: {value.name}"
                )
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
        elif isinstance(value, MemberAccessNode):
            visit(value.object)
        elif isinstance(value, CallExpressionNode):
            visit(value.callee, callee=True)
            for argument in value.arguments:
                visit(argument)

    _expression(expression, "CAL-V006 expression")
    visit(expression.expression)


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


def _expression(value: ExpressionNode, location: str) -> None:
    if not isinstance(value, ExpressionNode):
        raise SurfaceValidationError(f"{location} is required")
    _expression_value(value.expression)


def _expression_value(value: Any) -> None:
    if isinstance(value, IdentifierNode):
        _identifier(value.name, "EX-001 IdentifierNode.name")
    elif isinstance(value, IntegerLiteralNode):
        if (
            isinstance(value.value, bool)
            or not isinstance(value.value, int)
            or not -(2**63) <= value.value < 2**63
        ):
            raise SurfaceValidationError(
                "EX-V001 IntegerLiteralNode.value must fit int64"
            )
    elif isinstance(value, (BooleanLiteralNode, StringLiteralNode, NullLiteralNode)):
        return
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
        _identifier(value.member, "EX-V005 MemberAccessNode.member")
    elif isinstance(value, CallExpressionNode):
        _expression_value(value.callee)
        for argument in value.arguments:
            _expression_value(argument)
    else:
        raise SurfaceValidationError(
            f"EX-V001 unknown expression type: {type(value).__name__}"
        )


def _pattern(value: PatternNode) -> None:
    if not isinstance(value, PatternNode):
        raise SurfaceValidationError("PT-V001 pattern is required")
    pattern = value.pattern
    if isinstance(pattern, WildcardPatternNode):
        return
    if isinstance(pattern, IdentifierPatternNode):
        _identifier(pattern.name, "PT-V004 IdentifierPatternNode.name")
        if pattern.name == "_":
            raise SurfaceValidationError("PT-V002 wildcard must use WildcardPatternNode")
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
    raise SurfaceValidationError(
        f"PT-V001 unknown pattern type: {type(pattern).__name__}"
    )
