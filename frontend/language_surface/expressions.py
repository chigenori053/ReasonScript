"""Phase 1.2 expression and pattern parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .nodes import (
    BinaryExpressionNode,
    BinaryOperator,
    ArrayLiteralNode,
    BooleanLiteralNode,
    CallExpressionNode,
    ComparisonExpressionNode,
    ComparisonOperator,
    Expression,
    ExpressionNode,
    EnumValuePatternNode,
    FloatLiteralNode,
    IdentifierNode,
    IndexAccessNode,
    IdentifierPatternNode,
    IntegerLiteralNode,
    LiteralPatternNode,
    LogicalExpressionNode,
    LogicalOperator,
    MemberAccessNode,
    NoneLiteralNode,
    NullLiteralNode,
    OptionalPatternNode,
    ParenthesizedExpressionNode,
    PatternNode,
    QualifiedIdentifierNode,
    StringLiteralNode,
    SomeExpressionNode,
    TupleLiteralNode,
    UnaryExpressionNode,
    UnaryOperator,
    WildcardPatternNode,
)


class ExpressionSyntaxError(ValueError):
    pass


class _Kind(str, Enum):
    IDENTIFIER = "identifier"
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    OPERATOR = "operator"
    LEFT_PAREN = "left_paren"
    RIGHT_PAREN = "right_paren"
    COMMA = "comma"
    LEFT_BRACKET = "left_bracket"
    RIGHT_BRACKET = "right_bracket"
    DOT = "dot"
    QUALIFIER = "qualifier"
    EOF = "eof"


@dataclass(frozen=True)
class _Token:
    kind: _Kind
    value: str
    offset: int


_BINARY = {
    "+": (50, BinaryOperator.ADD, BinaryExpressionNode),
    "-": (50, BinaryOperator.SUBTRACT, BinaryExpressionNode),
    "*": (60, BinaryOperator.MULTIPLY, BinaryExpressionNode),
    "/": (60, BinaryOperator.DIVIDE, BinaryExpressionNode),
    "%": (60, BinaryOperator.MODULO, BinaryExpressionNode),
    "==": (40, ComparisonOperator.EQUAL, ComparisonExpressionNode),
    "!=": (40, ComparisonOperator.NOT_EQUAL, ComparisonExpressionNode),
    ">": (40, ComparisonOperator.GREATER_THAN, ComparisonExpressionNode),
    ">=": (40, ComparisonOperator.GREATER_THAN_OR_EQUAL, ComparisonExpressionNode),
    "<": (40, ComparisonOperator.LESS_THAN, ComparisonExpressionNode),
    "<=": (40, ComparisonOperator.LESS_THAN_OR_EQUAL, ComparisonExpressionNode),
    "&&": (30, LogicalOperator.AND, LogicalExpressionNode),
    "||": (20, LogicalOperator.OR, LogicalExpressionNode),
}


def parse_expression(source: str, *, allow_tuple_access: bool = False) -> ExpressionNode:
    parser = _Parser(_tokenize(source), allow_tuple_access=allow_tuple_access)
    expression = parser.parse(0)
    if parser.current.kind != _Kind.EOF:
        raise ExpressionSyntaxError(
            f"unexpected token {parser.current.value!r} at offset {parser.current.offset}"
        )
    return ExpressionNode(expression)


def parse_pattern(source: str) -> PatternNode:
    text = source.strip()
    if not text:
        raise ExpressionSyntaxError("PT-V001 pattern is required")
    if text == "_":
        return PatternNode(WildcardPatternNode())
    if text == "none":
        return PatternNode(OptionalPatternNode("None"))
    some_match = re.fullmatch(r"some\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)", text)
    if some_match:
        return PatternNode(OptionalPatternNode("Some", some_match.group(1)))
    expression = parse_expression(text).expression
    if isinstance(expression, IdentifierNode):
        return PatternNode(IdentifierPatternNode(expression.name))
    if (
        isinstance(expression, MemberAccessNode)
        and isinstance(expression.object, IdentifierNode)
    ):
        return PatternNode(
            EnumValuePatternNode(expression.object.name, expression.member)
        )
    if isinstance(
        expression,
        (
            IntegerLiteralNode,
            FloatLiteralNode,
            BooleanLiteralNode,
            StringLiteralNode,
            NullLiteralNode,
        ),
    ):
        return PatternNode(LiteralPatternNode(expression))
    raise ExpressionSyntaxError("pattern must be an identifier, literal, or wildcard")


class _Parser:
    def __init__(self, tokens: tuple[_Token, ...], *, allow_tuple_access: bool):
        self.tokens = tokens
        self.index = 0
        self.allow_tuple_access = allow_tuple_access

    @property
    def current(self) -> _Token:
        return self.tokens[self.index]

    def take(self) -> _Token:
        token = self.current
        self.index += 1
        return token

    def parse(self, minimum_precedence: int) -> Expression:
        left = self._prefix()
        while True:
            if self.current.kind == _Kind.DOT:
                left = self._member(left)
                continue
            if self.current.kind == _Kind.LEFT_PAREN:
                left = self._call(left)
                continue
            if self.current.kind == _Kind.LEFT_BRACKET:
                left = self._index(left)
                continue
            entry = _BINARY.get(self.current.value)
            if entry is None or entry[0] < minimum_precedence:
                return left
            precedence, operator, node_type = entry
            self.take()
            if self.current.kind in {_Kind.EOF, _Kind.RIGHT_PAREN, _Kind.COMMA}:
                raise ExpressionSyntaxError("D-001 binary operator is missing operand")
            right = self.parse(precedence + 1)
            left = node_type(left, operator, right)

    def _prefix(self) -> Expression:
        token = self.take()
        if token.kind == _Kind.INTEGER:
            return IntegerLiteralNode(int(token.value))
        if token.kind == _Kind.FLOAT:
            return FloatLiteralNode(float(token.value))
        if token.kind == _Kind.STRING:
            return StringLiteralNode(_decode_string(token.value))
        if token.kind == _Kind.IDENTIFIER:
            if token.value == "true":
                return BooleanLiteralNode(True)
            if token.value == "false":
                return BooleanLiteralNode(False)
            if token.value == "null":
                return NullLiteralNode()
            if token.value == "none":
                return NoneLiteralNode()
            if self.current.kind == _Kind.QUALIFIER:
                parts = [token.value]
                while self.current.kind == _Kind.QUALIFIER:
                    self.take()
                    if self.current.kind != _Kind.IDENTIFIER:
                        raise ExpressionSyntaxError(
                            "NS-030 qualified name requires an identifier"
                        )
                    parts.append(self.take().value)
                if len(parts) < 2:
                    raise AssertionError("qualified name requires at least two parts")
                return QualifiedIdentifierNode(tuple(parts[:-1]), parts[-1])
            return IdentifierNode(token.value)
        if token.value in {"-", "!"}:
            if self.current.kind == _Kind.EOF:
                raise ExpressionSyntaxError("D-001 unary operator is missing operand")
            operator = UnaryOperator.NEGATE if token.value == "-" else UnaryOperator.NOT
            return UnaryExpressionNode(operator, self.parse(70))
        if token.kind == _Kind.LEFT_PAREN:
            if self.current.kind == _Kind.RIGHT_PAREN:
                raise ExpressionSyntaxError("parenthesized expression must not be empty")
            expression = self.parse(0)
            if self.current.kind == _Kind.COMMA:
                elements = [ExpressionNode(expression)]
                while self.current.kind == _Kind.COMMA:
                    self.take()
                    if self.current.kind == _Kind.RIGHT_PAREN:
                        raise ExpressionSyntaxError("tuple trailing comma is not supported")
                    elements.append(ExpressionNode(self.parse(0)))
                if self.current.kind != _Kind.RIGHT_PAREN:
                    raise ExpressionSyntaxError("EX-V003 unbalanced tuple")
                self.take()
                return TupleLiteralNode(tuple(elements))
            if self.current.kind != _Kind.RIGHT_PAREN:
                raise ExpressionSyntaxError("EX-V003 unbalanced parentheses")
            self.take()
            return ParenthesizedExpressionNode(expression)
        if token.kind == _Kind.LEFT_BRACKET:
            elements: list[ExpressionNode] = []
            if self.current.kind == _Kind.RIGHT_BRACKET:
                self.take()
                return ArrayLiteralNode(())
            while True:
                elements.append(ExpressionNode(self.parse(0)))
                if self.current.kind == _Kind.RIGHT_BRACKET:
                    self.take()
                    return ArrayLiteralNode(tuple(elements))
                if self.current.kind != _Kind.COMMA:
                    raise ExpressionSyntaxError("array literal requires comma or closing bracket")
                self.take()
                if self.current.kind == _Kind.RIGHT_BRACKET:
                    raise ExpressionSyntaxError("array trailing comma is not supported")
        raise ExpressionSyntaxError(
            f"expected expression at offset {token.offset}, received {token.value!r}"
        )

    def _member(self, left: Expression) -> Expression:
        self.take()
        if self.current.kind == _Kind.INTEGER and not self.allow_tuple_access:
            raise ExpressionSyntaxError("EX-V005 member access requires an identifier")
        if self.current.kind not in {_Kind.IDENTIFIER, _Kind.INTEGER}:
            raise ExpressionSyntaxError("EX-V005 member access requires an identifier")
        return MemberAccessNode(left, self.take().value)

    def _index(self, collection: Expression) -> Expression:
        self.take()
        if self.current.kind == _Kind.RIGHT_BRACKET:
            raise ExpressionSyntaxError("CV5-6 index expression is required")
        index = self.parse(0)
        if self.current.kind != _Kind.RIGHT_BRACKET:
            raise ExpressionSyntaxError("CV5-6 unbalanced index access")
        self.take()
        return IndexAccessNode(collection, index)

    def _call(self, callee: Expression) -> Expression:
        self.take()
        arguments: list[Expression] = []
        if self.current.kind == _Kind.RIGHT_PAREN:
            self.take()
            if isinstance(callee, IdentifierNode) and callee.name == "some":
                raise ExpressionSyntaxError("OV-2 some requires one argument")
            return CallExpressionNode(callee, ())
        while True:
            if self.current.kind in {_Kind.COMMA, _Kind.EOF}:
                raise ExpressionSyntaxError("EX-V004 invalid call argument")
            arguments.append(self.parse(0))
            if self.current.kind == _Kind.RIGHT_PAREN:
                self.take()
                if isinstance(callee, IdentifierNode) and callee.name == "some":
                    if len(arguments) != 1:
                        raise ExpressionSyntaxError("OV-2 some requires one argument")
                    return SomeExpressionNode(arguments[0])
                return CallExpressionNode(callee, tuple(arguments))
            if self.current.kind != _Kind.COMMA:
                raise ExpressionSyntaxError("EX-V004 call requires comma or closing parenthesis")
            self.take()
            if self.current.kind == _Kind.RIGHT_PAREN:
                raise ExpressionSyntaxError("EX-V004 trailing comma is not supported")


def _tokenize(source: str) -> tuple[_Token, ...]:
    tokens: list[_Token] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char.isspace():
            index += 1
            continue
        if char in {'"', "'"}:
            start = index
            quote = char
            index += 1
            escaped = False
            while index < len(source):
                if source[index] == quote and not escaped:
                    index += 1
                    break
                escaped = source[index] == "\\" and not escaped
                if source[index] != "\\":
                    escaped = False
                index += 1
            else:
                raise ExpressionSyntaxError("unterminated string literal")
            tokens.append(_Token(_Kind.STRING, source[start:index], start))
            continue
        if char.isdigit():
            match = re.match(r"\d+(?:\.\d+)?", source[index:])
            assert match is not None
            value = match.group(0)
            kind = _Kind.FLOAT if "." in value else _Kind.INTEGER
            tokens.append(_Token(kind, value, index))
            index += len(value)
            continue
        if char.isalpha() or char == "_":
            match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", source[index:])
            assert match is not None
            value = match.group(0)
            tokens.append(_Token(_Kind.IDENTIFIER, value, index))
            index += len(value)
            continue
        matched = next(
            (
                operator
                for operator in ("::", "==", "!=", ">=", "<=", "&&", "||")
                if source.startswith(operator, index)
            ),
            None,
        )
        if matched:
            kind = _Kind.QUALIFIER if matched == "::" else _Kind.OPERATOR
            tokens.append(_Token(kind, matched, index))
            index += len(matched)
            continue
        kind = {
            "(": _Kind.LEFT_PAREN,
            ")": _Kind.RIGHT_PAREN,
            "[": _Kind.LEFT_BRACKET,
            "]": _Kind.RIGHT_BRACKET,
            ",": _Kind.COMMA,
            ".": _Kind.DOT,
        }.get(char)
        if kind:
            tokens.append(_Token(kind, char, index))
            index += 1
            continue
        if char in "+-*/%><!":
            if index + 1 < len(source) and source[index + 1] in {"*", "&", "|"}:
                raise ExpressionSyntaxError(f"D-002 invalid operator at offset {index}")
            tokens.append(_Token(_Kind.OPERATOR, char, index))
            index += 1
            continue
        raise ExpressionSyntaxError(f"unsupported expression character {char!r}")
    tokens.append(_Token(_Kind.EOF, "", len(source)))
    return tuple(tokens)


def _decode_string(source: str) -> str:
    quote = source[0]
    body = source[1:-1]
    return body.replace(f"\\{quote}", quote).replace("\\\\", "\\")
