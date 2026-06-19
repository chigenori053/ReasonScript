"""reason_graph.validation — validate ReasonGraph consistency."""

from __future__ import annotations

from .builder import ReasonGraph


def validate(graph: ReasonGraph) -> bool:
    """Validate a ReasonGraph. Returns True if valid, False otherwise.

    Checks:
    - State existence (all transition endpoints exist as nodes)
    - Transition validity (from/to must be non-empty)
    - Duplicate states
    - Duplicate transitions
    """
    node_ids = [n.get("id") for n in graph.nodes]

    # Duplicate states
    if len(node_ids) != len(set(id for id in node_ids if id is not None)):
        return False

    # Duplicate transitions
    edge_keys = [(e.get("from"), e.get("to")) for e in graph.edges]
    if len(edge_keys) != len(set(edge_keys)):
        return False

    node_id_set = set(id for id in node_ids if id is not None)
    for edge in graph.edges:
        src = edge.get("from")
        dst = edge.get("to")
        # Transition validity
        if not src or not dst:
            return False
        # State existence
        if src not in node_id_set or dst not in node_id_set:
            return False

    return True
