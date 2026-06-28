"""Positioned lexer for the Phase 1.1 block surface."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


KEYWORDS = {
    "action",
    "as",
    "attribute",
    "bool",
    "calculation",
    "concept",
    "constraint",
    "const",
    "elif",
    "else",
    "enum",
    "event",
    "false",
    "fn",
    "for",
    "goal",
    "if",
    "in",
    "import",
    "let",
    "loop",
    "map",
    "match",
    "module",
    "object",
    "none",
    "optional",
    "pub",
    "reach",
    "require",
    "requires",
    "result",
    "return",
    "set",
    "some",
    "struct",
    "transition",
    "true",
    "while",
    "break",
    "continue",
}


class SurfaceTokenType(str, Enum):
    KEYWORD = "Keyword"
    IDENTIFIER = "Identifier"
    NUMBER = "Number"
    OPERATOR = "Operator"
    DELIMITER = "Delimiter"
    NEWLINE = "NewLine"
    EOF = "EOF"


@dataclass(frozen=True)
class SurfaceToken:
    token_type: SurfaceTokenType
    value: str
    line: int
    column: int


def tokenize(source: str) -> tuple[SurfaceToken, ...]:
    tokens: list[SurfaceToken] = []
    index = 0
    line = 1
    column = 1
    while index < len(source):
        char = source[index]
        if char in " \t\r":
            index += 1
            column += 1
            continue
        if char == "\n":
            tokens.append(SurfaceToken(SurfaceTokenType.NEWLINE, "\n", line, column))
            index += 1
            line += 1
            column = 1
            continue
        if source.startswith("//", index):
            while index < len(source) and source[index] != "\n":
                index += 1
                column += 1
            continue
        if char in {'"', "'"}:
            quote = char
            start = index
            start_column = column
            index += 1
            column += 1
            while index < len(source) and source[index] != quote:
                if source[index] == "\n":
                    raise ValueError(
                        f"unterminated string at {line}:{start_column}"
                    )
                if source[index] == "\\" and index + 1 < len(source):
                    index += 1
                    column += 1
                index += 1
                column += 1
            if index >= len(source):
                raise ValueError(f"unterminated string at {line}:{start_column}")
            index += 1
            column += 1
            tokens.append(
                SurfaceToken(
                    SurfaceTokenType.IDENTIFIER,
                    source[start:index],
                    line,
                    start_column,
                )
            )
            continue
        matched = next(
            (
                operator
                for operator in (
                    "->",
                    "=>",
                    "::",
                    ">=",
                    "<=",
                    "==",
                    "!=",
                    "&&",
                    "||",
                )
                if source.startswith(operator, index)
            ),
            None,
        )
        if matched:
            tokens.append(
                SurfaceToken(SurfaceTokenType.OPERATOR, matched, line, column)
            )
            index += len(matched)
            column += len(matched)
            continue
        if char in "{}()[]:,.":
            tokens.append(
                SurfaceToken(SurfaceTokenType.DELIMITER, char, line, column)
            )
            index += 1
            column += 1
            continue
        if char in "=+-*/%><!|":
            tokens.append(
                SurfaceToken(SurfaceTokenType.OPERATOR, char, line, column)
            )
            index += 1
            column += 1
            continue
        start = index
        start_column = column
        while (
            index < len(source)
            and (source[index].isalnum() or source[index] == "_")
        ):
            index += 1
            column += 1
        if index == start:
            raise ValueError(f"unsupported character {char!r} at {line}:{column}")
        value = source[start:index]
        token_type = (
            SurfaceTokenType.KEYWORD
            if value in KEYWORDS
            else SurfaceTokenType.NUMBER
            if value.isdigit()
            else SurfaceTokenType.IDENTIFIER
        )
        tokens.append(SurfaceToken(token_type, value, line, start_column))
    tokens.append(SurfaceToken(SurfaceTokenType.EOF, "", line, column))
    return tuple(tokens)
