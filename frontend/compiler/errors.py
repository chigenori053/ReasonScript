from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CompilerErrorCode(str, Enum):
    INVALID_AST = "compiler.invalid_ast"
    SCHEMA_VIOLATION = "compiler.schema_violation"
    LOWERING_FAILURE = "compiler.lowering_failure"
    UNSUPPORTED_NODE = "compiler.unsupported_node"
    INVALID_POLICY = "compiler.invalid_policy"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class CompilerError(ValueError):
    code: CompilerErrorCode
    node_id: str | None
    message: str
    severity: Severity = Severity.ERROR

    def __str__(self) -> str:
        location = f" for node {self.node_id}" if self.node_id else ""
        return f"{self.code.value}{location}: {self.message} ({self.severity.value})"
