"""reason_graph.query — inspect ReasonGraph without mutation."""

from __future__ import annotations

from .builder import ReasonGraph


def states(graph: ReasonGraph) -> list[str]:
    """Return the list of state IDs in the graph (does not mutate)."""
    return [n.get("id", "") for n in graph.nodes]


def transitions(graph: ReasonGraph) -> list[str]:
    """Return human-readable transition strings (does not mutate)."""
    return [f"{e.get('from')} -> {e.get('to')}" for e in graph.edges]
