"""Immutable AST nodes for the Phase 1.1 Language Surface."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any, Mapping, TypeAlias


class Visibility(str, Enum):
    PUBLIC = "Public"
    PRIVATE = "Private"


class RelationType(str, Enum):
    IS_A = "IsA"
    PART_OF = "PartOf"
    CAUSE = "Cause"
    DEPENDENCY = "Dependency"
    CONSTRAINT = "Constraint"
    TEMPORAL = "Temporal"
    SPATIAL = "Spatial"
    SIMILAR = "Similar"


class UnaryOperator(str, Enum):
    NEGATE = "Negate"
    NOT = "Not"


class BinaryOperator(str, Enum):
    ADD = "Add"
    SUBTRACT = "Subtract"
    MULTIPLY = "Multiply"
    DIVIDE = "Divide"
    MODULO = "Modulo"


class ComparisonOperator(str, Enum):
    EQUAL = "Equal"
    NOT_EQUAL = "NotEqual"
    GREATER_THAN = "GreaterThan"
    GREATER_THAN_OR_EQUAL = "GreaterThanOrEqual"
    LESS_THAN = "LessThan"
    LESS_THAN_OR_EQUAL = "LessThanOrEqual"


class LogicalOperator(str, Enum):
    AND = "And"
    OR = "Or"


class PrimitiveKind(str, Enum):
    INT = "Int"
    FLOAT = "Float"
    BOOL = "Bool"
    STRING = "String"
    NULL = "Null"


class StateKind(str, Enum):
    CONCEPT = "Concept"
    OBJECT = "Object"
    EVENT = "Event"
    ACTION = "Action"
    ATTRIBUTE = "Attribute"
    GOAL = "Goal"
    CONSTRAINT = "Constraint"


@dataclass(frozen=True)
class PrimitiveTypeNode:
    kind: PrimitiveKind


@dataclass(frozen=True)
class StateTypeNode:
    kind: StateKind


TypeNode: TypeAlias = PrimitiveTypeNode | StateTypeNode


@dataclass(frozen=True)
class IntegerLiteralNode:
    value: int


@dataclass(frozen=True)
class FloatLiteralNode:
    value: float


@dataclass(frozen=True)
class BooleanLiteralNode:
    value: bool


@dataclass(frozen=True)
class StringLiteralNode:
    value: str


@dataclass(frozen=True)
class NullLiteralNode:
    pass


@dataclass(frozen=True)
class IdentifierNode:
    name: str


@dataclass(frozen=True)
class QualifiedIdentifierNode:
    path: tuple[str, ...]
    symbol: str
    resolved_name: str | None = None


@dataclass(frozen=True)
class UnaryExpressionNode:
    operator: UnaryOperator
    operand: "Expression"


@dataclass(frozen=True)
class BinaryExpressionNode:
    left: "Expression"
    operator: BinaryOperator
    right: "Expression"


@dataclass(frozen=True)
class ComparisonExpressionNode:
    left: "Expression"
    operator: ComparisonOperator
    right: "Expression"


@dataclass(frozen=True)
class LogicalExpressionNode:
    left: "Expression"
    operator: LogicalOperator
    right: "Expression"


@dataclass(frozen=True)
class ParenthesizedExpressionNode:
    expression: "Expression"


@dataclass(frozen=True)
class MemberAccessNode:
    object: "Expression"
    member: str


@dataclass(frozen=True)
class CallExpressionNode:
    callee: "Expression"
    arguments: tuple["Expression", ...]


Expression: TypeAlias = (
    IntegerLiteralNode
    | FloatLiteralNode
    | BooleanLiteralNode
    | StringLiteralNode
    | NullLiteralNode
    | IdentifierNode
    | QualifiedIdentifierNode
    | UnaryExpressionNode
    | BinaryExpressionNode
    | ComparisonExpressionNode
    | LogicalExpressionNode
    | ParenthesizedExpressionNode
    | MemberAccessNode
    | CallExpressionNode
)


@dataclass(frozen=True)
class ExpressionNode:
    expression: Expression


@dataclass(frozen=True)
class IdentifierPatternNode:
    name: str


@dataclass(frozen=True)
class WildcardPatternNode:
    pass


@dataclass(frozen=True)
class LiteralPatternNode:
    value: (
        IntegerLiteralNode
        | FloatLiteralNode
        | BooleanLiteralNode
        | StringLiteralNode
        | NullLiteralNode
    )


Pattern: TypeAlias = IdentifierPatternNode | WildcardPatternNode | LiteralPatternNode


@dataclass(frozen=True)
class PatternNode:
    pattern: Pattern


@dataclass(frozen=True)
class ImportResolutionNode:
    namespace: str
    symbol: str | None
    exposed_names: tuple[str, ...]


@dataclass(frozen=True)
class ImportNode:
    path: tuple[str, ...]
    alias: str | None = None
    resolution: ImportResolutionNode | None = None


@dataclass(frozen=True)
class ConceptNode:
    name: str


@dataclass(frozen=True)
class ObjectNode:
    name: str


@dataclass(frozen=True)
class EventNode:
    name: str


@dataclass(frozen=True)
class ActionNode:
    name: str


@dataclass(frozen=True)
class AttributeNode:
    name: str


@dataclass(frozen=True)
class GoalNode:
    name: str


@dataclass(frozen=True)
class ConstraintNode:
    name: str


@dataclass(frozen=True)
class RelationNode:
    source: str
    relation: RelationType
    target: str


@dataclass(frozen=True)
class LetStatementNode:
    identifier: str
    expression: ExpressionNode
    type_annotation: TypeNode | None = None


@dataclass(frozen=True)
class ConstStatementNode:
    identifier: str
    expression: ExpressionNode
    type_annotation: TypeNode | None = None


@dataclass(frozen=True)
class AssignmentStatementNode:
    target: str
    expression: ExpressionNode


@dataclass(frozen=True)
class ResultStatementNode:
    expression: ExpressionNode


@dataclass(frozen=True)
class ReturnStatementNode:
    expression: ExpressionNode


@dataclass(frozen=True)
class RequireStatementNode:
    constraint: str


@dataclass(frozen=True)
class GoalStatementNode:
    goal: str


@dataclass(frozen=True)
class ReachStatementNode:
    goal: str


@dataclass(frozen=True)
class ExpressionStatementNode:
    expression: ExpressionNode


@dataclass(frozen=True)
class ElseIfStatementNode:
    condition: ExpressionNode
    body: tuple["StatementNode", ...]


@dataclass(frozen=True)
class ElseStatementNode:
    body: tuple["StatementNode", ...]


@dataclass(frozen=True)
class IfStatementNode:
    condition: ExpressionNode
    body: tuple["StatementNode", ...]
    elif_branches: tuple[ElseIfStatementNode, ...] = ()
    else_branch: ElseStatementNode | None = None


@dataclass(frozen=True)
class MatchArmNode:
    pattern: PatternNode
    body: tuple["StatementNode", ...]


@dataclass(frozen=True)
class MatchStatementNode:
    expression: ExpressionNode
    arms: tuple[MatchArmNode, ...]


StatementNode: TypeAlias = (
    LetStatementNode
    | ConstStatementNode
    | AssignmentStatementNode
    | ResultStatementNode
    | ReturnStatementNode
    | RequireStatementNode
    | GoalStatementNode
    | ReachStatementNode
    | ExpressionStatementNode
    | IfStatementNode
    | MatchStatementNode
)

# Phase 1.1/1.2 source compatibility aliases.
LetNode = LetStatementNode
ElseIfNode = ElseIfStatementNode
ElseNode = ElseStatementNode
IfNode = IfStatementNode
MatchNode = MatchStatementNode


@dataclass(frozen=True)
class TransitionNode:
    name: str
    from_state: str
    to_state: str
    body: tuple[StatementNode, ...] = ()


@dataclass(frozen=True)
class CalculationNode:
    name: str
    goal_annotation: str | None
    body: tuple[StatementNode, ...]
    visibility: Visibility = Visibility.PRIVATE
    return_type: TypeNode | None = None


@dataclass(frozen=True)
class FunctionDeclarationNode:
    name: str
    parameters: tuple[str, ...]
    body: tuple[StatementNode, ...]
    visibility: Visibility = Visibility.PRIVATE


AstNode: TypeAlias = (
    ImportNode
    | ConceptNode
    | ObjectNode
    | EventNode
    | ActionNode
    | AttributeNode
    | GoalNode
    | ConstraintNode
    | RelationNode
    | TransitionNode
    | CalculationNode
    | FunctionDeclarationNode
)


@dataclass(frozen=True)
class ModuleNode:
    name: str
    visibility: Visibility
    body: tuple[AstNode, ...]


@dataclass(frozen=True)
class ProgramNode:
    modules: tuple[ModuleNode, ...]


_NODE_TYPES = {
    item.__name__: item
    for item in (
        ActionNode,
        AttributeNode,
        CalculationNode,
        BinaryExpressionNode,
        BooleanLiteralNode,
        CallExpressionNode,
        ComparisonExpressionNode,
        ConceptNode,
        ConstraintNode,
        ConstStatementNode,
        AssignmentStatementNode,
        ElseIfStatementNode,
        ElseStatementNode,
        EventNode,
        ExpressionStatementNode,
        ExpressionNode,
        FloatLiteralNode,
        FunctionDeclarationNode,
        GoalNode,
        GoalStatementNode,
        IdentifierNode,
        IdentifierPatternNode,
        IfStatementNode,
        ImportNode,
        ImportResolutionNode,
        IntegerLiteralNode,
        LetStatementNode,
        LiteralPatternNode,
        LogicalExpressionNode,
        MatchArmNode,
        MatchStatementNode,
        MemberAccessNode,
        ModuleNode,
        NullLiteralNode,
        ObjectNode,
        ParenthesizedExpressionNode,
        PatternNode,
        PrimitiveTypeNode,
        ProgramNode,
        QualifiedIdentifierNode,
        ReachStatementNode,
        RelationNode,
        RequireStatementNode,
        ResultStatementNode,
        ReturnStatementNode,
        StringLiteralNode,
        StateTypeNode,
        TransitionNode,
        UnaryExpressionNode,
        WildcardPatternNode,
    )
}
_NODE_TYPES.update(
    {
        "LetNode": LetStatementNode,
        "ElseIfNode": ElseIfStatementNode,
        "ElseNode": ElseStatementNode,
        "IfNode": IfStatementNode,
        "MatchNode": MatchStatementNode,
    }
)


def to_json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        result = {
            field.name: to_json_value(getattr(value, field.name)) for field in fields(value)
        }
        result["node_type"] = type(value).__name__
        return result
    if isinstance(value, Mapping):
        return {str(key): to_json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [to_json_value(item) for item in value]
    return value


def from_json_value(value: Mapping[str, Any]) -> ProgramNode:
    node = _from_json_node(value)
    if not isinstance(node, ProgramNode):
        raise ValueError("surface AST root must be ProgramNode")
    return node


def expression_from_json(value: Mapping[str, Any]) -> ExpressionNode:
    node = _from_json_node(value)
    if not isinstance(node, ExpressionNode):
        raise ValueError("document must contain ExpressionNode")
    return node


def pattern_from_json(value: Mapping[str, Any]) -> PatternNode:
    node = _from_json_node(value)
    if not isinstance(node, PatternNode):
        raise ValueError("document must contain PatternNode")
    return node


def statement_from_json(value: Mapping[str, Any]) -> StatementNode:
    node = _from_json_node(value)
    if not isinstance(
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
        raise ValueError("document must contain StatementNode")
    return node


def type_from_json(value: Mapping[str, Any]) -> TypeNode:
    node = _from_json_node(value)
    if not isinstance(node, (PrimitiveTypeNode, StateTypeNode)):
        raise ValueError("document must contain TypeNode")
    return node


def calculation_from_json(value: Mapping[str, Any]) -> CalculationNode:
    node = _from_json_node(value)
    if not isinstance(node, CalculationNode):
        raise ValueError("document must contain CalculationNode")
    return node


def _from_json_node(value: Mapping[str, Any]) -> Any:
    node_type = value.get("node_type")
    if node_type not in _NODE_TYPES:
        raise ValueError(f"unknown surface node_type: {node_type}")
    if node_type == "ProgramNode":
        return ProgramNode(tuple(_from_json_node(item) for item in value["modules"]))
    if node_type == "ModuleNode":
        return ModuleNode(
            value["name"],
            Visibility(value["visibility"]),
            tuple(_from_json_node(item) for item in value["body"]),
        )
    if node_type == "ExpressionNode":
        return ExpressionNode(_from_json_node(value["expression"]))
    if node_type == "PatternNode":
        return PatternNode(_from_json_node(value["pattern"]))
    if node_type == "PrimitiveTypeNode":
        return PrimitiveTypeNode(PrimitiveKind(value["kind"]))
    if node_type == "StateTypeNode":
        return StateTypeNode(StateKind(value["kind"]))
    if node_type == "IntegerLiteralNode":
        return IntegerLiteralNode(value["value"])
    if node_type == "FloatLiteralNode":
        return FloatLiteralNode(value["value"])
    if node_type == "BooleanLiteralNode":
        return BooleanLiteralNode(value["value"])
    if node_type == "StringLiteralNode":
        return StringLiteralNode(value["value"])
    if node_type == "NullLiteralNode":
        return NullLiteralNode()
    if node_type == "IdentifierNode":
        return IdentifierNode(value["name"])
    if node_type == "QualifiedIdentifierNode":
        return QualifiedIdentifierNode(
            tuple(value["path"]),
            value["symbol"],
            value.get("resolved_name"),
        )
    if node_type == "UnaryExpressionNode":
        return UnaryExpressionNode(
            UnaryOperator(value["operator"]), _from_json_node(value["operand"])
        )
    if node_type == "BinaryExpressionNode":
        return BinaryExpressionNode(
            _from_json_node(value["left"]),
            BinaryOperator(value["operator"]),
            _from_json_node(value["right"]),
        )
    if node_type == "ComparisonExpressionNode":
        return ComparisonExpressionNode(
            _from_json_node(value["left"]),
            ComparisonOperator(value["operator"]),
            _from_json_node(value["right"]),
        )
    if node_type == "LogicalExpressionNode":
        return LogicalExpressionNode(
            _from_json_node(value["left"]),
            LogicalOperator(value["operator"]),
            _from_json_node(value["right"]),
        )
    if node_type == "ParenthesizedExpressionNode":
        return ParenthesizedExpressionNode(_from_json_node(value["expression"]))
    if node_type == "MemberAccessNode":
        return MemberAccessNode(
            _from_json_node(value["object"]), value["member"]
        )
    if node_type == "CallExpressionNode":
        return CallExpressionNode(
            _from_json_node(value["callee"]),
            tuple(_from_json_node(item) for item in value["arguments"]),
        )
    if node_type == "IdentifierPatternNode":
        return IdentifierPatternNode(value["name"])
    if node_type == "WildcardPatternNode":
        return WildcardPatternNode()
    if node_type == "LiteralPatternNode":
        return LiteralPatternNode(_from_json_node(value["value"]))
    if node_type == "ImportNode":
        return ImportNode(
            tuple(value["path"]),
            value.get("alias"),
            (
                _from_json_node(value["resolution"])
                if value.get("resolution")
                else None
            ),
        )
    if node_type == "ImportResolutionNode":
        return ImportResolutionNode(
            value["namespace"],
            value.get("symbol"),
            tuple(value["exposed_names"]),
        )
    if node_type == "RelationNode":
        return RelationNode(
            value["source"], RelationType(value["relation"]), value["target"]
        )
    if node_type in {
        "ConceptNode",
        "ObjectNode",
        "EventNode",
        "ActionNode",
        "AttributeNode",
        "GoalNode",
        "ConstraintNode",
    }:
        return _NODE_TYPES[node_type](value["name"])
    if node_type in {"LetNode", "LetStatementNode"}:
        return LetStatementNode(
            value["identifier"],
            _from_json_node(value["expression"]),
            (
                _from_json_node(value["type_annotation"])
                if value.get("type_annotation")
                else None
            ),
        )
    if node_type == "ConstStatementNode":
        return ConstStatementNode(
            value["identifier"],
            _from_json_node(value["expression"]),
            (
                _from_json_node(value["type_annotation"])
                if value.get("type_annotation")
                else None
            ),
        )
    if node_type == "AssignmentStatementNode":
        return AssignmentStatementNode(
            value["target"], _from_json_node(value["expression"])
        )
    if node_type == "ResultStatementNode":
        return ResultStatementNode(_from_json_node(value["expression"]))
    if node_type == "ReturnStatementNode":
        return ReturnStatementNode(_from_json_node(value["expression"]))
    if node_type == "RequireStatementNode":
        return RequireStatementNode(value["constraint"])
    if node_type == "GoalStatementNode":
        return GoalStatementNode(value["goal"])
    if node_type == "ReachStatementNode":
        return ReachStatementNode(value["goal"])
    if node_type == "ExpressionStatementNode":
        return ExpressionStatementNode(_from_json_node(value["expression"]))
    if node_type in {"ElseIfNode", "ElseIfStatementNode"}:
        return ElseIfStatementNode(
            _from_json_node(value["condition"]),
            tuple(_from_json_node(item) for item in value["body"]),
        )
    if node_type in {"ElseNode", "ElseStatementNode"}:
        return ElseStatementNode(
            tuple(_from_json_node(item) for item in value["body"])
        )
    if node_type in {"IfNode", "IfStatementNode"}:
        return IfStatementNode(
            _from_json_node(value["condition"]),
            tuple(_from_json_node(item) for item in value["body"]),
            tuple(_from_json_node(item) for item in value["elif_branches"]),
            _from_json_node(value["else_branch"]) if value.get("else_branch") else None,
        )
    if node_type == "MatchArmNode":
        return MatchArmNode(
            _from_json_node(value["pattern"]),
            tuple(_from_json_node(item) for item in value["body"]),
        )
    if node_type in {"MatchNode", "MatchStatementNode"}:
        return MatchStatementNode(
            _from_json_node(value["expression"]),
            tuple(_from_json_node(item) for item in value["arms"]),
        )
    if node_type == "TransitionNode":
        return TransitionNode(
            value["name"],
            value["from_state"],
            value["to_state"],
            tuple(_from_json_node(item) for item in value.get("body", ())),
        )
    if node_type == "CalculationNode":
        return CalculationNode(
            value["name"],
            value.get("goal_annotation"),
            tuple(_from_json_node(item) for item in value["body"]),
            Visibility(value.get("visibility", Visibility.PRIVATE.value)),
            (
                _from_json_node(value["return_type"])
                if value.get("return_type")
                else None
            ),
        )
    if node_type == "FunctionDeclarationNode":
        return FunctionDeclarationNode(
            value["name"],
            tuple(value["parameters"]),
            tuple(_from_json_node(item) for item in value["body"]),
            Visibility(value.get("visibility", Visibility.PRIVATE.value)),
        )
    raise AssertionError(f"unhandled surface node_type: {node_type}")
