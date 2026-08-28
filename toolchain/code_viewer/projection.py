"""Source → ViewerDocument. The only place CodeViewer touches the compiler.

Read-only consumer of the existing pipeline (parse / project_program /
compile_program / execution_plan_for) — no new compilation path is
introduced. Each stage is attempted independently (see design doc §9): a
failure at one stage still lets earlier stages render, and later stages
degrade to a diagnostic instead of taking the whole viewer down.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from frontend.ast import to_json_value as semantic_to_json_value
from frontend.language_surface.integration import (
    compile_program,
    execution_plan_for,
    project_program,
)
from frontend.language_surface.lexer import tokenize
from frontend.language_surface.namespace import NamespaceResolutionError
from frontend.language_surface.nodes import to_json_value as surface_to_json_value
from frontend.language_surface.parser import SurfaceSyntaxError, parse
from frontend.language_surface.validation import SurfaceValidationError
from frontend.lsp.model import Diagnostic, DiagnosticSeverity, Location, point_range

from . import stages as _stages
from .anchors import scan_anchors
from .model import SCHEMA, Stage, StageView, TokenSpan, ViewerDocument


class ProjectionError(Exception):
    """Raised only for CLI-level failures (unknown --module), never for
    ordinary source errors — those become unavailable stages, not exceptions."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def project(source: str, path: Path, *, module: str | None = None) -> ViewerDocument:
    lines = tuple(source.splitlines())
    anchors = scan_anchors(source)
    tokens = _token_spans(source)

    stages: dict[Stage, StageView] = {
        Stage.SOURCE: StageView(Stage.SOURCE, nodes=(), available=True, diagnostics=()),
    }

    try:
        program = parse(source)
    except SurfaceSyntaxError as error:
        diagnostic = _diagnostic(path, "SyntaxError", str(error))
        for stage in (Stage.SURFACE, Stage.SEMANTIC, Stage.IR, Stage.PLAN):
            stages[stage] = StageView(stage, nodes=(), available=False, diagnostics=(diagnostic,))
        return _document(path, lines, tokens, anchors, stages, module_names=(), active_module=None)

    module_names = tuple(m.name for m in program.modules)
    module_index = _resolve_module_index(module_names, module)
    active_module = module_names[module_index] if module_names else None

    stages[Stage.SURFACE] = StageView(
        Stage.SURFACE,
        nodes=_stages.flatten(surface_to_json_value(program), resolve_anchor=_surface_anchor),
        available=True,
        diagnostics=(),
    )

    semantic_module_json = None
    semantic_failure: tuple[str, str] | None = None
    try:
        semantic_modules = project_program(program)
        if module_index < len(semantic_modules):
            semantic_module_json = semantic_to_json_value(semantic_modules[module_index])
    except (SurfaceValidationError, NamespaceResolutionError) as error:
        semantic_failure = ("ValidationError", str(error))
    except Exception as error:  # pipeline.py treats unclassified failures the same way
        semantic_failure = ("CompilerError", str(error))

    if semantic_failure is not None:
        diagnostic = _diagnostic(path, *semantic_failure)
        for stage in (Stage.SEMANTIC, Stage.IR, Stage.PLAN):
            stages[stage] = StageView(stage, nodes=(), available=False, diagnostics=(diagnostic,))
        return _document(path, lines, tokens, anchors, stages, module_names, active_module)

    reason_ir = None
    ir_failure: tuple[str, str] | None = None
    try:
        reason_irs = compile_program(program)
        if module_index < len(reason_irs):
            reason_ir = reason_irs[module_index]
    except (SurfaceValidationError, NamespaceResolutionError) as error:
        ir_failure = ("ValidationError", str(error))
    except Exception as error:  # pipeline.py treats unclassified failures the same way
        ir_failure = ("CompilerError", str(error))

    if ir_failure is not None:
        diagnostic = _diagnostic(path, *ir_failure)
        stages[Stage.SEMANTIC] = StageView(
            Stage.SEMANTIC,
            nodes=_stages.flatten(semantic_module_json, resolve_anchor=lambda n: _semantic_anchor(n, {}))
            if semantic_module_json is not None
            else (),
            available=semantic_module_json is not None,
            diagnostics=(),
        )
        stages[Stage.IR] = StageView(Stage.IR, nodes=(), available=False, diagnostics=(diagnostic,))
        stages[Stage.PLAN] = StageView(Stage.PLAN, nodes=(), available=False, diagnostics=(diagnostic,))
        return _document(path, lines, tokens, anchors, stages, module_names, active_module)

    transition_symbol = _transition_symbol_map(reason_ir) if reason_ir is not None else {}

    stages[Stage.SEMANTIC] = StageView(
        Stage.SEMANTIC,
        nodes=_stages.flatten(
            semantic_module_json, resolve_anchor=lambda n: _semantic_anchor(n, transition_symbol)
        )
        if semantic_module_json is not None
        else (),
        available=semantic_module_json is not None,
        diagnostics=(),
    )

    if reason_ir is None:
        diagnostic = _diagnostic(path, "CompilerError", "Reason IR unavailable for the selected module")
        stages[Stage.IR] = StageView(Stage.IR, nodes=(), available=False, diagnostics=(diagnostic,))
        stages[Stage.PLAN] = StageView(Stage.PLAN, nodes=(), available=False, diagnostics=(diagnostic,))
        return _document(path, lines, tokens, anchors, stages, module_names, active_module)

    stages[Stage.IR] = StageView(
        Stage.IR,
        nodes=_stages.flatten(reason_ir, resolve_anchor=lambda n: _semantic_anchor(n, transition_symbol)),
        available=True,
        diagnostics=(),
    )

    try:
        plan = execution_plan_for(reason_ir)
    except Exception as error:
        diagnostic = _diagnostic(path, "CompilerError", str(error))
        stages[Stage.PLAN] = StageView(Stage.PLAN, nodes=(), available=False, diagnostics=(diagnostic,))
        return _document(path, lines, tokens, anchors, stages, module_names, active_module)

    stages[Stage.PLAN] = StageView(
        Stage.PLAN,
        nodes=_stages.flatten(plan, resolve_anchor=lambda n: _plan_anchor(n, transition_symbol)),
        available=True,
        diagnostics=(),
    )

    return _document(path, lines, tokens, anchors, stages, module_names, active_module)


