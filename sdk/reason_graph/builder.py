"""reason_graph.builder — construct ReasonGraph instances programmatically."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReasonGraph:
    name: str
    nodes: tuple[dict, ...] = field(default_factory=tuple)
    edges: tuple[dict, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "nodes": list(self.nodes),
            "edges": list(self.edges),
        }


def create_graph(name: str) -> ReasonGraph:
    """Create an empty ReasonGraph with the given name."""
    return ReasonGraph(name=name, nodes=(), edges=())


def add_state(graph: ReasonGraph, state: str | dict) -> ReasonGraph:
    """Return a new ReasonGraph with the given state added."""
    node = {"id": state} if isinstance(state, str) else dict(state)
    if any(n.get("id") == node.get("id") for n in graph.nodes):
        return graph
    return ReasonGraph(
        name=graph.name,
        nodes=graph.nodes + (node,),
        edges=graph.edges,
    )


def add_transition(
    graph: ReasonGraph, from_state: str | dict, to_state: str | dict
) -> ReasonGraph:
    """Return a new ReasonGraph with a transition edge added."""
    src = from_state if isinstance(from_state, str) else from_state.get("id", str(from_state))
    dst = to_state if isinstance(to_state, str) else to_state.get("id", str(to_state))
    edge = {"from": src, "to": dst}
    if any(e.get("from") == src and e.get("to") == dst for e in graph.edges):
        return graph
    return ReasonGraph(
        name=graph.name,
        nodes=graph.nodes,
        edges=graph.edges + (edge,),
    )
