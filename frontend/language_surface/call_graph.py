"""Call Graph Analysis for ReasonScript language surface.

Provides static call graph extraction, caller/callee mapping, direct recursion
detection, mutual recursion cycle detection, and recursion classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .nodes import (
    ArrayLiteralNode,
    AssignmentStatementNode,
    BinaryExpressionNode,
    CalculationNode,
    CallExpressionNode,
    ComparisonExpressionNode,
    ConstStatementNode,
    ExpressionNode,
    ExpressionStatementNode,
    FieldAssignmentStatementNode,
    ForStatementNode,
    FunctionDeclarationNode,
    IdentifierNode,
    IfStatementNode,
    IndexAccessNode,
    IndexAssignmentStatementNode,
    LetStatementNode,
    LogicalExpressionNode,
    LoopStatementNode,
    MapLiteralNode,
    MatchStatementNode,
    MemberAccessNode,
    ParenthesizedExpressionNode,
    ProgramNode,
    QualifiedIdentifierNode,
    ResultStatementNode,
    ReturnStatementNode,
    RuntimeCallExpressionNode,
    SomeExpressionNode,
    StructLiteralNode,
    TupleLiteralNode,
    UnaryExpressionNode,
    WhileStatementNode,
)


@dataclass(frozen=True)
class CallGraphAnalysisResult:
    """Represents the static call graph and recursion analysis results."""

    functions: list[str]
    calculations: list[str]
    callees: dict[str, set[str]] = field(default_factory=dict)
    callers: dict[str, set[str]] = field(default_factory=dict)
    direct_recursive: set[str] = field(default_factory=set)
    mutual_recursive: set[str] = field(default_factory=set)
    cycles: list[list[str]] = field(default_factory=list)

    def is_recursive(self, name: str) -> bool:
        """Returns True if the function is either directly or mutually recursive."""
        return name in self.direct_recursive or name in self.mutual_recursive

    def recursion_kind(self, name: str) -> str | None:
        """Returns 'direct', 'mutual', or None."""
        if name in self.direct_recursive:
            return "direct"
        if name in self.mutual_recursive:
            return "mutual"
        return None

    def to_dict(self) -> dict[str, Any]:
        """Converts analysis result to a JSON-serializable dictionary."""
        return {
            "functions": sorted(self.functions),
            "calculations": sorted(self.calculations),
            "callees": {k: sorted(v) for k, v in sorted(self.callees.items())},
            "callers": {k: sorted(v) for k, v in sorted(self.callers.items())},
            "direct_recursive": sorted(self.direct_recursive),
            "mutual_recursive": sorted(self.mutual_recursive),
            "cycles": self.cycles,
        }


def analyze_call_graph(program: ProgramNode) -> CallGraphAnalysisResult:
    """Analyzes all modules, functions, and calculations in a ProgramNode to build the Call Graph."""
    functions: list[str] = []
    calculations: list[str] = []
    callees: dict[str, set[str]] = {}
    callers: dict[str, set[str]] = {}

    function_nodes: dict[str, FunctionDeclarationNode] = {}
    calc_nodes: dict[str, CalculationNode] = {}

    for module in program.modules:
        for item in module.body:
            if isinstance(item, FunctionDeclarationNode):
                functions.append(item.name)
                function_nodes[item.name] = item
                callees[item.name] = set()
                if item.name not in callers:
                    callers[item.name] = set()
            elif isinstance(item, CalculationNode):
                calculations.append(item.name)
                calc_nodes[item.name] = item
                callees[item.name] = set()
                if item.name not in callers:
                    callers[item.name] = set()

    known_functions = set(functions)

    # Extract function calls from function bodies
    for func_name, func_node in function_nodes.items():
        called = _extract_function_calls(func_node.body, known_functions)
        callees[func_name] = called
        for callee in called:
            callers.setdefault(callee, set()).add(func_name)

    # Extract function calls from calculation bodies
    for calc_name, calc_node in calc_nodes.items():
        called = _extract_function_calls(calc_node.body, known_functions)
        callees[calc_name] = called
        for callee in called:
            callers.setdefault(callee, set()).add(calc_name)

    # Detect direct recursion (f -> f)
    direct_recursive: set[str] = {
        func for func in functions if func in callees.get(func, set())
    }

    # Detect cycles among functions using DFS
    cycles: list[list[str]] = []
    visited_cycles: set[tuple[str, ...]] = set()

    def find_cycles(start: str, current: str, path: list[str], visited_in_path: set[str]) -> None:
        for neighbor in sorted(callees.get(current, set())):
            if neighbor not in known_functions:
                continue
            if neighbor == start and len(path) > 0:
                cycle_tuple = _canonical_cycle(path + [start])
                if cycle_tuple not in visited_cycles:
                    visited_cycles.add(cycle_tuple)
                    cycles.append(list(cycle_tuple) + [cycle_tuple[0]])
            elif neighbor not in visited_in_path:
                find_cycles(start, neighbor, path + [neighbor], visited_in_path | {neighbor})

    for func in sorted(functions):
        find_cycles(func, func, [func], {func})

    # Mutual recursion is any function in a cycle of length > 1
    mutual_recursive: set[str] = set()
    for cycle in cycles:
        cycle_nodes = cycle[:-1]
        if len(cycle_nodes) > 1:
            for node in cycle_nodes:
                if node not in direct_recursive:
                    mutual_recursive.add(node)

    return CallGraphAnalysisResult(
        functions=functions,
        calculations=calculations,
        callees=callees,
        callers=callers,
        direct_recursive=direct_recursive,
        mutual_recursive=mutual_recursive,
        cycles=cycles,
    )


def _canonical_cycle(path: list[str]) -> tuple[str, ...]:
    """Returns a canonical rotational representation of a simple cycle."""
    nodes = path[:-1]
    min_idx = nodes.index(min(nodes))
    rotated = nodes[min_idx:] + nodes[:min_idx]
    return tuple(rotated)


def _extract_function_calls(statements: Any, known_functions: set[str]) -> set[str]:
    """Recursively walks statements and expressions to extract all called function identifiers."""
    called: set[str] = set()
    seen_ids: set[int] = set()

    def visit(item: Any) -> None:
        if item is None:
            return
        item_id = id(item)
        if item_id in seen_ids:
            return
        seen_ids.add(item_id)

        if isinstance(item, ExpressionNode):
            visit(item.expression)
            return

        if isinstance(item, CallExpressionNode):
            if isinstance(item.callee, IdentifierNode) and item.callee.name in known_functions:
                called.add(item.callee.name)
            elif isinstance(item.callee, QualifiedIdentifierNode) and item.callee.symbol in known_functions:
                called.add(item.callee.symbol)
            else:
                visit(item.callee)
            for argument in item.arguments:
                visit(argument)
            return

        if isinstance(item, RuntimeCallExpressionNode):
            for argument in item.arguments:
                visit(argument)
            return

        if isinstance(item, UnaryExpressionNode):
            visit(item.operand)
            return

        if isinstance(item, (BinaryExpressionNode, ComparisonExpressionNode, LogicalExpressionNode)):
            visit(item.left)
            visit(item.right)
            return

        if isinstance(item, ParenthesizedExpressionNode):
            visit(item.expression)
            return

        if isinstance(item, MemberAccessNode):
            visit(item.object)
            return

        if isinstance(item, StructLiteralNode):
            for field in item.fields:
                visit(getattr(field, "expression", None))
            return

        if isinstance(item, (ArrayLiteralNode, TupleLiteralNode)):
            for element in item.elements:
                visit(element)
            return

        if isinstance(item, MapLiteralNode):
            for entry in item.entries:
                visit(entry.key)
                visit(entry.value)
            return

        if isinstance(item, IndexAccessNode):
            visit(item.collection)
            visit(item.index)
            return

        if isinstance(item, SomeExpressionNode):
            visit(item.value)
            return

        if isinstance(item, (LetStatementNode, ConstStatementNode)):
            visit(getattr(item, "expression", getattr(item, "initializer", None)))
            return

        if isinstance(item, AssignmentStatementNode):
            visit(item.value)
            return

        if isinstance(item, FieldAssignmentStatementNode):
            visit(item.target)
            visit(item.value)
            return

        if isinstance(item, IndexAssignmentStatementNode):
            visit(item.target)
            visit(item.index)
            visit(item.value)
            return

        if isinstance(item, (ResultStatementNode, ReturnStatementNode, ExpressionStatementNode)):
            visit(item.expression)
            return

        if isinstance(item, IfStatementNode):
            visit(item.condition)
            for stmt in item.body:
                visit(stmt)
            for elif_branch in getattr(item, "elif_branches", ()):
                visit(getattr(elif_branch, "condition", None))
                for stmt in getattr(elif_branch, "body", ()):
                    visit(stmt)
            if getattr(item, "else_branch", None):
                for stmt in getattr(item.else_branch, "body", ()):
                    visit(stmt)
            return

        if isinstance(item, (WhileStatementNode, LoopStatementNode, ForStatementNode)):
            if hasattr(item, "condition"):
                visit(item.condition)
            if hasattr(item, "iterable"):
                visit(item.iterable)
            for stmt in item.body:
                visit(stmt)
            return

        if isinstance(item, MatchStatementNode):
            visit(item.subject)
            for arm in getattr(item, "arms", ()):
                if hasattr(arm, "guard") and arm.guard:
                    visit(arm.guard)
                if hasattr(arm, "body"):
                    for stmt in arm.body:
                        visit(stmt)
            return

    if isinstance(statements, (list, tuple)):
        for stmt in statements:
            visit(stmt)
    else:
        visit(statements)

    return called
