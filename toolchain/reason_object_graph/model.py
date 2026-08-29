"""JSON-compatible reference model for MRA Reason Object Graph v0.1."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import unicodedata
from typing import Any


CORE_RELATION_DIRECTIONS = {
    "causes": "directed",
    "supports": "directed",
    "contradicts": "directed",
    "depends_on": "directed",
    "contains": "directed",
    "part_of": "directed",
    "precedes": "directed",
    "equivalent_to": "symmetric",
    "observes": "directed",
    "derived_from": "directed",
}
CORE_RELATION_TYPES = frozenset(CORE_RELATION_DIRECTIONS)
MAX_RELATION_DEPTH = 1

_DIRECTIONS = {"directed", "bidirectional", "symmetric"}
_LIFECYCLES = {"proposed", "active", "suspended", "invalidated", "retired"}
_VALIDATION_STATES = {"unverified", "validated", "disputed", "rejected"}
_ENTITY_KINDS = {"unit", "relation"}
_DOMAIN_RELATION = re.compile(r"domain:[a-z][a-z0-9_-]{0,63}:[a-z][a-z0-9_-]{0,127}$")


def canonicalize_graph(value: Any) -> str:
    """Return deterministic UTF-8 JSON for a logical ReasonGraph value."""

    def normalize(item: Any, parent: str = "") -> Any:
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("non-finite numeric value")
            return 0 if item == 0 else item
        if isinstance(item, str):
            return unicodedata.normalize("NFC", item)
        if isinstance(item, dict):
            return {str(key): normalize(child, str(key)) for key, child in sorted(item.items(), key=lambda pair: str(pair[0]))}
        if isinstance(item, list):
            values = [normalize(child, parent) for child in item]
            if parent == "units":
                return sorted(values, key=lambda child: _identity(child, "unit_id"))
            if parent == "relations":
                return sorted(values, key=lambda child: _identity(child, "relation_id"))
            if parent in {"root_refs", "evidence_refs"}:
                return sorted(values, key=lambda child: json.dumps(child, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return values
        return item

    return json.dumps(normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def unit_hash(unit: dict[str, Any]) -> str:
    return _digest(unit)


def relation_hash(relation: dict[str, Any]) -> str:
    return _digest(relation)


def graph_hash(graph: dict[str, Any]) -> str:
    return _digest(graph)


def validate_graph(value: dict[str, Any]) -> list[dict[str, Any]]:
    """Return stable diagnostics for the v0.1 logical ReasonGraph contract."""
    diagnostics: list[dict[str, Any]] = []

    def error(code: str, stage: str, message: str, *affected_ids: str) -> None:
        diagnostics.append({
            "code": code,
            "severity": "ERROR",
            "stage": stage,
            "affected_ids": sorted(identifier for identifier in affected_ids if identifier),
            "message": message,
        })

    if not isinstance(value, dict):
        error("RRG-001", "graph", "ReasonGraph must be a JSON object.")
        return diagnostics
    try:
        canonicalize_graph(value)
    except (TypeError, ValueError):
        error("RRG-001", "canonicalization", "ReasonGraph values must be finite and JSON-compatible.")

    graph_id = _string(value.get("graph_id"))
    if not graph_id.startswith("ruo:graph:"):
        error("RRG-002", "identity", "Graph ID must use the ruo:graph: namespace.", graph_id)
    units = value.get("units", [])
    relations = value.get("relations", [])
    if not isinstance(units, list) or not isinstance(relations, list):
        error("RRG-001", "graph", "Graph units and relations must be lists.", graph_id)
        return _sorted(diagnostics)

    unit_ids = _validate_units(units, error)
    relation_ids = _validate_relation_ids(relations, error)
    known_ids = unit_ids | relation_ids
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        _validate_relation(relation, known_ids, error)
    _validate_relation_depth(relations, error)
    _validate_roots(value.get("root_refs", []), unit_ids, error)
    _validate_graph_envelope(value, error)
    return _sorted(diagnostics)


def reference_graph() -> dict[str, Any]:
    """Return a valid fixture used by the Phase 2 RRI test set."""
    provenance = {
        "origin": "inference",
        "producer": "reason-object-graph-fixture",
        "source_ref": "fixture:phase2",
        "created_at": "1970-01-01T00:00:00Z",
        "derivation_ref": "fixture:derivation:0",
    }
    return {
        "graph_id": "ruo:graph:phase2-fixture",
        "units": [
            {
                "unit_id": "ruo:unit:a",
                "unit_type": "claim",
                "state": {"status": "ready"},
                "payload": {"symbol": "A"},
                "evidence_refs": ["ruo:evidence:a"],
                "lifecycle": "active",
                "provenance": copy.deepcopy(provenance),
                "metadata": {},
            },
            {
                "unit_id": "ruo:unit:b",
                "unit_type": "claim",
                "state": {"status": "ready"},
                "payload": {"symbol": "B"},
                "evidence_refs": [],
                "lifecycle": "active",
                "provenance": copy.deepcopy(provenance),
                "metadata": {},
            },
        ],
        "relations": [
            {
                "relation_id": "ruo:relation:a-causes-b",
                "source": {"entity_kind": "unit", "entity_id": "ruo:unit:a"},
                "target": {"entity_kind": "unit", "entity_id": "ruo:unit:b"},
                "relation_type": "causes",
                "direction": "directed",
                "strength": 0.8,
                "evidence_refs": ["ruo:evidence:a"],
                "temporal_scope": {"kind": "persistent"},
                "validation_state": "validated",
                "lifecycle": "active",
                "provenance": copy.deepcopy(provenance),
                "metadata": {},
            },
        ],
        "root_refs": [{"entity_kind": "unit", "entity_id": "ruo:unit:a"}],
        "lifecycle": "active",
        "provenance": provenance,
        "metadata": {},
    }


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonicalize_graph(value).encode("utf-8")).hexdigest()


def _identity(value: Any, key: str) -> str:
    return _string(value.get(key)) if isinstance(value, dict) else ""


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _validate_units(units: list[Any], error: Any) -> set[str]:
    seen: set[str] = set()
    for unit in units:
        if not isinstance(unit, dict):
            error("RRG-003", "unit", "Every Unit must be an object.")
            continue
        unit_id = _string(unit.get("unit_id"))
        if not unit_id.startswith("ruo:unit:"):
            error("RRG-003", "identity", "Unit ID must use the ruo:unit: namespace.", unit_id)
        if unit_id in seen:
            error("RRG-004", "identity", "Unit IDs must be unique within a Graph.", unit_id)
        seen.add(unit_id)
        _validate_reason_object(unit, unit_id, "Unit", error)
    return seen


def _validate_relation_ids(relations: list[Any], error: Any) -> set[str]:
    seen: set[str] = set()
    for relation in relations:
        if not isinstance(relation, dict):
            error("RRG-005", "relation", "Every Relation must be an object.")
            continue
        relation_id = _string(relation.get("relation_id"))
        if not relation_id.startswith("ruo:relation:"):
            error("RRG-005", "identity", "Relation ID must use the ruo:relation: namespace.", relation_id)
        if relation_id in seen:
            error("RRG-006", "identity", "Relation IDs must be unique within a Graph.", relation_id)
        seen.add(relation_id)
    return seen


def _validate_reason_object(value: dict[str, Any], identifier: str, name: str, error: Any) -> None:
    if _string(value.get("lifecycle")) not in _LIFECYCLES:
        error("RRG-007", "lifecycle", f"{name} lifecycle is invalid.", identifier)
    provenance = value.get("provenance")
    if not isinstance(provenance, dict):
        error("RRG-008", "provenance", f"{name} provenance must be an object.", identifier)
    elif not {"origin", "producer", "source_ref", "created_at"}.issubset(provenance) or any(
        not _string(provenance[part]) for part in ("origin", "producer", "source_ref", "created_at")
    ):
        error("RRG-008", "provenance", f"{name} provenance requires origin, producer, source_ref, and created_at.", identifier)
    if not isinstance(value.get("evidence_refs", []), list) or any(not _string(reference) for reference in value.get("evidence_refs", [])):
        error("RRG-009", "evidence", f"{name} evidence_refs must be a string list.", identifier)


def _validate_relation(relation: dict[str, Any], known_ids: set[str], error: Any) -> None:
    relation_id = _string(relation.get("relation_id"))
    _validate_reason_object(relation, relation_id, "Relation", error)
    if relation.get("validation_state") not in _VALIDATION_STATES:
        error("RRG-010", "validation_state", "Relation validation state is invalid.", relation_id)
    relation_type = _string(relation.get("relation_type"))
    direction = relation.get("direction")
    if relation_type not in CORE_RELATION_TYPES and not _DOMAIN_RELATION.fullmatch(relation_type):
        error("RRG-011", "relation_type", "Relation type must be core or a valid domain namespace.", relation_id)
    if direction not in _DIRECTIONS:
        error("RRG-012", "direction", "Relation direction is invalid.", relation_id)
    elif relation_type in CORE_RELATION_TYPES and direction != CORE_RELATION_DIRECTIONS[relation_type]:
        error("RRG-012", "direction", "Core Relation direction conflicts with its type contract.", relation_id)
    for endpoint_name in ("source", "target"):
        endpoint = relation.get(endpoint_name)
        if not isinstance(endpoint, dict) or endpoint.get("entity_kind") not in _ENTITY_KINDS or not _string(endpoint.get("entity_id")):
            error("RRG-013", "reference", f"Relation {endpoint_name} must be a ReasonEntityRef.", relation_id)
            continue
        if endpoint["entity_id"] not in known_ids:
            error("RRG-014", "reference", "Relation endpoint does not resolve in this Graph.", relation_id, endpoint["entity_id"])
    if "strength" in relation and (isinstance(relation["strength"], bool) or not isinstance(relation["strength"], (int, float)) or not math.isfinite(relation["strength"]) or not 0 <= relation["strength"] <= 1):
        error("RRG-015", "strength", "Relation strength must be a finite number in [0.0, 1.0].", relation_id)
    _validate_temporal_scope(relation.get("temporal_scope"), relation_id, error)


def _validate_temporal_scope(scope: Any, relation_id: str, error: Any) -> None:
    if scope is None:
        return
    if not isinstance(scope, dict):
        error("RRG-016", "temporal", "Temporal scope must be an object.", relation_id)
        return
    kind = scope.get("kind")
    expected = {
        "instant": {"kind", "at"},
        "interval": {"kind", "valid_from", "valid_until"},
        "persistent": {"kind"},
        "unknown": {"kind"},
    }.get(kind)
    if expected is None or set(scope) != expected or any(not _string(scope[key]) for key in expected - {"kind"}):
        error("RRG-016", "temporal", "Temporal scope does not match a v0.1 temporal shape.", relation_id)


def _validate_relation_depth(relations: list[Any], error: Any) -> None:
    refs: dict[str, set[str]] = {}
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        relation_id = _string(relation.get("relation_id"))
        refs[relation_id] = {
            endpoint["entity_id"]
            for endpoint in (relation.get("source"), relation.get("target"))
            if isinstance(endpoint, dict) and endpoint.get("entity_kind") == "relation" and _string(endpoint.get("entity_id"))
        }
    for relation_id, direct_refs in refs.items():
        if any(refs.get(reference, set()) for reference in direct_refs):
            error("RRG-017", "recursion", f"Relation reference depth exceeds MAX_RELATION_DEPTH={MAX_RELATION_DEPTH}.", relation_id)


def _validate_roots(root_refs: Any, unit_ids: set[str], error: Any) -> None:
    if not isinstance(root_refs, list):
        error("RRG-018", "roots", "Graph root_refs must be a list.")
        return
    for root in root_refs:
        if not isinstance(root, dict) or root.get("entity_kind") != "unit" or _string(root.get("entity_id")) not in unit_ids:
            error("RRG-018", "roots", "Graph roots must resolve to Units.")


def _validate_graph_envelope(value: dict[str, Any], error: Any) -> None:
    graph_id = _string(value.get("graph_id"))
    if value.get("lifecycle") not in _LIFECYCLES:
        error("RRG-007", "lifecycle", "Graph lifecycle is invalid.", graph_id)
    _validate_reason_object(value, graph_id, "Graph", error)


def _sorted(diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(diagnostics, key=lambda item: (item["code"], item["stage"], item["affected_ids"], item["message"]))
