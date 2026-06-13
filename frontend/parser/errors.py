from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ParserErrorCode(str, Enum):
    UNKNOWN_KEYWORD = "syntax.unknown_keyword"
    MISSING_ARGUMENT = "syntax.missing_argument"
    MALFORMED_STATEMENT = "syntax.malformed_statement"
    UNTERMINATED_STRING = "syntax.unterminated_string"
    DUPLICATE_GOAL = "semantic.duplicate_goal"
    DUPLICATE_INITIAL_STATE = "semantic.duplicate_initial_state"
    MISSING_GOAL = "semantic.missing_goal"
    MISSING_INITIAL_STATE = "semantic.missing_initial_state"
    INVALID_URI = "semantic.invalid_uri"
    AST_VALIDATION = "validation.ast_abi"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class ParserError(ValueError):
    code: ParserErrorCode
    line: int
    column: int
    message: str
    severity: Severity = Severity.ERROR

    def __str__(self) -> str:
        return (
            f"{self.code.value} at {self.line}:{self.column}: "
            f"{self.message} ({self.severity.value})"
        )
