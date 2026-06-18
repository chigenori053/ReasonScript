"""Validation rules AST-V001 through AST-V007."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, fields, is_dataclass
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
    ConstStatementNode,
    ElseIfStatementNode,
    ElseStatementNode,
    EventNode,
    ExpressionStatementNode,
    ExpressionNode,
    FloatLiteralNode,
    FunctionDeclarationNode,
    GoalNode,
    GoalStatementNode,
    IfStatementNode,
    IdentifierNode,
    IdentifierPatternNode,
    ImportNode,
    ImportResolutionNode,
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
    PrimitiveKind,
    PrimitiveTypeNode,
    ProgramNode,
    QualifiedIdentifierNode,
    ReachStatementNode,
    RelationNode,
    RelationType,
    RequireStatementNode,
    ResultStatementNode,
    ReturnStatementNode,
    StringLiteralNode,
    StateKind,
    StateTypeNode,
    TransitionNode,
    UnaryExpressionNode,
    UnaryOperator,
    Visibility,
    WildcardPatternNode,
)
from .namespace import ModuleNamespace, NamespaceResolutionError, resolve_program


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RESERVED_IDENTIFIERS = {
    "bool",
    "true",
    "false",
    "if",
    "else",
    "match",
}
DECLARATION_NODES = (
    ConceptNode,
    ObjectNode,
    EventNode,
    ActionNode,
    AttributeNode,
    GoalNode,
    ConstraintNode,
    CalculationNode,
    FunctionDeclarationNode,
    TransitionNode,
)
KNOWN_NODE_TYPES = (
    ProgramNode,
    ModuleNode,
    ImportNode,
    ImportResolutionNode,
    *DECLARATION_NODES,
    RelationNode,
    LetStatementNode,
    ConstStatementNode,
    AssignmentStatementNode,
    ResultStatementNode,
    ReturnStatementNode,
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
    PrimitiveTypeNode,
    StateTypeNode,
)


class SurfaceValidationError(ValueError):
    pass


_CURRENT_NAMESPACE: ModuleNamespace | None = None


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
    try:
        resolved_program, namespaces = resolve_program(program, strict=False)
    except NamespaceResolutionError as error:
        raise SurfaceValidationError(str(error)) from error
    module_names: set[str] = set()
    for module in resolved_program.modules:
        _CURRENT_NAMESPACE = namespaces[module.name]
        _validate_node_types(module)
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
                ConstStatementNode,
                AssignmentStatementNode,
                ResultStatementNode,
                ReturnStatementNode,
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
        elif isinstance(node, FunctionDeclarationNode):
            _validate_function(node, symbols)
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
        if node.return_type is not None:
            _validate_type_node(node.return_type)
    elif isinstance(node, FunctionDeclarationNode):
        _identifier(node.name, "FN-001 FunctionDeclarationNode.name")
        if not isinstance(node.visibility, Visibility):
            raise SurfaceValidationError("FN-001 invalid function visibility")
        seen: set[str] = set()
        for parameter in node.parameters:
            _identifier(parameter, "FN-002 FunctionDeclarationNode.parameter")
            if parameter in seen:
                raise SurfaceValidationError(f"FN-003 duplicate parameter: {parameter}")
            seen.add(parameter)
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
        arm_keys: set[tuple[str, Any]] = set()
        default_seen = False
        for index, arm in enumerate(node.arms):
            _pattern(arm.pattern)
            key = _pattern_key(arm.pattern)
            if key[0] == "wildcard":
                if default_seen:
                    raise SurfaceValidationError(
                        "CV-6 only one default match arm is permitted"
                    )
                default_seen = True
                if index != len(node.arms) - 1:
                    raise SurfaceValidationError(
                        "CV-7 default match arm must be last"
                    )
            elif key in arm_keys:
                raise SurfaceValidationError("CV-5 duplicate match arm")
            arm_keys.add(key)
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
        bindings={},
        allow_terminal_result=True,
        return_type=node.return_type,
    )
    if not _statement_list_terminates_with_result(node.body):
        raise SurfaceValidationError(
            "CAL-010 calculation requires a terminal ResultStatementNode"
        )


def _validate_function(node: FunctionDeclarationNode, symbols: dict[str, Any]) -> None:
    _validate_ast_node(node)
    bindings = {
        parameter: _Binding(_UNKNOWN_TYPE, mutable=False)
        for parameter in node.parameters
    }
    _validate_function_statements(
        node.body,
        symbols=symbols,
        bindings=bindings,
        allow_terminal_return=True,
    )
    if not _statement_list_terminates_with_return(node.body):
        raise SurfaceValidationError(
            "FN-010 function requires a terminal ReturnStatementNode"
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
            ConstStatementNode,
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
) -> None:
    allowed = (
        LetStatementNode,
        ConstStatementNode,
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
            if statement.type_annotation is not None:
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
                )
            if statement.else_branch:
                _validate_calculation_statements(
                    statement.else_branch.body,
                    symbols=symbols,
                    bindings=local_bindings,
                    allow_terminal_result=is_last,
                    return_type=return_type,
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
                    return_type=return_type,
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
) -> None:
    allowed = (
        LetStatementNode,
        ConstStatementNode,
        AssignmentStatementNode,
        IfStatementNode,
        MatchStatementNode,
        ExpressionStatementNode,
        ReturnStatementNode,
    )
    direct_returns = sum(
        isinstance(statement, ReturnStatementNode) for statement in statements
    )
    if direct_returns > 1:
        raise SurfaceValidationError(
            "FN-011 function path contains multiple ReturnStatementNode values"
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
            if statement.type_annotation is not None:
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
        elif isinstance(statement, ExpressionStatementNode):
            _validate_calculation_expression(
                statement.expression, symbols, local_bindings
            )
        elif isinstance(statement, ReturnStatementNode):
            if not allow_terminal_return or not is_last:
                raise SurfaceValidationError(
                    "FN-012 ReturnStatementNode must be the final statement"
                )
            _validate_calculation_expression(
                statement.expression, symbols, local_bindings
            )
        elif isinstance(statement, IfStatementNode):
            _validate_calculation_expression(
                statement.condition, symbols, local_bindings
            )
            _require_bool_condition(statement.condition, symbols, local_bindings)
            _validate_function_statements(
                statement.body,
                symbols=symbols,
                bindings=local_bindings,
                allow_terminal_return=is_last,
            )
            for branch in statement.elif_branches:
                _validate_calculation_expression(
                    branch.condition, symbols, local_bindings
                )
                _require_bool_condition(branch.condition, symbols, local_bindings)
                _validate_function_statements(
                    branch.body,
                    symbols=symbols,
                    bindings=local_bindings,
                    allow_terminal_return=is_last,
                )
            if statement.else_branch:
                _validate_function_statements(
                    statement.else_branch.body,
                    symbols=symbols,
                    bindings=local_bindings,
                    allow_terminal_return=is_last,
                )
        elif isinstance(statement, MatchStatementNode):
            _validate_calculation_expression(
                statement.expression, symbols, local_bindings
            )
            for arm in statement.arms:
                _validate_function_statements(
                    arm.body,
                    symbols=symbols,
                    bindings=local_bindings,
                    allow_terminal_return=is_last,
                )


def _statement_list_terminates_with_return(statements: tuple[Any, ...]) -> bool:
    if not statements:
        return False
    final = statements[-1]
    if isinstance(final, ReturnStatementNode):
        return True
    if isinstance(final, IfStatementNode):
        if final.else_branch is None:
            return False
        branches = [final.body]
        branches.extend(branch.body for branch in final.elif_branches)
        branches.append(final.else_branch.body)
        return all(_statement_list_terminates_with_return(body) for body in branches)
    if isinstance(final, MatchStatementNode):
        return bool(final.arms) and all(
            _statement_list_terminates_with_return(arm.body) for arm in final.arms
        )
    return False


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
                raise SurfaceValidationError(
                    f"CAL-020 undefined variable: {value.name}"
                )
        elif isinstance(value, QualifiedIdentifierNode):
            if _CURRENT_NAMESPACE is None:
                raise SurfaceValidationError("NS-V005 namespace is unavailable")
            _CURRENT_NAMESPACE.resolve_qualified(value)
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
    _expression_type(expression.expression, symbols, bindings)


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
    if isinstance(value, ParenthesizedExpressionNode):
        return _expression_type(value.expression, symbols, bindings)
    if isinstance(value, UnaryExpressionNode):
        operand = _expression_type(value.operand, symbols, bindings)
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
        if any(item is not _UNKNOWN_TYPE and item != bool_type for item in (left, right)):
            raise SurfaceValidationError("TYPE-V006 logical operands must be Bool")
        return bool_type
    if isinstance(value, (MemberAccessNode, CallExpressionNode)):
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
    raise SurfaceValidationError("TYPE-V002 invalid TypeNode")


def _type_name(value: Any) -> str:
    if isinstance(value, (PrimitiveTypeNode, StateTypeNode)):
        return value.kind.value
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


def _expression(value: ExpressionNode, location: str) -> None:
    if not isinstance(value, ExpressionNode):
        raise SurfaceValidationError(f"{location} is required")
    _expression_value(value.expression)


def _expression_value(value: Any) -> None:
    if isinstance(value, IdentifierNode):
        _identifier(value.name, "EX-001 IdentifierNode.name")
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


def _pattern_key(value: PatternNode) -> tuple[str, Any]:
    pattern = value.pattern
    if isinstance(pattern, WildcardPatternNode):
        return ("wildcard", "_")
    if isinstance(pattern, IdentifierPatternNode):
        return ("identifier", pattern.name)
    if isinstance(pattern, LiteralPatternNode):
        literal = pattern.value
        if isinstance(literal, NullLiteralNode):
            return ("literal", "Null", None)
        return (
            "literal",
            type(literal).__name__,
            getattr(literal, "value", None),
        )
    return ("unknown", type(pattern).__name__)
