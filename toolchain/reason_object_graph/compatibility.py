"""Read-only Legacy RUO and RUO-U1 projection into ReasonGraph v0.1."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

from .model import CORE_RELATION_DIRECTIONS, canonicalize_graph, validate_graph


PROFILE = "reasonscript-reason-object-graph-compatibility/0.1"
_SAFE_NAME = re.compile(r"[^a-z0-9_-]+")


def project_to_graph(source: dict[str, Any]) -> dict[str, Any]:
    """Project a legacy or RUO-U1 value without mutating its source value."""
    if not isinstance(source, dict):
        raise ValueError("Reason Object Graph compatibility input must be an object")
    source_copy = copy.deepcopy(source)
    snapshot_available = _json_compatible(source_copy)
    loss_records: list[dict[str, Any]] = []
    if not snapshot_available:
        loss_records.append({
            "code": "RRG-COMP-001",
            "path": "$",
            "reason": "source is not JSON-compatible and cannot be reverse-projected exactly",
        })

    units, unit_map, unit_mappings = _project_units(source_copy)
    raw_relations = _collect_relations(source_copy, unit_map)
    relations: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    relation_mappings: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for locator, raw, source_id, target_id in raw_relations:
        relation, mapping, reason = _project_relation(raw, locator, source_id, target_id, unit_map, used_ids)
        relation_mappings.append(mapping)
        if relation is None:
            retained.append(_safe_compatibility_record(locator, raw, reason))
            continue
        relations.append(relation)
        used_ids.add(relation["relation_id"])

    source_digest = _digest(source_copy) if snapshot_available else "unavailable"
    graph_id = _graph_id(source_copy, source_digest)
    graph = {
        "graph_id": graph_id,
        "units": units,
        "relations": relations,
        "root_refs": _root_refs(source_copy, unit_map, units),
        "lifecycle": _lifecycle(source_copy.get("lifecycle_state", source_copy.get("lifecycle"))),
        "provenance": _provenance(source_copy.get("provenance"), "import", "compatibility-adapter", source_digest),
        "metadata": {
            "compatibility": {
                "profile": PROFILE,
                "source_kind": "ruo-u1" if "object_identity" in source_copy else "legacy-ruo",
                "legacy_snapshot": source_copy if snapshot_available else None,
                "unsupported_relations": retained,
            },
        },
    }
    diagnostics = validate_graph(graph)
    if diagnostics:
        raise ValueError(f"Compatibility projection produced an invalid graph: {diagnostics[0]['code']}")
    report = {
        "profile": PROFILE,
        "lossless": snapshot_available,
        "canonical_coverage": not retained,
        "loss_records": loss_records,
        "unit_identity_mappings": unit_mappings,
        "relation_identity_mappings": relation_mappings,
        "relation_counts": {
            "source": len(raw_relations),
            "promoted": len(relations),
            "retained_for_reverse_projection": len(retained),
        },
    }
    return {"graph": graph, "report": report}


def reverse_project(projection: dict[str, Any]) -> dict[str, Any]:
    """Return the original compatibility snapshot when exact projection is possible."""
    report = projection.get("report", {}) if isinstance(projection, dict) else {}
    graph = projection.get("graph", {}) if isinstance(projection, dict) else {}
    snapshot = graph.get("metadata", {}).get("compatibility", {}).get("legacy_snapshot") if isinstance(graph, dict) else None
    return {
        "lossless": bool(report.get("lossless")) and snapshot is not None,
        "value": copy.deepcopy(snapshot),
        "loss_records": copy.deepcopy(report.get("loss_records", [])),
    }


def _project_units(source: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    raw_units = source.get("units", source.get("unit_registry", []))
    if not isinstance(raw_units, list):
        raise ValueError("Compatibility source units must be a list")
    units: list[dict[str, Any]] = []
    unit_map: dict[str, str] = {}
    mappings: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_units):
        if not isinstance(raw, dict):
            raise ValueError("Compatibility source Unit must be an object")
        original_id = _unit_original_id(raw, index)
        graph_id = original_id if original_id.startswith("ruo:unit:") else _generated_id("unit", {"id": original_id, "raw": raw})
        if original_id in unit_map or graph_id in unit_map.values():
            raise ValueError("Compatibility source Unit identity collision")
        unit_map[original_id] = graph_id
        provenance = _provenance(raw.get("provenance"), "import", "compatibility-adapter", f"legacy-unit:{original_id}")
        units.append({
            "unit_id": graph_id,
            "unit_type": str(raw.get("unit_type", raw.get("kind", raw.get("entity_kind", "legacy_unit")))),
            "state": copy.deepcopy(raw.get("state", {})),
            "payload": copy.deepcopy(raw.get("payload", {})),
            "evidence_refs": _evidence_refs(raw),
            "lifecycle": _lifecycle(raw.get("lifecycle_state", raw.get("lifecycle"))),
            "provenance": provenance,
            "metadata": {"compatibility": {"original_unit_id": original_id}},
        })
        mappings.append({"source_id": original_id, "graph_id": graph_id, "preserved": graph_id == original_id})
    return units, unit_map, mappings


def _collect_relations(source: dict[str, Any], unit_map: dict[str, str]) -> list[tuple[str, dict[str, Any], str, str]]:
    collected: list[tuple[str, dict[str, Any], str, str]] = []
    raw_units = source.get("units", source.get("unit_registry", []))
    for unit_index, raw_unit in enumerate(raw_units if isinstance(raw_units, list) else []):
        if not isinstance(raw_unit, dict):
            continue
        source_id = _unit_original_id(raw_unit, unit_index)
        for relation_index, raw_relation in enumerate(raw_unit.get("relations", [])):
            if isinstance(raw_relation, dict):
                target_id = _string(raw_relation.get("target", raw_relation.get("target_id", raw_relation.get("to"))))
                collected.append((f"units[{unit_index}].relations[{relation_index}]", raw_relation, source_id, target_id))
    for relation_index, raw_relation in enumerate(source.get("relations", source.get("relation_registry", []))):
        if not isinstance(raw_relation, dict):
            continue
        source_id = _string(raw_relation.get("source_id", raw_relation.get("source", raw_relation.get("from"))))
        target_id = _string(raw_relation.get("target_id", raw_relation.get("target", raw_relation.get("to"))))
        collected.append((f"relations[{relation_index}]", raw_relation, source_id, target_id))
    return collected


def _project_relation(
    raw: dict[str, Any],
    locator: str,
    source_id: str,
    target_id: str,
    unit_map: dict[str, str],
    used_ids: set[str],
) -> tuple[dict[str, Any] | None, dict[str, Any], str | None]:
    original_id = _string(raw.get("relation_id"))
    relation_id = original_id if original_id.startswith("ruo:relation:") else _generated_id(
        "relation", {"locator": locator, "source": source_id, "target": target_id, "raw": raw}
    )
    mapping = {"source_id": original_id or locator, "graph_id": relation_id, "promoted": False}
    if source_id not in unit_map or target_id not in unit_map:
        return None, mapping, "endpoint is not a projected Unit"
    if relation_id in used_ids:
        return None, mapping, "Relation identity collision"
    raw_type = _string(raw.get("relation_type", raw.get("type"))) or "legacy_unknown"
    relation_type = raw_type if raw_type in CORE_RELATION_DIRECTIONS or raw_type.startswith("domain:") else f"domain:legacy:{_safe_name(raw_type)}"
    direction = raw.get("direction", raw.get("directionality", CORE_RELATION_DIRECTIONS.get(relation_type, "directed")))
    if relation_type in CORE_RELATION_DIRECTIONS:
        direction = CORE_RELATION_DIRECTIONS[relation_type]
    relation = {
        "relation_id": relation_id,
        "source": {"entity_kind": "unit", "entity_id": unit_map[source_id]},
        "target": {"entity_kind": "unit", "entity_id": unit_map[target_id]},
        "relation_type": relation_type,
        "direction": direction,
        "evidence_refs": _evidence_refs(raw),
        "validation_state": raw.get("validation_state", "unverified"),
        "lifecycle": _lifecycle(raw.get("lifecycle_state", raw.get("lifecycle"))),
        "provenance": _provenance(raw.get("provenance"), "import", "compatibility-adapter", f"legacy-relation:{locator}"),
        "metadata": {"compatibility": {"original_relation_id": original_id or None, "original_relation_type": raw_type}},
    }
    for key in ("strength", "temporal_scope"):
        if key in raw:
            relation[key] = copy.deepcopy(raw[key])
    mapping["promoted"] = True
    return relation, mapping, None


def _root_refs(source: dict[str, Any], unit_map: dict[str, str], units: list[dict[str, Any]]) -> list[dict[str, str]]:
    raw_roots = source.get("root_units", source.get("root_refs", []))
    if not isinstance(raw_roots, list):
        raw_roots = []
    roots = []
    for root in raw_roots:
        original_id = _string(root.get("entity_id")) if isinstance(root, dict) else _string(root)
        if original_id in unit_map:
            roots.append({"entity_kind": "unit", "entity_id": unit_map[original_id]})
    return roots or ([{"entity_kind": "unit", "entity_id": units[0]["unit_id"]}] if units else [])


def _provenance(value: Any, origin: str, producer: str, source_ref: str) -> dict[str, str]:
    if isinstance(value, dict) and all(_string(value.get(key)) for key in ("origin", "producer", "source_ref", "created_at")):
        return {key: _string(value[key]) for key in ("origin", "producer", "source_ref", "created_at", "derivation_ref") if key in value}
    return {"origin": origin, "producer": producer, "source_ref": source_ref, "created_at": "1970-01-01T00:00:00Z"}


def _evidence_refs(value: dict[str, Any]) -> list[str]:
    direct = value.get("evidence_refs", [])
    if isinstance(direct, list) and all(isinstance(item, str) for item in direct):
        return copy.deepcopy(direct)
    evidence = value.get("evidence", [])
    if isinstance(evidence, list):
        return sorted(item["evidence_id"] for item in evidence if isinstance(item, dict) and isinstance(item.get("evidence_id"), str))
    return []


def _lifecycle(value: Any) -> str:
    return value if value in {"proposed", "active", "suspended", "invalidated", "retired"} else "active"


def _unit_original_id(value: dict[str, Any], index: int) -> str:
    for key in ("unit_id", "entity_id", "id", "locator", "name"):
        candidate = _string(value.get(key))
        if candidate:
            return candidate
    return f"unit-{index}"


def _graph_id(source: dict[str, Any], source_digest: str) -> str:
    candidate = _string(source.get("graph_id"))
    return candidate if candidate.startswith("ruo:graph:") else _generated_id("graph", {"source_digest": source_digest})


def _generated_id(kind: str, value: Any) -> str:
    return f"ruo:{kind}:" + hashlib.sha256(canonicalize_graph(value).encode("utf-8")).hexdigest()[:24]


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonicalize_graph(value).encode("utf-8")).hexdigest()


def _safe_name(value: str) -> str:
    result = _SAFE_NAME.sub("-", value.lower()).strip("-")
    return result or "unknown"


def _safe_compatibility_record(locator: str, raw: dict[str, Any], reason: str | None) -> dict[str, Any]:
    return {
        "locator": locator,
        "reason": reason,
        "original": copy.deepcopy(raw) if _json_compatible(raw) else {"status": "unavailable_non_json_compatible"},
    }


def _json_compatible(value: Any) -> bool:
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return True


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""
