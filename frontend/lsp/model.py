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


@dataclass(frozen=True)
class Hover:
    contents: str
    range: Range | None = None


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
