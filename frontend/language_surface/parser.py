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
    ArrayLiteralNode,
    BinaryExpressionNode,
    BreakStatementNode,
    CalculationNode,
    CallExpressionNode,
    ComparisonExpressionNode,
    ConceptNode,
    ConstDeclarationNode,
    ContinueStatementNode,
    ConstraintNode,
    ConstStatementNode,
    ArrayTypeNode,
    EnumDeclarationNode,
    EnumValueNode,
    ElseIfStatementNode,
    ElseStatementNode,
    EventNode,
    ExecutionPlanDeclarationNode,
    ExpressionNode,
    ExpressionStatementNode,
    ForStatementNode,
    FunctionDeclarationNode,
    GoalNode,
    GoalStatementNode,
    IfStatementNode,
    IdentifierNode,
    ImportNode,
    IndexAccessNode,
    LetStatementNode,
    LogicalExpressionNode,
    LoopStatementNode,
    MapEntryNode,
    MapLiteralNode,
    MapTypeNode,
    MatchArmNode,
    MatchStatementNode,
    ModuleNode,
    MemberAccessNode,
    NamedTypeNode,
    ObjectNode,
    OptionalTypeNode,
    PackageDeclarationNode,
    ParenthesizedExpressionNode,
    PlanStepNode,
    ProgramNode,
    PrimitiveKind,
    PrimitiveTypeNode,
    ReasonGraphDeclarationNode,
    ReasonGraphTransitionNode,
    RelationNode,
    RelationType,
    ReachStatementNode,
    RequireStatementNode,
    ResultStatementNode,
    ReturnStatementNode,
    RuntimeCallExpressionNode,
    RuntimeCallKind,
    RuntimeNamespaceNode,
    SetLiteralNode,
    SetTypeNode,
    SomeExpressionNode,
    StateDeclarationNode,
    StateKind,
    StateTypeNode,
    StructDeclarationNode,
    StructFieldNode,
    StructLiteralFieldNode,
    StructLiteralNode,
    FieldAssignmentStatementNode,
    IndexAssignmentStatementNode,
    TupleTypeNode,
    TupleLiteralNode,
    TransitionNode,
    UnaryExpressionNode,
    Visibility,
    WhileStatementNode,
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
    package: PackageDeclarationNode | None = None
    while cursor.index < len(cursor.lines):
        if cursor.current().startswith("package "):
            if modules or package is not None:
                raise SurfaceSyntaxError("PV-3 PackageMustAppearFirst")
            package = _parse_package(cursor)
            continue
        modules.append(_parse_module(cursor))
    program = ProgramNode(tuple(modules), package)
    try:
        program, _ = resolve_program(program)
        validate(program)
    except (SurfaceValidationError, NamespaceResolutionError) as error:
        raise SurfaceSyntaxError(str(error)) from error
    return program


