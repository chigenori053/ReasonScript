"""Unified Compiler Frontend API shared by CLI and LSP.

Provides deterministic analysis pipeline:
  lexer -> parser -> name resolution -> type check -> completed.
Guarantees panic / exception isolation by catching unexpected errors and
returning ICE-0001 diagnostics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from frontend.language_surface import (
    SurfaceSyntaxError,
    SurfaceValidationError,
    parse_unresolved,
    tokenize,
    validate,
)
from frontend.language_surface.namespace import (
    NamespaceResolutionError,
    resolve_program,
)
from frontend.language_surface.parser import (
    SurfaceReservedConstructError,
    _restore_source_locations,
    _source_location_index,
)
import difflib
from toolchain.diagnostics import (
    Diagnostic,
    DiagnosticFix,
    create_fix,
    diagnostic_from_parts,
)


KNOWN_SUGGESTIONS = (
    "model", "module", "pub", "fn", "struct", "enum", "const", "let",
    "goal", "state", "constraint", "transition", "relation", "calculation",
    "reason_graph", "execution_plan", "if", "elif", "else", "match", "when",
    "for", "while", "loop", "break", "continue", "return", "input", "print",
    "true", "false", "some", "none",
    "runtime", "vision", "planning", "agent", "world",
    "search", "plan", "predict", "simulate",
    "World", "Scene", "Entity", "Object", "Relation", "Snapshot",
)


def _suggest_similar(name: str) -> str | None:
    matches = difflib.get_close_matches(name, KNOWN_SUGGESTIONS, n=1, cutoff=0.6)
    return matches[0] if matches else None


@dataclass(frozen=True)
class FrontendRequest:
    """Request object passed to CompilerFrontend."""

    source: str
    filename: str = "<anonymous>"
    uri: str = ""
    compiler_mode: str = "check"
    cancel_token: Any = None
    source_context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FrontendResult:
    """Result object returned by CompilerFrontend."""

    ok: bool
    diagnostics: tuple[Diagnostic, ...]
    ast: Any = None
    symbols: tuple[Any, ...] = ()
    phase_reached: str = "completed"
    metadata: dict[str, Any] = field(default_factory=dict)


def _extract_line_column(message: str) -> tuple[int | None, int | None]:
    """Extract line and column numbers from error message text if present."""
    # Pattern: at X:Y or starting at X:Y
    m = re.search(r"(?:at|starting at)\s+(\d+):(\d+)", message)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Pattern: at line X, column Y
    m = re.search(r"at line\s+(\d+)(?:,\s*column\s+(\d+))?", message, re.IGNORECASE)
    if m:
        line = int(m.group(1))
        col = int(m.group(2)) if m.group(2) else None
        return line, col

    # Pattern: line X
    m = re.search(r"line\s+(\d+)", message, re.IGNORECASE)
    if m:
        return int(m.group(1)), None

    return None, None


class CompilerFrontend:
    """Unified Compiler Frontend for CLI and LSP analysis."""

    @classmethod
    def analyze(cls, request: FrontendRequest) -> FrontendResult:
        source = request.source
        filename = request.filename or "<anonymous>"
        current_phase = "lexer"

        try:
            # Phase 1: Lexer
            current_phase = "lexer"
            try:
                tokenize(source)
            except ValueError as error:
                err_msg = str(error)
                line, col = _extract_line_column(err_msg)
                code = "LEX-0001"
                help_text = ""
                fixes_list: list[DiagnosticFix] = []
                if "unterminated string" in err_msg:
                    code = "LEX-0002"
                    help_text = "Add closing quote to terminate string literal."
                    fixes_list.append(create_fix(title="Close string literal", replacement='"'))
                elif "unsupported character" in err_msg:
                    help_text = "Remove unsupported character or replace with valid ReasonScript syntax."

                diag = diagnostic_from_parts(
                    code=code,
                    severity="ERROR",
                    category="LEX",
                    message=err_msg,
                    file=filename,
                    line=line,
                    column=col,
                    title="Lexical Error",
                    help=help_text,
                    fixes=fixes_list,
                )
                return FrontendResult(
                    ok=False,
                    diagnostics=(diag,),
                    phase_reached="lexer",
                )

            # Phase 2: Parser
            current_phase = "parser"
            try:
                program = parse_unresolved(source)
            except SurfaceReservedConstructError as error:
                line, col = _extract_line_column(str(error))
                code = getattr(error, "code", "LL-002-RESERVED-TOP-LEVEL-CONSTRUCT")
                help_text = "Reserved top-level construct. Replace with 'model' (preferred) or 'module'."
                fixes_list = [
                    create_fix(title="Replace with 'model'", replacement="model"),
                    create_fix(title="Replace with 'module'", replacement="module"),
                ]
                diag = diagnostic_from_parts(
                    code=code,
                    severity="ERROR",
                    category="PAR",
                    message=str(error),
                    file=filename,
                    line=line,
                    column=col,
                    title="Reserved Construct",
                    help=help_text,
                    fixes=fixes_list,
                )
                return FrontendResult(
                    ok=False,
                    diagnostics=(diag,),
                    phase_reached="parser",
                )
            except SurfaceSyntaxError as error:
                err_msg = str(error)
                line, col = _extract_line_column(err_msg)
                code = "PAR-0001"
                help_text = ""
                fixes_list = []
                if "invalid package declaration" in err_msg.lower():
                    code = "PAR-0004"
                    help_text = "Remove trailing semicolon; package declarations do not take semicolons."
                    fixes_list.append(create_fix(title="Remove semicolon", replacement="package"))

                diag = diagnostic_from_parts(
                    code=code,
                    severity="ERROR",
                    category="PAR",
                    message=err_msg,
                    file=filename,
                    line=line,
                    column=col,
                    title="Syntax Error",
                    help=help_text,
                    fixes=fixes_list,
                )
                return FrontendResult(
                    ok=False,
                    diagnostics=(diag,),
                    phase_reached="parser",
                )

            # Phase 3: Name Resolution
            current_phase = "name_resolution"
            source_locations = _source_location_index(program)
            try:
                program, resolved_symbols = resolve_program(program)
                _restore_source_locations(program, source_locations)
            except NamespaceResolutionError as error:
                msg = str(error)
                line, col = _extract_line_column(msg)
                code = "NAM-0001"
                help_text = ""
                fixes_list = []
                if "RV-2" in msg or "RuntimeNamespaceCannotBeImported" in msg:
                    help_text = "The 'runtime' namespace is built-in and cannot be explicitly imported. Call 'runtime.<api>' directly."
                    fixes_list.append(create_fix(title="Remove import runtime", replacement=""))
                elif "ModuleNotFound" in msg or "import target does not exist" in msg:
                    code = "NAM-0002"
                    m = re.search(r"(?:ModuleNotFound|import target does not exist):\s*([A-Za-z0-9_.]+)", msg)
                    if m:
                        sim = _suggest_similar(m.group(1).split(".")[-1])
                        if sim:
                            help_text = f"Did you mean '{sim}'?"
                            fixes_list.append(create_fix(title=f"Change to '{sim}'", replacement=sim))
                elif "unknown" in msg.lower() or "does not exist" in msg:
                    code = "NAM-0003"
                    m = re.search(r"(?:unknown symbol|does not exist):\s*([A-Za-z0-9_.]+)", msg)
                    if m:
                        sim = _suggest_similar(m.group(1).split(".")[-1])
                        if sim:
                            help_text = f"Did you mean '{sim}'?"
                            fixes_list.append(create_fix(title=f"Change to '{sim}'", replacement=sim))
                elif "private symbol" in msg:
                    code = "NAM-0004"
                    help_text = "Add 'pub' keyword to declaration in defining module to make it accessible."
                elif "NAM-2004" in msg or "Js." in msg or "ModuleNotFound: Js" in msg or "does not exist: Js" in msg:
                    code = "NAM-2004"
                    help_text = "Use ReasonScript standard output API 'Console.log' or 'print' instead."
                    fixes_list = [
                        create_fix(title="Replace with 'Console.log'", replacement="Console.log"),
                        create_fix(title="Replace with 'print'", replacement="print"),
                    ]

                diag = diagnostic_from_parts(
                    code=code,
                    severity="ERROR",
                    category="NAM",
                    message=msg,
                    file=filename,
                    line=line,
                    column=col,
                    title="Name Resolution Error" if code != "NAM-2004" else "Unsupported JavaScript API",
                    help=help_text,
                    fixes=fixes_list,
                )
                return FrontendResult(
                    ok=False,
                    diagnostics=(diag,),
                    phase_reached="name_resolution",
                )

            # Phase 4: Type Check & Validation
            current_phase = "type_check"
            try:
                validate(program)
            except SurfaceValidationError as error:
                msg = str(error)
                line, col = _extract_line_column(msg)
                code = "TYP-0001"
                cat = "TYP"
                title = "Type Validation Error"
                help_text = ""
                fixes_list = []
                if "NAM-2004" in msg or "Js." in msg:
                    code = "NAM-2004"
                    cat = "NAM"
                    title = "Unsupported JavaScript API"
                    help_text = "Use ReasonScript standard output API 'Console.log' or 'print' instead."
                    fixes_list = [
                        create_fix(title="Replace with 'Console.log'", replacement="Console.log"),
                        create_fix(title="Replace with 'print'", replacement="print"),
                    ]
                elif "FN-005" in msg or "function return mismatch" in msg:
                    code = "TYP-0002"
                    help_text = "Change function return type annotation or return a value matching the declared type."

                diag = diagnostic_from_parts(
                    code=code,
                    severity="ERROR",
                    category=cat,
                    message=msg,
                    file=filename,
                    line=line,
                    column=col,
                    title=title,
                    help=help_text,
                    fixes=fixes_list,
                )
                return FrontendResult(
                    ok=False,
                    diagnostics=(diag,),
                    phase_reached="type_check",
                )

            # Completed
            symbols_tuple = ()
            if isinstance(resolved_symbols, dict):
                symbols_tuple = tuple(resolved_symbols.values())
            elif isinstance(resolved_symbols, (list, tuple)):
                symbols_tuple = tuple(resolved_symbols)

            return FrontendResult(
                ok=True,
                diagnostics=(),
                ast=program,
                symbols=symbols_tuple,
                phase_reached="completed",
            )

        except Exception as error:
            # Panic / Exception Isolation: Return ICE-0001
            line, col = _extract_line_column(str(error))
            diag = diagnostic_from_parts(
                code="ICE-0001",
                severity="ERROR",
                category="ICE",
                message=f"Internal compiler error during {current_phase}: {error}",
                file=filename,
                line=line,
                column=col,
                title="Internal Compiler Error",
            )
            return FrontendResult(
                ok=False,
                diagnostics=(diag,),
                phase_reached=current_phase,
                metadata={"ice_exception": repr(error)},
            )
