"""ReasonScript LSP Phase 1 core data model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

SCHEMA = "reasonscript-lsp/0.1"


class DiagnosticSeverity(str, Enum):
    ERROR = "Error"
    WARNING = "Warning"
    INFORMATION = "Information"
    HINT = "Hint"


@dataclass(frozen=True, order=True)
class Position:
    line: int
    character: int


@dataclass(frozen=True, order=True)
class Range:
    start: Position
    end: Position


@dataclass(frozen=True)
class Location:
    uri: str
    range: Range


@dataclass(frozen=True)
class Diagnostic:
    severity: DiagnosticSeverity
    code: str
    message: str
    location: Location
    data: Any = None


class SymbolKind(int, Enum):
    FILE = 1
    MODULE = 2
    NAMESPACE = 3
    PACKAGE = 4
    CLASS = 5
    METHOD = 6
    PROPERTY = 7
    FIELD = 8
    CONSTRUCTOR = 9
    ENUM = 10
    INTERFACE = 11
    FUNCTION = 12
    VARIABLE = 13
    CONSTANT = 14
    STRING = 15
    NUMBER = 16
    BOOLEAN = 17
    ARRAY = 18
    OBJECT = 19
    KEY = 20
    NULL = 21
    ENUM_MEMBER = 22
    STRUCT = 23
    EVENT = 24
    OPERATOR = 25
    TYPE_PARAMETER = 26


@dataclass(frozen=True)
class DocumentSymbol:
    name: str
    detail: str
    kind: int
    range: Range
    selection_range: Range
    children: tuple[DocumentSymbol, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "detail": self.detail,
            "kind": int(self.kind),
            "range": {
                "start": {"line": self.range.start.line, "character": self.range.start.character},
                "end": {"line": self.range.end.line, "character": self.range.end.character},
            },
            "selectionRange": {
                "start": {"line": self.selection_range.start.line, "character": self.selection_range.start.character},
                "end": {"line": self.selection_range.end.line, "character": self.selection_range.end.character},
            },
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    module: str
    visibility: str
    location: Location
    detail: str = ""


@dataclass(frozen=True)
class CompletionItem:
    label: str
    kind: str
    detail: str = ""
    documentation: str = ""


@dataclass(frozen=True)
class Hover:
    contents: str | dict[str, Any]
    range: Range | None = None


@dataclass(frozen=True)
class TextEdit:
    range: Range
    new_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "range": {
                "start": {"line": self.range.start.line, "character": self.range.start.character},
                "end": {"line": self.range.end.line, "character": self.range.end.character},
            },
            "newText": self.new_text,
        }


@dataclass(frozen=True)
class WorkspaceEdit:
    changes: dict[str, list[TextEdit]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "changes": {
                uri: [edit.to_dict() for edit in edits]
                for uri, edits in self.changes.items()
            }
        }


@dataclass(frozen=True)
class CodeAction:
    title: str
    kind: str = "quickfix"
    diagnostics: tuple[Diagnostic, ...] = ()
    is_preferred: bool = False
    edit: WorkspaceEdit | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "title": self.title,
            "kind": self.kind,
        }
        if self.is_preferred:
            res["isPreferred"] = True
        if self.edit is not None:
            res["edit"] = self.edit.to_dict()
        return res


@dataclass(frozen=True)
class DocumentState:
    uri: str
    version: int
    text: str
    ast: Any | None
    diagnostics: tuple[Diagnostic, ...]
    symbols: tuple[Symbol, ...]


def position(line: int, character: int) -> Position:
    return Position(max(line, 0), max(character, 0))


def range_for(line: int, start: int, text: str) -> Range:
    return Range(position(line, start), position(line, start + len(text)))


def point_range(line: int, character: int) -> Range:
    return Range(position(line, character), position(line, character))


@dataclass(frozen=True)
class ParameterInformation:
    label: str
    documentation: str = ""

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {"label": self.label}
        if self.documentation:
            res["documentation"] = self.documentation
        return res


@dataclass(frozen=True)
class SignatureInformation:
    label: str
    documentation: str = ""
    parameters: tuple[ParameterInformation, ...] = ()
    active_parameter: int = 0

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "label": self.label,
            "parameters": [p.to_dict() for p in self.parameters],
            "activeParameter": self.active_parameter,
        }
        if self.documentation:
            res["documentation"] = {"kind": "markdown", "value": self.documentation}
        return res


@dataclass(frozen=True)
class SignatureHelp:
    signatures: tuple[SignatureInformation, ...]
    active_signature: int = 0
    active_parameter: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "signatures": [s.to_dict() for s in self.signatures],
            "activeSignature": self.active_signature,
            "activeParameter": self.active_parameter,
        }


@dataclass(frozen=True)
class SemanticTokensLegend:
    token_types: tuple[str, ...]
    token_modifiers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "tokenTypes": list(self.token_types),
            "tokenModifiers": list(self.token_modifiers),
        }


@dataclass(frozen=True)
class SemanticTokens:
    data: tuple[int, ...]
    result_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {"data": list(self.data)}
        if self.result_id is not None:
            res["resultId"] = self.result_id
        return res


@dataclass(frozen=True)
class FormattingOptions:
    tab_size: int = 4
    insert_spaces: bool = True