def _parse_package(cursor: _Cursor) -> PackageDeclarationNode:
    match = re.fullmatch(r"package\s+([A-Za-z_][A-Za-z0-9_]*)", cursor.take())
    if not match:
        raise SurfaceSyntaxError("PV-1 invalid package declaration")
    return PackageDeclarationNode(match.group(1))


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
        if line.startswith("export import "):
            raise SurfaceSyntaxError("UnsupportedFeature")
        if line.startswith("export ") and context != "module":
            raise SurfaceSyntaxError("ExportMustBeTopLevel")
        if line.startswith("struct ") or line.startswith("export struct "):
            nodes.append(_parse_struct(cursor))
        elif line.startswith("enum ") or line.startswith("export enum "):
            nodes.append(_parse_enum(cursor))
        elif _is_collection_literal_statement(line):
            nodes.append(_parse_collection_literal_statement(cursor))
        elif _is_struct_literal_statement(line):
            nodes.append(_parse_struct_literal_statement(cursor))
        elif line.startswith("goal ") and line.endswith("{"):
            nodes.append(_parse_goal_declaration(cursor, context=context))
        elif line.startswith("state ") and line.endswith("{"):
            nodes.append(_parse_state_declaration(cursor))
        elif line.startswith("constraint ") and line.endswith("{"):
            nodes.append(_parse_constraint_declaration(cursor))
        elif line.startswith("transition "):
            nodes.append(_parse_transition(cursor))
        elif line.startswith("reason_graph "):
            nodes.append(_parse_reason_graph(cursor))
        elif line.startswith("execution_plan "):
            nodes.append(_parse_execution_plan(cursor))
        elif (
            line.startswith("calculation ")
            or line.startswith("pub calculation ")
            or line.startswith("export calculation ")
        ):
            nodes.append(_parse_calculation(cursor))
        elif (
            line.startswith("fn ")
            or line.startswith("pub fn ")
            or line.startswith("export fn ")
        ):
            nodes.append(_parse_function(cursor))
        elif line.startswith("for "):
            nodes.append(_parse_for(cursor, context=context))
        elif line.startswith("while "):
            nodes.append(_parse_while(cursor, context=context))
        elif line == "loop {":
            nodes.append(_parse_loop(cursor, context=context))
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
    match = re.fullmatch(r"state\s+([A-Za-z_]\w*)", line)
    if match:
        return StateDeclarationNode(match.group(1))
    match = re.fullmatch(r"constraint\s+([A-Za-z_]\w*)\s*\{\s*(.+)\s*\}", line)
    if match:
        return ConstraintNode(match.group(1), match.group(2).strip())
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
    match = re.fullmatch(r"let\s+([A-Za-z_]\w*)(?:\s*:\s*(.+?))?\s*=\s*(.+)", line)
    if match:
        return LetStatementNode(
            match.group(1),
            _expression(match.group(3)),
            _type_annotation(match.group(2)) if match.group(2) else None,
        )
    match = re.fullmatch(r"const\s+([A-Za-z_]\w*)(?:\s*:\s*(.+?))?\s*=\s*(.+)", line)
    if match:
        if context == "module":
            return ConstDeclarationNode(
                match.group(1),
                _expression(match.group(3)),
                _type_annotation(match.group(2)) if match.group(2) else None,
            )
        return ConstStatementNode(
            match.group(1),
            _expression(match.group(3)),
            _type_annotation(match.group(2)) if match.group(2) else None,
        )
    match = re.fullmatch(
        r"export\s+const\s+([A-Za-z_]\w*)(?:\s*:\s*(.+?))?\s*=\s*(.+)",
        line,
    )
    if match:
        if context != "module":
            raise SurfaceSyntaxError("ExportMustBeTopLevel")
        return ConstDeclarationNode(
            match.group(1),
            _expression(match.group(3)),
            _type_annotation(match.group(2)) if match.group(2) else None,
            Visibility.PUBLIC,
        )
    match = re.fullmatch(r"result\s*=\s*(.+)", line)
    if match:
        return ResultStatementNode(_expression(match.group(1)))
    match = re.fullmatch(r"return\s+(.+)", line)
    if match:
        return ReturnStatementNode(_expression(match.group(1)))
    match = re.fullmatch(r"(.+\.[A-Za-z_]\w*)\s*=\s*(.+)", line)
    if match:
        return FieldAssignmentStatementNode(
            _expression(match.group(1)),
            _expression(match.group(2)),
        )
    match = re.fullmatch(r"(.+\[.+\])\s*=\s*(.+)", line)
    if match:
        return IndexAssignmentStatementNode(
            _expression(match.group(1)),
            _expression(match.group(2)),
        )
    if line == "break":
        return BreakStatementNode()
    if line == "continue":
        return ContinueStatementNode()
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


def _parse_goal_declaration(cursor: _Cursor, *, context: str) -> GoalNode | GoalStatementNode:
    match = re.fullmatch(r"goal\s+([A-Za-z_]\w*)\s*\{", cursor.take())
    if not match:
        raise SurfaceSyntaxError("invalid goal declaration")
    metadata = _parse_metadata_block(cursor, owner="goal")
    if context != "module":
        return GoalStatementNode(match.group(1))
    return GoalNode(match.group(1), metadata)


