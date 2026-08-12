"""Deterministic, read-only ReasonGraph queries."""

from __future__ import annotations

import copy
from typing import Any

from .model import graph_hash, validate_graph


PROFILE = "reasonscript-reason-object-graph-query/0.1"
SUPPORTED_QUERIES = frozenset({"entity", "outgoing", "incoming", "neighbors", "summary"})


def query_graph(graph: dict[str, Any], query: str, entity_id: str | None = None) -> dict[str, Any]:
    """Return a stable, self-describing read-only query result."""
    diagnostics = validate_graph(graph)
    if diagnostics:
        raise ValueError(f"RGO-QUERY-001: invalid ReasonGraph ({diagnostics[0]['code']})")
    if query not in SUPPORTED_QUERIES:
        raise ValueError(f"RGO-QUERY-002: unsupported query {query}")
    units = {unit["unit_id"]: unit for unit in graph["units"]}
    relations = {relation["relation_id"]: relation for relation in graph["relations"]}
    entities = {**units, **relations}
    if query != "summary" and (not isinstance(entity_id, str) or entity_id not in entities):
        raise ValueError("RGO-QUERY-003: entity ID does not resolve in ReasonGraph")

    result: dict[str, Any] = {
        "profile": PROFILE,
        "graph_id": graph["graph_id"],
        "graph_hash": graph_hash(graph),
        "query": query,
        "entity_id": entity_id,
        "read_only": True,
    }
    if query == "summary":
        result["result"] = {"unit_count": len(units), "relation_count": len(relations), "root_refs": copy.deepcopy(graph["root_refs"])}
    elif query == "entity":
        result["result"] = copy.deepcopy(entities[entity_id])
    elif query in {"outgoing", "incoming"}:
        endpoint = "source" if query == "outgoing" else "target"
        result["result"] = [copy.deepcopy(relation) for _, relation in sorted(relations.items()) if relation[endpoint]["entity_id"] == entity_id]
    else:
        adjacent = []
        for relation_id, relation in sorted(relations.items()):
            source, target = relation["source"]["entity_id"], relation["target"]["entity_id"]
            if source == entity_id:
                adjacent.append({"relation_id": relation_id, "direction": "outgoing", "entity_ref": copy.deepcopy(relation["target"])})
            if target == entity_id:
                adjacent.append({"relation_id": relation_id, "direction": "incoming", "entity_ref": copy.deepcopy(relation["source"])})
        result["result"] = adjacent
    return result
