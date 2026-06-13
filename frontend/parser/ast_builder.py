from __future__ import annotations

import re
from urllib.parse import urlparse

from frontend.ast import (
    ConstraintNode,
    ContextNode,
    GoalNode,
    ModuleNode,
    StateNode,
    TransitionNode,
)

from .errors import ParserError, ParserErrorCode


class AstBuilder:
    def __init__(self) -> None:
        self.imports: list[str] = []
        self.declarations = []
        self.counts: dict[str, int] = {}
        self.goal_line: int | None = None
        self.state_line: int | None = None

    def add_goal(self, target: str, line: int, column: int) -> None:
        if self.goal_line is not None:
            raise ParserError(
                ParserErrorCode.DUPLICATE_GOAL,
                line,
                column,
                f"goal already declared on line {self.goal_line}",
            )
        self.goal_line = line
        self.declarations.append(
            GoalNode(self._node_id("goal"), "reach_state", target)
        )

    def add_state(self, state_id: str, line: int, column: int) -> None:
        if self.state_line is not None:
            raise ParserError(
                ParserErrorCode.DUPLICATE_INITIAL_STATE,
                line,
                column,
                f"initial state already declared on line {self.state_line}",
            )
        self.state_line = line
        self.declarations.append(
            StateNode(self._node_id("state"), state_id, "symbolic", {})
        )

    def add_transition(
        self, source: str, relation: str, target: str, line: int
    ) -> None:
        identifier = "-".join(_identifier(item) for item in (source, relation, target))
        occurrence = self.counts.get(f"transition-id:{identifier}", 0) + 1
        self.counts[f"transition-id:{identifier}"] = occurrence
        if occurrence > 1:
            identifier = f"{identifier}-{occurrence}"
        self.declarations.append(
            TransitionNode(
                self._node_id("transition"),
                identifier,
                source,
                relation,
                target,
            )
        )

    def add_constraint(self, name: str, line: int) -> None:
        self.declarations.append(
            ConstraintNode(
                self._node_id("constraint"),
                _identifier(name),
                "predicate",
                name,
            )
        )

    def add_context(self, uri: str, line: int, column: int) -> None:
        parsed = urlparse(uri)
        if not parsed.scheme or "://" not in uri:
            raise ParserError(
                ParserErrorCode.INVALID_URI,
                line,
                column,
                "context requires an absolute URI",
            )
        label = parsed.netloc or parsed.path.strip("/") or parsed.scheme
        self.declarations.append(
            ContextNode(
                self._node_id("context"),
                _identifier(f"{parsed.scheme}-{label}"),
                parsed.scheme,
                uri,
            )
        )

    def add_import(self, reference: str) -> None:
        self.imports.append(reference)

    def build(self, eof_line: int, eof_column: int) -> ModuleNode:
        if self.goal_line is None:
            raise ParserError(
                ParserErrorCode.MISSING_GOAL,
                eof_line,
                eof_column,
                "module requires exactly one goal statement",
            )
        if self.state_line is None:
            raise ParserError(
                ParserErrorCode.MISSING_INITIAL_STATE,
                eof_line,
                eof_column,
                "module requires exactly one state statement",
            )
        return ModuleNode(
            node_id="module",
            imports=tuple(self.imports),
            declarations=tuple(self.declarations),
        )

    def _node_id(self, kind: str) -> str:
        count = self.counts.get(kind, 0) + 1
        self.counts[kind] = count
        return f"{kind}-{count}"


def _identifier(value: str) -> str:
    normalized = re.sub(r"[^\w.-]+", "-", value, flags=re.UNICODE).strip("-")
    return normalized or "unnamed"