def _parse_state_declaration(cursor: _Cursor) -> StateDeclarationNode:
    match = re.fullmatch(r"state\s+([A-Za-z_]\w*)\s*\{", cursor.take())
    if not match:
        raise SurfaceSyntaxError("invalid state declaration")
    return StateDeclarationNode(match.group(1), _parse_metadata_block(cursor, owner="state"))


def _parse_constraint_declaration(cursor: _Cursor) -> ConstraintNode:
    match = re.fullmatch(r"constraint\s+([A-Za-z_]\w*)\s*\{", cursor.take())
    if not match:
        raise SurfaceSyntaxError("invalid constraint declaration")
    expressions: list[str] = []
    while cursor.index < len(cursor.lines):
        line = cursor.take()
        if line == "}":
            return ConstraintNode(match.group(1), " ".join(expressions).strip() or None)
        expressions.append(line)
    raise SurfaceSyntaxError("unterminated constraint declaration")


def _parse_metadata_block(cursor: _Cursor, *, owner: str) -> tuple[tuple[str, str], ...]:
    metadata: list[tuple[str, str]] = []
    while cursor.index < len(cursor.lines):
        line = cursor.take()
        if line == "}":
            return tuple(metadata)
        match = re.fullmatch(r"([A-Za-z_]\w*)\s*:\s*(.+)", line)
        if not match:
            raise SurfaceSyntaxError(f"invalid {owner} metadata entry: {line}")
        metadata.append((match.group(1), match.group(2).strip()))
    raise SurfaceSyntaxError(f"unterminated {owner} declaration")


def _parse_reason_graph(cursor: _Cursor) -> ReasonGraphDeclarationNode:
    match = re.fullmatch(r"reason_graph\s+([A-Za-z_]\w*)\s*\{", cursor.take())
    if not match:
        raise SurfaceSyntaxError("invalid reason_graph declaration")
    states: list[StateDeclarationNode] = []
    transitions: list[ReasonGraphTransitionNode] = []
    while cursor.index < len(cursor.lines):
        line = cursor.take()
        if line == "}":
            return ReasonGraphDeclarationNode(
                match.group(1), tuple(states), tuple(transitions)
            )
        state = re.fullmatch(r"state\s+([A-Za-z_]\w*)", line)
        if state:
            states.append(StateDeclarationNode(state.group(1)))
            continue
        transition = re.fullmatch(
            r"transition\s+([A-Za-z_]\w*)\s*->\s*([A-Za-z_]\w*)",
            line,
        )
        if transition:
            transitions.append(
                ReasonGraphTransitionNode(transition.group(1), transition.group(2))
            )
            continue
        raise SurfaceSyntaxError(f"invalid reason_graph member: {line}")
    raise SurfaceSyntaxError("unterminated reason_graph declaration")


def _parse_execution_plan(cursor: _Cursor) -> ExecutionPlanDeclarationNode:
    match = re.fullmatch(r"execution_plan\s+([A-Za-z_]\w*)\s*\{", cursor.take())
    if not match:
        raise SurfaceSyntaxError("invalid execution_plan declaration")
    steps: list[PlanStepNode] = []
    while cursor.index < len(cursor.lines):
        line = cursor.take()
        if line == "}":
            return ExecutionPlanDeclarationNode(match.group(1), tuple(steps))
        step = re.fullmatch(r"step\s+([A-Za-z_]\w*)\s*->\s*([A-Za-z_]\w*)", line)
        if not step:
            raise SurfaceSyntaxError(f"invalid execution_plan step: {line}")
        steps.append(PlanStepNode(step.group(1), step.group(2)))
    raise SurfaceSyntaxError("unterminated execution_plan declaration")


