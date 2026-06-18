"""Deterministic block parser for the Phase 1.1 surface."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .expressions import ExpressionSyntaxError, parse_expression, parse_pattern
from .lexer import tokenize
from .namespace import NamespaceResolutionError, resolve_program
from .nodes import (
    ActionNode,
    AssignmentStatementNode,
    AttributeNode,
    CalculationNode,
    ConceptNode,
    ConstraintNode,
    ConstStatementNode,
    ElseIfStatementNode,
    ElseStatementNode,
    EventNode,
    ExpressionStatementNode,
    FunctionDeclarationNode,
    GoalNode,
    GoalStatementNode,
    IfStatementNode,
    ImportNode,
    LetStatementNode,
    MatchArmNode,
    MatchStatementNode,
    ModuleNode,
    ObjectNode,
    ProgramNode,
    PrimitiveKind,
    PrimitiveTypeNode,
    RelationNode,
    RelationType,
    ReachStatementNode,
    RequireStatementNode,
    ResultStatementNode,
    ReturnStatementNode,
    StateKind,
    StateTypeNode,
    TransitionNode,
    Visibility,
)
from .validation import SurfaceValidationError, validate


class SurfaceSyntaxError(ValueError):
    pass


@dataclass
class _Cursor:
    lines: list[str]
    index: int = 0

    def current(self) -> str:
        if self.index >= len(self.lines):
            raise SurfaceSyntaxError("unexpected end of source")
        return self.lines[self.index]

    def take(self) -> str:
        value = self.current()
        self.index += 1
        return value


def parse(source: str) -> ProgramNode:
    try:
        tokenize(source)
    except ValueError as error:
        raise SurfaceSyntaxError(str(error)) from error
    cursor = _Cursor(_logical_lines(source))
    modules: list[ModuleNode] = []
    while cursor.index < len(cursor.lines):
        modules.append(_parse_module(cursor))
    program = ProgramNode(tuple(modules))
    try:
        program, _ = resolve_program(program)
        validate(program)
    except (SurfaceValidationError, NamespaceResolutionError) as error:
        raise SurfaceSyntaxError(str(error)) from error
    return program


def _logical_lines(source: str) -> list[str]:
    lines: list[str] = []
    for raw in source.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        line = re.sub(r"}\s*(elif\b)", r"}\n\1", line)
        line = re.sub(r"}\s*(else\b)", r"}\n\1", line)
        lines.extend(part.strip() for part in line.splitlines() if part.strip())
    return lines


def _parse_module(cursor: _Cursor) -> ModuleNode:
    match = re.fullmatch(
        r"(?:(pub)\s+)?module\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{",
        cursor.take(),
    )
    if not match:
        raise SurfaceSyntaxError("expected module declaration")
    visibility = Visibility.PUBLIC if match.group(1) else Visibility.PRIVATE
    body = _parse_body(cursor, context="module")
    return ModuleNode(match.group(2), visibility, tuple(body))


def _parse_body(cursor: _Cursor, *, context: str) -> list:
    nodes: list = []
    while cursor.index < len(cursor.lines):
        line = cursor.current()
        if line == "}":
            cursor.index += 1
            return nodes
        if line.startswith("transition "):
            nodes.append(_parse_transition(cursor))
        elif line.startswith("calculation ") or line.startswith("pub calculation "):
            nodes.append(_parse_calculation(cursor))
        elif line.startswith("fn ") or line.startswith("pub fn "):
            nodes.append(_parse_function(cursor))
        elif line.startswith("if "):
            nodes.append(_parse_if(cursor, context=context))
        elif line.startswith("match "):
            nodes.append(_parse_match(cursor, context=context))
        else:
            nodes.append(_parse_simple(cursor.take(), context=context))
    raise SurfaceSyntaxError(f"unterminated {context} block")


def _parse_simple(line: str, *, context: str):
    declarations = {
        "concept": ConceptNode,
        "object": ObjectNode,
        "event": EventNode,
        "action": ActionNode,
        "attribute": AttributeNode,
        "constraint": ConstraintNode,
    }
    for keyword, node_type in declarations.items():
        match = re.fullmatch(rf"{keyword}\s+(\S+)", line)
        if match:
            return node_type(match.group(1))
    match = re.fullmatch(r"goal\s+(\S+)", line)
    if match:
        return (
            GoalNode(match.group(1))
            if context == "module"
            else GoalStatementNode(match.group(1))
        )
    match = re.fullmatch(
        r"import\s+([A-Za-z_][A-Za-z0-9_.]*)(?:\s+as\s+([A-Za-z_]\w*))?",
        line,
    )
    if match:
        return ImportNode(tuple(match.group(1).split(".")), match.group(2))
    match = re.fullmatch(
        r"([A-Za-z_]\w*)\s+(IsA|PartOf|Cause|Dependency|Constraint|Temporal|Spatial|Similar)\s+([A-Za-z_]\w*)",
        line,
    )
    if match:
        return RelationNode(match.group(1), RelationType(match.group(2)), match.group(3))
    match = re.fullmatch(
        r"let\s+([A-Za-z_]\w*)(?:\s*:\s*([A-Za-z_]\w*))?\s*=\s*(.+)",
        line,
    )
    if match:
        return LetStatementNode(
            match.group(1),
            _expression(match.group(3)),
            _type_annotation(match.group(2)) if match.group(2) else None,
        )
    match = re.fullmatch(
        r"const\s+([A-Za-z_]\w*)(?:\s*:\s*([A-Za-z_]\w*))?\s*=\s*(.+)",
        line,
    )
    if match:
        return ConstStatementNode(
            match.group(1),
            _expression(match.group(3)),
            _type_annotation(match.group(2)) if match.group(2) else None,
        )
    match = re.fullmatch(r"result\s*=\s*(.+)", line)
    if match:
        return ResultStatementNode(_expression(match.group(1)))
    match = re.fullmatch(r"return\s+(.+)", line)
    if match:
        return ReturnStatementNode(_expression(match.group(1)))
    match = re.fullmatch(r"([A-Za-z_]\w*)\s*=\s*(.+)", line)
    if match:
        return AssignmentStatementNode(match.group(1), _expression(match.group(2)))
    match = re.fullmatch(r"requires?\s+([A-Za-z_]\w*)", line)
    if match:
        return RequireStatementNode(match.group(1))
    match = re.fullmatch(r"reach\s+([A-Za-z_]\w*)", line)
    if match:
        return ReachStatementNode(match.group(1))
    call = re.fullmatch(r"(.+\))", line)
    if call:
        return ExpressionStatementNode(_expression(call.group(1)))
    raise SurfaceSyntaxError(f"unsupported {context} statement: {line}")


def _parse_transition(cursor: _Cursor) -> TransitionNode:
    match = re.fullmatch(r"transition\s+([A-Za-z_]\w*)\s*\{", cursor.take())
    if not match:
        raise SurfaceSyntaxError("invalid transition declaration")
    name = match.group(1)
    from_state = ""
    to_state = ""
    body: list = []
    while cursor.index < len(cursor.lines):
        line = cursor.current()
        if line == "}":
            cursor.index += 1
            return TransitionNode(
                name, from_state, to_state, tuple(body)
            )
        if line.startswith("if "):
            body.append(_parse_if(cursor, context="transition"))
            continue
        if line.startswith("match "):
            body.append(_parse_match(cursor, context="transition"))
            continue
        cursor.index += 1
        state_match = re.fullmatch(r"([A-Za-z_]\w*)\s*->\s*([A-Za-z_]\w*)", line)
        if state_match:
            if from_state:
                raise SurfaceSyntaxError("transition has multiple state mappings")
            from_state, to_state = state_match.groups()
        else:
            body.append(_parse_simple(line, context="transition"))
    raise SurfaceSyntaxError("unterminated transition block")


def _parse_calculation(cursor: _Cursor) -> CalculationNode:
    match = re.fullmatch(
        r"(?:(pub)\s+)?calculation\s+([A-Za-z_]\w*)"
        r"(?:\s+goal:([A-Za-z_]\w*))?"
        r"(?:\s*->\s*([A-Za-z_]\w*))?\s*\{",
        cursor.take(),
    )
    if not match:
        raise SurfaceSyntaxError("invalid calculation declaration")
    body = _parse_body(cursor, context="calculation")
    visibility = Visibility.PUBLIC if match.group(1) else Visibility.PRIVATE
    return CalculationNode(
        match.group(2),
        match.group(3),
        tuple(body),
        visibility,
        _type_annotation(match.group(4)) if match.group(4) else None,
    )


def _parse_function(cursor: _Cursor) -> FunctionDeclarationNode:
    match = re.fullmatch(
        r"(?:(pub)\s+)?fn\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*\{",
        cursor.take(),
    )
    if not match:
        raise SurfaceSyntaxError("invalid function declaration")
    parameters = _parameters(match.group(3))
    body = _parse_body(cursor, context="function")
    visibility = Visibility.PUBLIC if match.group(1) else Visibility.PRIVATE
    return FunctionDeclarationNode(match.group(2), parameters, tuple(body), visibility)


def _parse_if(cursor: _Cursor, *, context: str) -> IfStatementNode:
    match = re.fullmatch(r"if\s+(.+)\s*\{", cursor.take())
    if not match:
        raise SurfaceSyntaxError("invalid if statement")
    body = tuple(_parse_body(cursor, context=context))
    elif_branches: list[ElseIfStatementNode] = []
    else_branch = None
    while cursor.index < len(cursor.lines) and cursor.current().startswith("elif "):
        branch = re.fullmatch(r"elif\s+(.+)\s*\{", cursor.take())
        if not branch:
            raise SurfaceSyntaxError("invalid elif statement")
        elif_branches.append(
            ElseIfStatementNode(
                _expression(branch.group(1)),
                tuple(_parse_body(cursor, context=context)),
            )
        )
    if cursor.index < len(cursor.lines) and cursor.current() == "else {":
        cursor.index += 1
        else_branch = ElseStatementNode(tuple(_parse_body(cursor, context=context)))
    return IfStatementNode(
        _expression(match.group(1)),
        body,
        tuple(elif_branches),
        else_branch,
    )


def _parse_match(cursor: _Cursor, *, context: str) -> MatchStatementNode:
    match = re.fullmatch(r"match\s+(.+)\s*\{", cursor.take())
    if not match:
        raise SurfaceSyntaxError("invalid match statement")
    arms: list[MatchArmNode] = []
    while cursor.index < len(cursor.lines):
        line = cursor.take()
        if line == "}":
            return MatchStatementNode(_expression(match.group(1)), tuple(arms))
        arm = re.fullmatch(r"(.+?)\s*=>\s*(.+)", line)
        if not arm:
            raise SurfaceSyntaxError(f"invalid match arm: {line}")
        arms.append(
            MatchArmNode(
                _pattern(arm.group(1)),
                (_parse_simple(arm.group(2).strip(), context=context),),
            )
        )
    raise SurfaceSyntaxError("unterminated match block")


def _expression(source: str):
    try:
        return parse_expression(source.strip())
    except ExpressionSyntaxError as error:
        raise SurfaceSyntaxError(str(error)) from error


def _pattern(source: str):
    try:
        return parse_pattern(source.strip())
    except ExpressionSyntaxError as error:
        raise SurfaceSyntaxError(str(error)) from error


def _type_annotation(source: str):
    try:
        return PrimitiveTypeNode(PrimitiveKind(source))
    except ValueError:
        pass
    try:
        return StateTypeNode(StateKind(source))
    except ValueError as error:
        raise SurfaceSyntaxError(f"TYPE-V001 unknown type: {source}") from error


def _parameters(source: str) -> tuple[str, ...]:
    text = source.strip()
    if not text:
        return ()
    parameters = tuple(part.strip() for part in text.split(","))
    seen: set[str] = set()
    for parameter in parameters:
        if not re.fullmatch(r"[A-Za-z_]\w*", parameter):
            raise SurfaceSyntaxError(f"FN-002 invalid parameter: {parameter}")
        if parameter in seen:
            raise SurfaceSyntaxError(f"FN-003 duplicate parameter: {parameter}")
        seen.add(parameter)
    return parameters
