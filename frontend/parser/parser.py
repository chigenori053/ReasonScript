from __future__ import annotations

from frontend.ast import AstValidationError, ModuleNode, validate

from .ast_builder import AstBuilder
from .errors import ParserError, ParserErrorCode
from .lexer import Token, TokenType, tokenize

ARGUMENT_COUNTS = {
    "goal": 1,
    "state": 1,
    "transition": 3,
    "constraint": 1,
    "context": 1,
    "import": 1,
}


def parse(source: str) -> ModuleNode:
    tokens = tokenize(source)
    builder = AstBuilder()
    statement: list[Token] = []
    for token in tokens:
        if token.token_type in {TokenType.NEWLINE, TokenType.EOF}:
            if statement:
                _parse_statement(statement, builder)
                statement = []
            if token.token_type == TokenType.EOF:
                module = builder.build(token.line, token.column)
                try:
                    validate(module)
                except AstValidationError as error:
                    raise ParserError(
                        ParserErrorCode.AST_VALIDATION,
                        token.line,
                        token.column,
                        str(error),
                    ) from error
                return module
        else:
            statement.append(token)
    raise AssertionError("lexer did not emit EOF")


def _parse_statement(tokens: list[Token], builder: AstBuilder) -> None:
    first = tokens[0]
    if first.token_type != TokenType.KEYWORD:
        raise ParserError(
            ParserErrorCode.UNKNOWN_KEYWORD,
            first.line,
            first.column,
            f"unknown keyword: {first.value}",
        )
    keyword = first.value
    expected = ARGUMENT_COUNTS[keyword]
    actual = len(tokens) - 1
    if actual < expected:
        raise ParserError(
            ParserErrorCode.MISSING_ARGUMENT,
            first.line,
            first.column,
            f"{keyword} expects {expected} argument(s), received {actual}",
        )
    if actual > expected:
        raise ParserError(
            ParserErrorCode.MALFORMED_STATEMENT,
            tokens[expected + 1].line,
            tokens[expected + 1].column,
            f"{keyword} expects exactly {expected} argument(s)",
        )

    arguments = tokens[1:]
    _validate_argument_types(keyword, arguments)
    if keyword == "goal":
        builder.add_goal(arguments[0].value, first.line, first.column)
    elif keyword == "state":
        builder.add_state(arguments[0].value, first.line, first.column)
    elif keyword == "transition":
        builder.add_transition(*(token.value for token in arguments), first.line)
    elif keyword == "constraint":
        builder.add_constraint(arguments[0].value, first.line)
    elif keyword == "context":
        if arguments[0].token_type != TokenType.URI:
            raise ParserError(
                ParserErrorCode.INVALID_URI,
                arguments[0].line,
                arguments[0].column,
                "context requires an absolute URI",
            )
        builder.add_context(
            arguments[0].value, arguments[0].line, arguments[0].column
        )
    elif keyword == "import":
        builder.add_import(arguments[0].value)


def _validate_argument_types(keyword: str, arguments: list[Token]) -> None:
    allowed = {
        "goal": {TokenType.IDENTIFIER, TokenType.STRING},
        "state": {TokenType.IDENTIFIER, TokenType.STRING},
        "transition": {TokenType.IDENTIFIER, TokenType.STRING},
        "constraint": {TokenType.IDENTIFIER, TokenType.STRING},
        "context": {TokenType.URI},
        "import": {TokenType.IDENTIFIER, TokenType.STRING, TokenType.URI},
    }[keyword]
    for token in arguments:
        if token.token_type not in allowed:
            code = (
                ParserErrorCode.INVALID_URI
                if keyword == "context"
                else ParserErrorCode.MALFORMED_STATEMENT
            )
            raise ParserError(
                code,
                token.line,
                token.column,
                f"{keyword} does not accept {token.token_type.value} arguments",
            )