def _parse_calculation(cursor: _Cursor) -> CalculationNode:
    match = re.fullmatch(
        r"(?:(pub|export)\s+)?calculation\s+([A-Za-z_]\w*)"
        r"(?:\s+goal:([A-Za-z_]\w*))?"
        r"(?:\s*->\s*(.+?))?\s*\{",
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


def _parse_struct(cursor: _Cursor) -> StructDeclarationNode:
    match = re.fullmatch(
        r"(?:(export)\s+)?struct\s+([A-Za-z_]\w*)\s*\{",
        cursor.take(),
    )
    if not match:
        raise SurfaceSyntaxError("invalid struct declaration")
    fields: list[StructFieldNode] = []
    while cursor.index < len(cursor.lines):
        line = cursor.take()
        if line == "}":
            return StructDeclarationNode(
                match.group(2),
                tuple(fields),
                Visibility.PUBLIC if match.group(1) else Visibility.PRIVATE,
            )
        field = re.fullmatch(r"([A-Za-z_]\w*)\s*:\s*(.+)", line)
        if not field:
            raise SurfaceSyntaxError("TV-4 FieldTypeRequired")
        fields.append(StructFieldNode(field.group(1), _type_annotation(field.group(2))))
    raise SurfaceSyntaxError("unterminated struct declaration")


def _parse_enum(cursor: _Cursor) -> EnumDeclarationNode:
    match = re.fullmatch(
        r"(?:(export)\s+)?enum\s+([A-Za-z_]\w*)\s*\{",
        cursor.take(),
    )
    if not match:
        raise SurfaceSyntaxError("invalid enum declaration")
    values: list[EnumValueNode] = []
    while cursor.index < len(cursor.lines):
        line = cursor.take()
        if line == "}":
            return EnumDeclarationNode(
                match.group(2),
                tuple(values),
                Visibility.PUBLIC if match.group(1) else Visibility.PRIVATE,
            )
        value = re.fullmatch(r"([A-Za-z_]\w*)", line)
        if not value:
            raise SurfaceSyntaxError("invalid enum value")
        values.append(EnumValueNode(value.group(1)))
    raise SurfaceSyntaxError("unterminated enum declaration")


def _parse_function(cursor: _Cursor) -> FunctionDeclarationNode:
    match = re.fullmatch(
        r"(?:(pub|export)\s+)?fn\s+([A-Za-z_]\w*)\s*\(([^)]*)\)"
        r"(?:\s*(?:->|:)\s*(.+?))?\s*\{",
        cursor.take(),
    )
    if not match:
        raise SurfaceSyntaxError("invalid function declaration")
    parameters = _parameters(match.group(3))
    body = _parse_body(cursor, context="function")
    visibility = Visibility.PUBLIC if match.group(1) else Visibility.PRIVATE
    return FunctionDeclarationNode(
        match.group(2),
        parameters,
        tuple(body),
        visibility,
        _type_annotation(match.group(4)) if match.group(4) else None,
    )


def _parse_for(cursor: _Cursor, *, context: str) -> ForStatementNode:
    match = re.fullmatch(
        r"for\s+([A-Za-z_]\w*)\s+in\s+(.+)\s*\{",
        cursor.take(),
    )
    if not match:
        raise SurfaceSyntaxError("invalid for statement")
    return ForStatementNode(
        match.group(1),
        _expression(match.group(2)),
        tuple(_parse_body(cursor, context=context)),
    )


def _parse_while(cursor: _Cursor, *, context: str) -> WhileStatementNode:
    match = re.fullmatch(r"while\s+(.+)\s*\{", cursor.take())
    if not match:
        raise SurfaceSyntaxError("invalid while statement")
    return WhileStatementNode(
        _expression(match.group(1)),
        tuple(_parse_body(cursor, context=context)),
    )


def _parse_loop(cursor: _Cursor, *, context: str) -> LoopStatementNode:
    cursor.take()
    return LoopStatementNode(tuple(_parse_body(cursor, context=context)))


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
        line = _collect_struct_pattern_arm(cursor, line)
        arm = re.fullmatch(r"(.+?)\s*=>\s*(.+)", line)
        if not arm:
            raise SurfaceSyntaxError(f"invalid match arm: {line}")
        arm_body = (
            tuple(_parse_body(cursor, context=context))
            if arm.group(2).strip() == "{"
            else (_parse_simple(arm.group(2).strip(), context=context),)
        )
        arms.append(
            MatchArmNode(
                _pattern(arm.group(1)),
                arm_body,
            )
        )
    raise SurfaceSyntaxError("unterminated match block")


def _collect_struct_pattern_arm(cursor: _Cursor, line: str) -> str:
    if "=>" in line or not re.fullmatch(
        r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*\{", line
    ):
        return line
    parts = [line]
    while cursor.index < len(cursor.lines):
        next_line = cursor.take()
        parts.append(next_line)
        if next_line.startswith("}"):
            return " ".join(parts)
    raise SurfaceSyntaxError("SP-002 invalid struct pattern syntax")


def _expression(source: str):
    try:
        expression = parse_expression(source.strip(), allow_tuple_access=True)
        return ExpressionNode(_normalize_runtime_expression(expression.expression))
    except ExpressionSyntaxError as error:
        raise SurfaceSyntaxError(str(error)) from error


def _normalize_runtime_expression(value):
    if isinstance(value, CallExpressionNode):
        callee = _normalize_runtime_expression(value.callee)
        arguments = tuple(
            _normalize_runtime_expression(item) for item in value.arguments
        )
        if isinstance(callee, IdentifierNode):
            kind = {
                "input": RuntimeCallKind.INPUT,
                "print": RuntimeCallKind.PRINT,
            }.get(callee.name)
            if kind is not None:
                return RuntimeCallExpressionNode(
                    RuntimeNamespaceNode(), callee.name, kind, arguments
                )
        if (
            isinstance(callee, MemberAccessNode)
            and isinstance(callee.object, RuntimeNamespaceNode)
        ):
            kind = {
                "input": RuntimeCallKind.INPUT,
                "print": RuntimeCallKind.PRINT,
                "search": RuntimeCallKind.SEARCH,
                "simulate": RuntimeCallKind.SIMULATION,
                "predict": RuntimeCallKind.PREDICTION,
                "plan": RuntimeCallKind.PLANNING,
            }.get(callee.member)
            if kind is None:
                raise SurfaceSyntaxError("UnknownRuntimeMethod")
            return RuntimeCallExpressionNode(
                callee.object, callee.member, kind, arguments
            )
        return CallExpressionNode(callee, arguments)
    if isinstance(value, MemberAccessNode):
        normalized_object = _normalize_runtime_expression(value.object)
        if (
            isinstance(normalized_object, IdentifierNode)
            and normalized_object.name == "runtime"
        ):
            normalized_object = RuntimeNamespaceNode()
        return MemberAccessNode(normalized_object, value.member)
    if isinstance(value, ParenthesizedExpressionNode):
        return ParenthesizedExpressionNode(
            _normalize_runtime_expression(value.expression)
        )
    if isinstance(value, UnaryExpressionNode):
        return UnaryExpressionNode(
            value.operator, _normalize_runtime_expression(value.operand)
        )
    if isinstance(value, BinaryExpressionNode):
        return BinaryExpressionNode(
            _normalize_runtime_expression(value.left),
            value.operator,
            _normalize_runtime_expression(value.right),
        )
    if isinstance(value, ComparisonExpressionNode):
        return ComparisonExpressionNode(
            _normalize_runtime_expression(value.left),
            value.operator,
            _normalize_runtime_expression(value.right),
        )
    if isinstance(value, LogicalExpressionNode):
        return LogicalExpressionNode(
            _normalize_runtime_expression(value.left),
            value.operator,
            _normalize_runtime_expression(value.right),
        )
    if isinstance(value, SomeExpressionNode):
        return SomeExpressionNode(_normalize_runtime_expression(value.value))
    if isinstance(value, IndexAccessNode):
        return IndexAccessNode(
            _normalize_runtime_expression(value.collection),
            _normalize_runtime_expression(value.index),
        )
    if isinstance(value, StructLiteralNode):
        return StructLiteralNode(
            value.type_name,
            tuple(
                StructLiteralFieldNode(
                    field.name,
                    ExpressionNode(
                        _normalize_runtime_expression(field.expression.expression)
                    ),
                )
                for field in value.fields
            ),
        )
    if isinstance(value, (ArrayLiteralNode, TupleLiteralNode, SetLiteralNode)):
        return type(value)(
            tuple(
                ExpressionNode(_normalize_runtime_expression(item.expression))
                for item in value.elements
            )
        )
    if isinstance(value, MapLiteralNode):
        return MapLiteralNode(
            tuple(
                MapEntryNode(
                    ExpressionNode(_normalize_runtime_expression(entry.key.expression)),
                    ExpressionNode(
                        _normalize_runtime_expression(entry.value.expression)
                    ),
                )
                for entry in value.entries
            )
        )
    return value


def _is_struct_literal_statement(line: str) -> bool:
    return bool(
        re.fullmatch(
            r"(?:let|const)\s+[A-Za-z_]\w*(?:\s*:\s*[A-Za-z_]\w*)?\s*=\s*[A-Za-z_]\w*\s*\{",
            line,
        )
        or re.fullmatch(r"(?:return|result\s*=)\s*[A-Za-z_]\w*\s*\{", line)
    )


def _is_collection_literal_statement(line: str) -> bool:
    return bool(
        re.fullmatch(r"(?:let|const)\s+[A-Za-z_]\w*(?:\s*:\s*.+?)?\s*=\s*(?:set|map)\s*\{", line)
        or re.fullmatch(r"(?:return|result\s*=)\s*(?:set|map)\s*\{", line)
    )


def _parse_collection_literal_statement(cursor: _Cursor):
    line = cursor.take()
    binding = re.fullmatch(
        r"(let|const)\s+([A-Za-z_]\w*)(?:\s*:\s*(.+?))?\s*=\s*(set|map)\s*\{",
        line,
    )
    if binding:
        literal = _parse_collection_literal_body(cursor, binding.group(4))
        type_annotation = (
            _type_annotation(binding.group(3)) if binding.group(3) else None
        )
        if binding.group(1) == "let":
            return LetStatementNode(binding.group(2), literal, type_annotation)
        return ConstStatementNode(binding.group(2), literal, type_annotation)
    terminal = re.fullmatch(r"(return|result\s*=)\s*(set|map)\s*\{", line)
    if terminal:
        literal = _parse_collection_literal_body(cursor, terminal.group(2))
        return (
            ReturnStatementNode(literal)
            if terminal.group(1) == "return"
            else ResultStatementNode(literal)
        )
    raise SurfaceSyntaxError(f"invalid collection literal statement: {line}")


def _parse_collection_literal_body(cursor: _Cursor, kind: str) -> ExpressionNode:
    if kind == "set":
        elements = []
        while cursor.index < len(cursor.lines):
            line = cursor.take()
            if line == "}":
                return ExpressionNode(SetLiteralNode(tuple(elements)))
            elements.append(_expression(line.rstrip(",")))
        raise SurfaceSyntaxError("unterminated set literal")
    entries = []
    while cursor.index < len(cursor.lines):
        line = cursor.take()
        if line == "}":
            return ExpressionNode(MapLiteralNode(tuple(entries)))
        entry = re.fullmatch(r"(.+?)\s*:\s*(.+?),?", line)
        if not entry:
            raise SurfaceSyntaxError(f"invalid map entry: {line}")
        nested = re.fullmatch(r"([A-Za-z_]\w*)\s*\{", entry.group(2).strip())
        value = (
            _parse_struct_literal_body(cursor, nested.group(1))
            if nested
            else _expression(entry.group(2))
        )
        entries.append(MapEntryNode(_expression(entry.group(1)), value))
    raise SurfaceSyntaxError("unterminated map literal")


def _parse_struct_literal_statement(cursor: _Cursor):
    line = cursor.take()
    binding = re.fullmatch(
        r"(let|const)\s+([A-Za-z_]\w*)(?:\s*:\s*([A-Za-z_]\w*))?\s*=\s*([A-Za-z_]\w*)\s*\{",
        line,
    )
    if binding:
        literal = _parse_struct_literal_body(cursor, binding.group(4))
        type_annotation = (
            _type_annotation(binding.group(3)) if binding.group(3) else None
        )
        if binding.group(1) == "let":
            return LetStatementNode(binding.group(2), literal, type_annotation)
        return ConstStatementNode(binding.group(2), literal, type_annotation)
    terminal = re.fullmatch(r"(return|result\s*=)\s*([A-Za-z_]\w*)\s*\{", line)
    if terminal:
        literal = _parse_struct_literal_body(cursor, terminal.group(2))
        return (
            ReturnStatementNode(literal)
            if terminal.group(1) == "return"
            else ResultStatementNode(literal)
        )
    raise SurfaceSyntaxError(f"invalid struct literal statement: {line}")


def _parse_struct_literal_body(cursor: _Cursor, type_name: str) -> ExpressionNode:
    fields: list[StructLiteralFieldNode] = []
    while cursor.index < len(cursor.lines):
        line = cursor.take()
        if line == "}":
            return ExpressionNode(StructLiteralNode(type_name, tuple(fields)))
        field = re.fullmatch(r"([A-Za-z_]\w*)\s*:\s*(.+)", line)
        if not field:
            raise SurfaceSyntaxError(f"invalid struct literal field: {line}")
        nested = re.fullmatch(r"([A-Za-z_]\w*)\s*\{", field.group(2).strip())
        expression = (
            _parse_struct_literal_body(cursor, nested.group(1))
            if nested
            else _expression(field.group(2))
        )
        fields.append(StructLiteralFieldNode(field.group(1), expression))
    raise SurfaceSyntaxError("unterminated struct literal")


def _pattern(source: str):
    try:
        return parse_pattern(source.strip())
    except ExpressionSyntaxError as error:
        raise SurfaceSyntaxError(str(error)) from error


def _type_annotation(source: str):
    source = source.strip()
    if source.startswith("[") and source.endswith("]"):
        return ArrayTypeNode(_type_annotation(source[1:-1]))
    optional_match = re.fullmatch(r"optional\s*<\s*(.+)\s*>", source)
    if optional_match:
        return OptionalTypeNode(_type_annotation(optional_match.group(1)))
    if source.startswith("(") and source.endswith(")"):
        inner = source[1:-1].strip()
        if not inner:
            raise SurfaceSyntaxError("TYPE-V001 tuple type requires elements")
        return TupleTypeNode(tuple(_type_annotation(item.strip()) for item in inner.split(",")))
    set_match = re.fullmatch(r"set\s*<\s*(.+)\s*>", source)
    if set_match:
        return SetTypeNode(_type_annotation(set_match.group(1)))
    map_match = re.fullmatch(r"map\s*<\s*(.+)\s*,\s*(.+)\s*>", source)
    if map_match:
        return MapTypeNode(
            _type_annotation(map_match.group(1)),
            _type_annotation(map_match.group(2)),
        )
    primitive_aliases = {
        "int": PrimitiveKind.INT,
        "float": PrimitiveKind.FLOAT,
        "bool": PrimitiveKind.BOOL,
        "string": PrimitiveKind.STRING,
        "null": PrimitiveKind.NULL,
    }
    if source in primitive_aliases:
        return PrimitiveTypeNode(primitive_aliases[source])
    try:
        return PrimitiveTypeNode(PrimitiveKind(source))
    except ValueError:
        pass
    try:
        return StateTypeNode(StateKind(source))
    except ValueError:
        return NamedTypeNode(source)


def _parameters(source: str) -> tuple[dict[str, object], ...]:
    text = source.strip()
    if not text:
        return ()
    parameters: list[dict[str, object]] = []
    seen: set[str] = set()
    for part in text.split(","):
        parameter = part.strip()
        match = re.fullmatch(r"([A-Za-z_]\w*)\s*:\s*(.+)", parameter)
        if not match:
            raise SurfaceSyntaxError(f"FN-002 parameter type required: {parameter}")
        name = match.group(1)
        if name in seen:
            raise SurfaceSyntaxError(f"FN-006 duplicate parameter: {name}")
        seen.add(name)
        parameters.append({"name": name, "type": _type_annotation(match.group(2))})
    return tuple(parameters)
