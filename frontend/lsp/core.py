"""In-process ReasonScript LSP Phase 1 services."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from frontend.language_surface import SurfaceSyntaxError, parse

from .model import (
    CompletionItem,
    Diagnostic,
    DiagnosticSeverity,
    DocumentState,
    Hover,
    Location,
    Range,
    SCHEMA,
    Symbol,
    point_range,
    position,
    range_for,
)


KEYWORD_COMPLETIONS = (
    "package",
    "module",
    "import",
    "export",
    "struct",
    "enum",
    "const",
    "fn",
    "goal",
    "state",
    "constraint",
    "transition",
    "reason_graph",
    "execution_plan",
    "calculation",
    "let",
    "return",
    "requires",
    "reach",
)
RUNTIME_APIS = ("runtime.search", "runtime.plan", "runtime.predict", "runtime.simulate")
WORLD_TYPES = (
    "World",
    "Scene",
    "Entity",
    "Object",
    "Geometry",
    "Relation",
    "Event",
    "Snapshot",
    "SceneTemplate",
    "SimulationTrace",
)
PLANNING_TYPES = ("Goal", "Planner", "Plan", "PlanStep", "PlanResult")
AGENT_TYPES = ("Agent", "Task", "Decision", "Action", "Tool", "AgentResult")
REASONING_TYPES = ("Goal", "State", "Constraint", "ReasonGraph", "ExecutionPlan")
BUILTIN_SYMBOLS = tuple(
    Symbol(
        name=name,
        kind=(
            "RuntimeAPI"
            if name.startswith("runtime.")
            else "PlanningType"
            if name in PLANNING_TYPES
            else "AgentType"
            if name in AGENT_TYPES
            else "WorldType"
        ),
        module=(
            "runtime"
            if name.startswith("runtime.")
            else "planning"
            if name in PLANNING_TYPES
            else "agent"
            if name in AGENT_TYPES
            else "world"
        ),
        visibility="Public",
        location=Location("builtin://reasonscript-lsp", point_range(0, 0)),
        detail="ReasonScript built-in symbol",
    )
    for name in (*RUNTIME_APIS, *WORLD_TYPES, *PLANNING_TYPES, *AGENT_TYPES)
)


DECLARATION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("Module", r"(?:(?:pub|export)\s+)?module\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{"),
    ("Function", r"(?:(?:pub|export)\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
    ("Struct", r"(?:(?:pub|export)\s+)?struct\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{"),
    ("Enum", r"(?:(?:pub|export)\s+)?enum\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{"),
    ("Const", r"(?:(?:pub|export)\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ("Goal", r"goal\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ("State", r"state\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ("Constraint", r"constraint\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ("ReasonGraph", r"reason_graph\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{"),
    ("ExecutionPlan", r"execution_plan\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{"),
    ("World", r"world\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ("Scene", r"scene\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ("Entity", r"entity\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ("Object", r"object\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
)


@dataclass(frozen=True)
class _Token:
    text: str
    range: Range


def _word_at(text: str, position_line: int, character: int) -> _Token | None:
    lines = text.splitlines()
    if position_line < 0 or position_line >= len(lines):
        return None
    line = lines[position_line]
    character = min(max(character, 0), len(line))
    pattern = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
    for match in pattern.finditer(line):
        if match.start() <= character <= match.end():
            return _Token(match.group(0), range_for(position_line, match.start(), match.group(0)))
    return None


def _module_for_line(text: str, line_number: int) -> str:
    package = ""
    current = "main"
    for index, line in enumerate(text.splitlines()):
        if index > line_number:
            break
        package_match = re.match(r"\s*package\s+([A-Za-z_][A-Za-z0-9_.]*)", line)
        if package_match:
            package = package_match.group(1)
        module_match = re.match(
            r"\s*(?:(?:pub|export)\s+)?module\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{",
            line,
        )
        if module_match:
            current = module_match.group(1)
    return f"{package}.{current}" if package else current


def _scan_symbols(uri: str, text: str) -> tuple[Symbol, ...]:
    symbols: list[Symbol] = []
    package = ""
    current_module = "main"
    for line_number, raw_line in enumerate(text.splitlines()):
        line = raw_line.split("//", 1)[0]
        package_match = re.match(r"\s*package\s+([A-Za-z_][A-Za-z0-9_.]*)", line)
        if package_match:
            package = package_match.group(1)
            continue
        module_match = re.match(DECLARATION_PATTERNS[0][1], line.strip())
        if module_match:
            current_module = module_match.group(1)
        module = f"{package}.{current_module}" if package else current_module
        for kind, pattern in DECLARATION_PATTERNS:
            match = re.search(pattern, line)
            if match is None:
                continue
            name = match.group(1)
            start = match.start(1)
            visibility = "Public" if re.match(r"\s*(pub|export)\b", line) or kind not in {"Function", "Struct", "Enum", "Const"} else "Private"
            symbols.append(
                Symbol(
                    name=name,
                    kind=kind,
                    module=module if kind != "Module" else (f"{package}.{name}" if package else name),
                    visibility=visibility,
                    location=Location(uri, range_for(line_number, start, name)),
                    detail=f"{kind} {module}::{name}",
                )
            )
            break
    return tuple(symbols)


def _syntax_diagnostic(uri: str, message: str) -> Diagnostic:
    line = 0
    character = 0
    match = re.search(r"at\s+(\d+):(\d+)", message)
    if match:
        line = max(int(match.group(1)) - 1, 0)
        character = max(int(match.group(2)) - 1, 0)
    return Diagnostic(
        DiagnosticSeverity.ERROR,
        _diagnostic_code(message),
        message,
        Location(uri, point_range(line, character)),
    )


def _diagnostic_code(message: str) -> str:
    if "ModuleNotFound" in message or "import target does not exist" in message:
        return "UnknownModule"
    if "unknown" in message.lower() or "does not exist" in message:
        return "UnknownSymbol"
    if "private symbol" in message:
        return "VisibilityViolation"
    if "TYPE" in message or "type" in message.lower():
        return "TypeMismatch"
    return "SyntaxError"


class ReasonScriptLanguageServer:
    """Phase 1 language server core.

    The class intentionally exposes editor-neutral methods so tests and future
    transports can reuse the same analysis engine.
    """

    schema = SCHEMA

    def __init__(self) -> None:
        self.documents: dict[str, DocumentState] = {}
        self.symbols: dict[str, tuple[Symbol, ...]] = {}
        self.package_graph = None

    def open_document(self, uri: str, text: str, version: int = 1) -> DocumentState:
        return self._analyze(uri, text, version)

    def change_document(self, uri: str, text: str, version: int) -> DocumentState:
        return self._analyze(uri, text, version)

    def save_document(self, uri: str) -> DocumentState:
        return self.documents[uri]

    def scan_workspace(self, root: str | Path) -> tuple[Symbol, ...]:
        root_path = Path(root)
        self.load_package_graph(root_path)
        for path in sorted(root_path.rglob("*.rsn")):
            uri = path.resolve().as_uri()
            self._analyze(uri, path.read_text(encoding="utf-8"), 1)
        return self.workspace_symbols()

    def load_package_graph(self, root: str | Path):
        try:
            from toolchain.workspace import PackageGraphService

            self.package_graph = PackageGraphService().discover(root).graph
        except Exception:
            self.package_graph = None
        return self.package_graph

    def diagnostics(self, uri: str) -> tuple[Diagnostic, ...]:
        return self.documents[uri].diagnostics

    def completion(self, uri: str, line: int, character: int) -> tuple[CompletionItem, ...]:
        del line, character
        symbol_items = [
            CompletionItem(symbol.name, symbol.kind, symbol.detail)
            for symbol in self.workspace_symbols()
            if symbol.location.uri != "builtin://reasonscript-lsp"
        ]
        return tuple(
            [
                *(CompletionItem(label, "Keyword") for label in KEYWORD_COMPLETIONS),
                *(CompletionItem(label, "RuntimeAPI") for label in RUNTIME_APIS),
                *(CompletionItem(label, "WorldType") for label in WORLD_TYPES),
                *(CompletionItem(label, "PlanningType") for label in PLANNING_TYPES),
                *(CompletionItem(label, "AgentType") for label in AGENT_TYPES),
                *(CompletionItem(label, "ReasoningType") for label in REASONING_TYPES),
                *symbol_items,
            ]
        )

    def hover(self, uri: str, line: int, character: int) -> Hover | None:
        document = self.documents.get(uri)
        if document is None:
            return None
        token = _word_at(document.text, line, character)
        if token is None:
            return None
        symbol = self._resolve_token(uri, token.text, line)
        if symbol is None:
            return None
        return Hover(
            "\n".join(
                [
                    symbol.kind,
                    f"Name: {symbol.name}",
                    f"Type: {symbol.kind}",
                    f"Module: {symbol.module}",
                ]
            ),
            token.range,
        )

    def definition(self, uri: str, line: int, character: int) -> Location | None:
        document = self.documents.get(uri)
        if document is None:
            return None
        token = _word_at(document.text, line, character)
        if token is None:
            return None
        symbol = self._resolve_token(uri, token.text, line)
        return symbol.location if symbol is not None else None

    def references(self, uri: str, line: int, character: int) -> tuple[Location, ...]:
        document = self.documents.get(uri)
        if document is None:
            return ()
        token = _word_at(document.text, line, character)
        if token is None:
            return ()
        symbol = self._resolve_token(uri, token.text, line)
        name = symbol.name if symbol is not None else token.text.split(".")[-1]
        locations: list[Location] = []
        for state in self.documents.values():
            for line_number, raw_line in enumerate(state.text.splitlines()):
                for match in re.finditer(rf"\b{re.escape(name)}\b", raw_line):
                    locations.append(
                        Location(
                            state.uri,
                            range_for(line_number, match.start(), name),
                        )
                    )
        return tuple(locations)

    def workspace_symbols(self) -> tuple[Symbol, ...]:
        indexed = [symbol for symbols in self.symbols.values() for symbol in symbols]
        return tuple([*indexed, *BUILTIN_SYMBOLS])

    def _analyze(self, uri: str, text: str, version: int) -> DocumentState:
        ast = None
        diagnostics: tuple[Diagnostic, ...] = ()
        try:
            ast = parse(text)
        except SurfaceSyntaxError as error:
            diagnostics = (_syntax_diagnostic(uri, str(error)),)
        symbols = _scan_symbols(uri, text)
        state = DocumentState(uri, version, text, ast, diagnostics, symbols)
        self.documents[uri] = state
        self.symbols[uri] = symbols
        return state

    def _resolve_token(self, uri: str, token: str, line: int) -> Symbol | None:
        if token in RUNTIME_APIS or token in WORLD_TYPES or token in PLANNING_TYPES or token in AGENT_TYPES:
            return next(symbol for symbol in BUILTIN_SYMBOLS if symbol.name == token)
        name = token.split(".")[-1].split("::")[-1]
        module = _module_for_line(self.documents[uri].text, line)
        symbols = [
            symbol
            for symbol in self.workspace_symbols()
            if symbol.name == name or symbol.module == token
        ]
        if not symbols:
            return None
        same_module = [symbol for symbol in symbols if symbol.module == module]
        if same_module:
            return same_module[0]
        public = [symbol for symbol in symbols if symbol.visibility == "Public"]
        return public[0] if public else symbols[0]
