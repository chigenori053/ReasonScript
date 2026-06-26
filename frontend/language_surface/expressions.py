"""Phase 1.2 expression and pattern parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .nodes import (
    BinaryExpressionNode,
    BinaryOperator,
    ArrayLiteralNode,
    BooleanLiteralNode,
    CallExpressionNode,
    ComparisonExpressionNode,
    ComparisonOperator,
    DefaultPatternNode,
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
    QualifiedPatternNode,
    QualifiedIdentifierNode,
    StringLiteralNode,
    SomeExpressionNode,
    StructFieldPatternNode,
    StructLiteralExpressionNode,
    StructLiteralFieldNode,
    StructPatternNode,
    TupleLiteralNode,
    UnaryExpressionNode,
    UnaryOperator,
    WildcardPatternNode,
)


class ExpressionSyntaxError(ValueError):
    pass


MAX_PATTERN_DEPTH = 128
_NP_010 = "NP-010 nested pattern depth exceeded"


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
    LEFT_BRACE = "left_brace"
    RIGHT_BRACE = "right_brace"
    COLON = "colon"
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


def parse_pattern(source: str, depth: int = 0) -> PatternNode:
    if depth > MAX_PATTERN_DEPTH:
        raise ExpressionSyntaxError(_NP_010)
    text = source.strip()
    if not text:
        raise ExpressionSyntaxError("PT-V001 pattern is required")
    if " if " in text:
        raise ExpressionSyntaxError("PT-201 guard patterns are not supported in LSI-200")
    if "|" in text:
        raise ExpressionSyntaxError("PT-202 OR patterns are not supported in LSI-200")
    if ".." in text:
        raise ExpressionSyntaxError("PT-203 range patterns are not supported in LSI-200")
    if text.startswith("(") and text.endswith(")") and "," in text:
        raise ExpressionSyntaxError("PT-204 destructuring patterns are not supported in LSI-200")
    if "{" in text or "}" in text:
        return _parse_struct_pattern(text, depth)
    nested_match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(.+\)", text)
    if nested_match and nested_match.group(1) != "some":
        raise ExpressionSyntaxError("PT-206 nested patterns are not supported in LSI-200")
    if text == "_":
        return PatternNode(WildcardPatternNode())
    if text == "default":
        return PatternNode(DefaultPatternNode())
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
        return PatternNode(QualifiedPatternNode(expression.object.name, expression.member))
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


def _parse_struct_pattern(source: str, depth: int) -> PatternNode:
    parser = _StructPatternFrameParser(source, depth)
    pattern = parser.parse_struct_pattern()
    parser.skip_separators()
    if not parser.at_end():
        raise ExpressionSyntaxError("SP-002 NP-002 unexpected token after struct pattern")
    return PatternNode(pattern)


def _skip_pattern_separators(source: str, index: int) -> int:
    while index < len(source) and (source[index].isspace() or source[index] == ","):
        index += 1
    return index


class _StructPatternFrameParser:
    def __init__(self, source: str, depth: int):
        self.source = source
        self.index = 0
        self.depth = depth

    def at_end(self) -> bool:
        return self.index >= len(self.source)

    def skip_separators(self) -> None:
        self.index = _skip_pattern_separators(self.source, self.index)

    def parse_struct_pattern(self) -> StructPatternNode:
        if self.depth > MAX_PATTERN_DEPTH:
            raise ExpressionSyntaxError(_NP_010)
        type_name = self._qualified_identifier()
        self._skip_whitespace()
        self._consume("{", "SP-002 NP-002 invalid struct pattern syntax")
        fields: list[StructFieldPatternNode] = []
        seen: set[str] = set()
        while True:
            self.skip_separators()
            if self.at_end():
                raise ExpressionSyntaxError("SP-002 NP-003 missing closing brace")
            if self.source[self.index] == "}":
                self.index += 1
                return StructPatternNode(type_name, tuple(fields))
            field_name = self._identifier()
            if field_name in seen:
                raise ExpressionSyntaxError("SP-001 duplicate struct field")
            seen.add(field_name)
            self._skip_whitespace()
            self._consume(":", "SP-002 NP-002 invalid struct pattern syntax")
            field_pattern = self._field_pattern()
            fields.append(StructFieldPatternNode(field_name, field_pattern))

    def _field_pattern(self) -> Any:
        self._skip_whitespace()
        if self.at_end() or self.source[self.index] == "}":
            raise ExpressionSyntaxError("SP-002 NP-002 invalid struct pattern syntax")
        if self._starts_struct_pattern():
            child = _StructPatternFrameParser(self.source[self.index:], self.depth + 1)
            pattern = child.parse_struct_pattern()
            self.index += child.index
            return pattern
        end = _next_struct_field_boundary(self.source, self.index)
        pattern_source = self.source[self.index:end].strip().rstrip(",").strip()
        if not pattern_source:
            raise ExpressionSyntaxError("SP-002 NP-002 invalid struct pattern syntax")
        self.index = end
        return parse_pattern(pattern_source, self.depth + 1).pattern

    def _starts_struct_pattern(self) -> bool:
        match = re.match(
            r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\s*\{",
            self.source[self.index:],
        )
        return match is not None

    def _qualified_identifier(self) -> str:
        match = re.match(
            r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*",
            self.source[self.index:],
        )
        if not match:
            raise ExpressionSyntaxError("SP-002 NP-002 invalid struct pattern syntax")
        self.index += match.end()
        return match.group(0)

    def _identifier(self) -> str:
        match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", self.source[self.index:])
        if not match:
            raise ExpressionSyntaxError("SP-002 NP-002 invalid struct pattern syntax")
        self.index += match.end()
        return match.group(0)

    def _skip_whitespace(self) -> None:
        while self.index < len(self.source) and self.source[self.index].isspace():
            self.index += 1

    def _consume(self, expected: str, diagnostic: str) -> None:
        if self.index >= len(self.source) or self.source[self.index] != expected:
            raise ExpressionSyntaxError(diagnostic)
        self.index += 1


def _next_struct_field_boundary(source: str, index: int) -> int:
    depth = 0
    in_string: str | None = None
    escaped = False
    cursor = index
    while cursor < len(source):
        char = source[cursor]
        if in_string is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            cursor += 1
            continue
        if char in {'"', "'"}:
            in_string = char
            cursor += 1
            continue
        if char == "{":
            depth += 1
            cursor += 1
            continue
        if char == "}":
            if depth == 0:
                return cursor
            depth -= 1
            cursor += 1
            continue
        if depth == 0 and _field_start_at(source, cursor):
            return cursor
        cursor += 1
    if depth != 0:
        raise ExpressionSyntaxError("SP-002 NP-003 missing closing brace")
    return len(source)


def _field_start_at(source: str, index: int) -> bool:
    if index == 0:
        boundary = True
    else:
        boundary = source[index - 1].isspace() or source[index - 1] == ","
    if not boundary:
        return False
    return re.match(r"[A-Za-z_][A-Za-z0-9_]*\s*:", source[index:]) is not None


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
            if self.current.kind == _Kind.LEFT_BRACE:
                left = self._struct_literal(left)
                continue
            entry = _BINARY.get(self.current.value)
            if entry is None or entry[0] < minimum_precedence:
                return left
            precedence, operator, node_type = entry
            self.take()
            if self.current.kind in {
                _Kind.EOF,
                _Kind.RIGHT_PAREN,
                _Kind.RIGHT_BRACE,
                _Kind.COMMA,
            }:
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

    def _struct_literal(self, type_expression: Expression) -> Expression:
        type_name = _qualified_type_name(type_expression)
        if type_name is None:
            raise ExpressionSyntaxError("EX-201A-002 invalid struct literal syntax")
        self.take()
        fields: list[StructLiteralFieldNode] = []
        seen: set[str] = set()
        if self.current.kind == _Kind.RIGHT_BRACE:
            self.take()
            return StructLiteralExpressionNode(type_name, ())
        while True:
            if self.current.kind != _Kind.IDENTIFIER:
                raise ExpressionSyntaxError("EX-201A-002 invalid struct literal syntax")
            field_name = self.take().value
            if self.current.kind != _Kind.COLON:
                raise ExpressionSyntaxError("EX-201A-002 invalid struct literal syntax")
            self.take()
            if self.current.kind in {_Kind.RIGHT_BRACE, _Kind.COMMA, _Kind.EOF}:
                raise ExpressionSyntaxError("EX-201A-002 invalid struct literal syntax")
            if field_name in seen:
                raise ExpressionSyntaxError("EX-201A-001 duplicate struct literal field")
            seen.add(field_name)
            fields.append(StructLiteralFieldNode(field_name, ExpressionNode(self.parse(0))))
            if self.current.kind == _Kind.RIGHT_BRACE:
                self.take()
                return StructLiteralExpressionNode(type_name, tuple(fields))
            if self.current.kind == _Kind.COMMA:
                self.take()
                if self.current.kind == _Kind.RIGHT_BRACE:
                    raise ExpressionSyntaxError("EX-201A-002 invalid struct literal syntax")
                continue
            if self.current.kind == _Kind.IDENTIFIER and self._next_kind() == _Kind.COLON:
                continue
            raise ExpressionSyntaxError("EX-201A-002 invalid struct literal syntax")

    def _next_kind(self) -> _Kind:
        if self.index + 1 >= len(self.tokens):
            return _Kind.EOF
        return self.tokens[self.index + 1].kind

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


def _qualified_type_name(expression: Expression) -> str | None:
    if isinstance(expression, IdentifierNode):
        return expression.name
    if isinstance(expression, QualifiedIdentifierNode):
        return ".".join((*expression.path, expression.symbol))
    if isinstance(expression, MemberAccessNode):
        base = _qualified_type_name(expression.object)
        if base is None:
            return None
        return f"{base}.{expression.member}"
    return None


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
            "{": _Kind.LEFT_BRACE,
            "}": _Kind.RIGHT_BRACE,
            ":": _Kind.COLON,
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
