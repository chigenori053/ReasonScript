"""Deterministic MIRP logical projections for ReasonGraph v0.1."""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from .model import canonicalize_graph, validate_graph


MIRP_GRAPH_FRAGMENT_SCHEMA = "mra-mirp-graph-fragment/0.1"


def project_mirp_unit(graph: dict[str, Any], unit_id: str) -> dict[str, Any]:
    """Project one Unit as a self-contained MIRP logical message."""
    return project_mirp_fragment(graph, unit_ids=[unit_id], fragment_kind="unit")


def project_mirp_relation(graph: dict[str, Any], relation_id: str) -> dict[str, Any]:
    """Project one Relation with every endpoint required to resolve it."""
    return project_mirp_fragment(graph, relation_ids=[relation_id], fragment_kind="relation")


def project_mirp_fragment(
    graph: dict[str, Any],
    *,
    unit_ids: list[str] | None = None,
    relation_ids: list[str] | None = None,
    fragment_kind: str = "graph_fragment",
) -> dict[str, Any]:
    """Project a valid, closed logical Graph Fragment without transport behavior."""
    diagnostics = validate_graph(graph)
    if diagnostics:
        raise ValueError(f"MIRP projection requires a valid ReasonGraph: {diagnostics[0]['code']}")
    if fragment_kind not in {"unit", "relation", "unit_relation", "graph_fragment"}:
        raise ValueError("Unknown MIRP fragment kind")
    known_units = {item["unit_id"]: item for item in graph["units"]}
    known_relations = {item["relation_id"]: item for item in graph["relations"]}
    selected_units = _select(unit_ids, known_units, "Unit")
    selected_relations = _select(relation_ids, known_relations, "Relation")
    if unit_ids is None and relation_ids is None:
        selected_units, selected_relations = set(known_units), set(known_relations)
    _close_relation_endpoints(selected_units, selected_relations, known_relations)

    fragment_graph = {
        "graph_id": graph["graph_id"],
        "units": [copy.deepcopy(known_units[unit_id]) for unit_id in sorted(selected_units)],
        "relations": [copy.deepcopy(known_relations[relation_id]) for relation_id in sorted(selected_relations)],
        "root_refs": [
            copy.deepcopy(root)
            for root in graph.get("root_refs", [])
            if root.get("entity_kind") == "unit" and root.get("entity_id") in selected_units
        ],
        "lifecycle": graph["lifecycle"],
        "provenance": copy.deepcopy(graph["provenance"]),
        "metadata": copy.deepcopy(graph.get("metadata", {})),
    }
    if validate_graph(fragment_graph):
        raise ValueError("MIRP projection closure produced an invalid Graph Fragment")
    result = {
        "schema": MIRP_GRAPH_FRAGMENT_SCHEMA,
        "fragment_kind": fragment_kind,
        "graph": fragment_graph,
    }
    result["fragment_hash"] = "sha256:" + hashlib.sha256(canonicalize_graph(result).encode("utf-8")).hexdigest()
    return result


def _select(requested: list[str] | None, known: dict[str, Any], name: str) -> set[str]:
    if requested is None:
        return set()
    if not isinstance(requested, list) or not all(isinstance(item, str) for item in requested):
        raise ValueError(f"MIRP {name} selection must be a string list")
    missing = sorted(set(requested) - set(known))
    if missing:
        raise ValueError(f"MIRP {name} selection does not resolve: {', '.join(missing)}")
    return set(requested)


def _close_relation_endpoints(units: set[str], relations: set[str], known_relations: dict[str, dict[str, Any]]) -> None:
    pending = list(relations)
    while pending:
        relation_id = pending.pop()
        relation = known_relations[relation_id]
        for endpoint in (relation["source"], relation["target"]):
            if endpoint["entity_kind"] == "unit":
                units.add(endpoint["entity_id"])
            elif endpoint["entity_id"] not in relations:
                relations.add(endpoint["entity_id"])
                pending.append(endpoint["entity_id"])
