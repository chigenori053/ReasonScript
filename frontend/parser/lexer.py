from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

from .errors import ParserError, ParserErrorCode

KEYWORDS = {"goal", "state", "transition", "constraint", "context", "import"}


class TokenType(str, Enum):
    KEYWORD = "Keyword"
    IDENTIFIER = "Identifier"
    STRING = "String"
    NUMBER = "Number"
    URI = "URI"
    NEWLINE = "NewLine"
    EOF = "EOF"


@dataclass(frozen=True)
class Token:
    token_type: TokenType
    value: str
    line: int
    column: int


def tokenize(source: str) -> tuple[Token, ...]:
    tokens: list[Token] = []
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
            tokens.append(Token(TokenType.NEWLINE, "\n", line, column))
            index += 1
            line += 1
            column = 1
            continue
        if char in {'"', "'"}:
            token, index, column = _string(source, index, line, column)
            tokens.append(token)
            continue

        start = index
        start_column = column
        while index < len(source) and not source[index].isspace():
            index += 1
            column += 1
        value = source[start:index]
        tokens.append(Token(_classify(value), value, line, start_column))

    tokens.append(Token(TokenType.EOF, "", line, column))
    return tuple(tokens)


def _string(
    source: str, index: int, line: int, column: int
) -> tuple[Token, int, int]:
    quote = source[index]
    start_column = column
    index += 1
    column += 1
    value: list[str] = []
    while index < len(source) and source[index] != quote:
        if source[index] == "\n":
            raise ParserError(
                ParserErrorCode.UNTERMINATED_STRING,
                line,
                start_column,
                "string literals cannot cross a line boundary",
            )
        if source[index] == "\\" and index + 1 < len(source):
            index += 1
            column += 1
        value.append(source[index])
        index += 1
        column += 1
    if index >= len(source):
        raise ParserError(
            ParserErrorCode.UNTERMINATED_STRING,
            line,
            start_column,
            "unterminated string literal",
        )
    return Token(TokenType.STRING, "".join(value), line, start_column), index + 1, column + 1


def _classify(value: str) -> TokenType:
    if value in KEYWORDS:
        return TokenType.KEYWORD
    if _is_number(value):
        return TokenType.NUMBER
    parsed = urlparse(value)
    if parsed.scheme and "://" in value:
        return TokenType.URI
    return TokenType.IDENTIFIER


def _is_number(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return any(char.isdigit() for char in value)