def _document(path, lines, tokens, anchors, stages, module_names, active_module) -> ViewerDocument:
    ok = all(view.available for view in stages.values())
    return ViewerDocument(
        schema=SCHEMA,
        source_path=str(path),
        source_lines=lines,
        tokens=tokens,
        anchors=anchors,
        stages=stages,
        module_names=module_names,
        active_module=active_module,
        ok=ok,
    )


def _resolve_module_index(module_names: tuple[str, ...], requested: str | None) -> int:
    if requested is None:
        return 0
    if requested in module_names:
        return module_names.index(requested)
    raise ProjectionError("CV-003", f"module not found in source: {requested}")


def _transition_symbol_map(reason_ir: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for transition in reason_ir.get("transitions", ()):
        if not isinstance(transition, Mapping):
            continue
        transition_id = transition.get("transition_id")
        effect = transition.get("effect")
        if isinstance(transition_id, str) and isinstance(effect, Mapping):
            calculation = effect.get("calculation")
            if isinstance(calculation, str):
                result[transition_id] = calculation
    return result


_ANCHORED_SURFACE_NODE_TYPES = {
    "ModuleNode",
    "CalculationNode",
    "FunctionDeclarationNode",
    "StructDeclarationNode",
    "EnumDeclarationNode",
}


def _surface_anchor(node: Mapping[str, Any]) -> str | None:
    if node.get("node_type") in _ANCHORED_SURFACE_NODE_TYPES:
        name = node.get("name")
        return name if isinstance(name, str) else None
    return None


def _semantic_anchor(node: Mapping[str, Any], transition_symbol: Mapping[str, str]) -> str | None:
    if node.get("node_type") == "ModuleNode":
        node_id = node.get("node_id")
        return node_id if isinstance(node_id, str) else None
    transition_id = node.get("transition_id")
    if isinstance(transition_id, str):
        return transition_symbol.get(transition_id)
    effect = node.get("effect")
    if isinstance(effect, Mapping):
        calculation = effect.get("calculation")
        if isinstance(calculation, str):
            return calculation
    return None


def _plan_anchor(node: Mapping[str, Any], transition_symbol: Mapping[str, str]) -> str | None:
    transition_id = node.get("transition_id")
    if isinstance(transition_id, str):
        return transition_symbol.get(transition_id)
    return None


def _token_spans(source: str) -> tuple[TokenSpan, ...]:
    try:
        tokens = tokenize(source)
    except ValueError:
        return ()
    return tuple(
        TokenSpan(line=token.line, column=token.column, text=token.value, token_type=token.token_type.value)
        for token in tokens
        if token.token_type.value not in {"NEWLINE", "EOF"}
    )


_LOCATION_PATTERN = re.compile(r"at\s+(\d+):(\d+)")


def _diagnostic(path: Path, code: str, message: str) -> Diagnostic:
    match = _LOCATION_PATTERN.search(message)
    line = max(int(match.group(1)) - 1, 0) if match else 0
    character = max(int(match.group(2)) - 1, 0) if match else 0
    return Diagnostic(
        DiagnosticSeverity.ERROR,
        code,
        message,
        Location(str(path), point_range(line, character)),
    )
