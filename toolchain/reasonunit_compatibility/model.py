"""In-memory RUO-C1 reference model.

The representation is deliberately made from JSON-compatible values.  It is a
compatibility adapter, not a new Runtime or language value.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

STATE_OWNERS = {
    "unit_local", "object_shared", "derived", "external_world",
    "cached_projection", "unknown",
}
ENTITY_KINDS = {"atomic_reasonunit", "composite_reasonunit"}
LIFECYCLE_STATES = {
    "proposed", "validated", "active", "suspended", "reactivated",
    "replaced", "pruned", "retired", "converged", "terminated",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _object_id(units: list[dict[str, Any]]) -> str:
    ids = sorted(str(unit.get("unit_id", "")) for unit in units)
    return "object:" + hashlib.sha256(_canonical(ids).encode("utf-8")).hexdigest()[:24]


def wrap_legacy_units(
    units: Iterable[dict[str, Any]],
    *,
    object_id: str | None = None,
    object_lifecycle: str = "active",
) -> dict[str, Any]:
    """Wrap legacy units without changing their canonical Unit identities."""
    legacy_units = copy.deepcopy(list(units))
    owner = object_id or _object_id(legacy_units)
    registry: list[dict[str, Any]] = []
    states: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    evidence: dict[str, dict[str, Any]] = {}
    dependencies: list[dict[str, str]] = []

    for legacy in legacy_units:
        known = {
            "unit_id", "kind", "role", "state", "state_owner", "relations",
            "evidence", "lifecycle", "revision", "children", "parent_unit_id",
            "dependencies", "execution", "ordered_children", "extensions",
        }
        unit_id = str(legacy.get("unit_id", ""))
        kind = str(legacy.get("kind", "atomic_reasonunit"))
        extension = copy.deepcopy(legacy.get("extensions", {}))
        unknown = {key: copy.deepcopy(value) for key, value in legacy.items() if key not in known}
        if unknown:
            extension.setdefault("legacy:unknown_fields", {}).update(unknown)
        unit = {
            "unit_id": unit_id,
            "entity_kind": kind,
            "role": legacy.get("role", "legacy"),
            "owner_object_id": owner,
            "parent_unit_id": legacy.get("parent_unit_id"),
            "children": list(legacy.get("children", [])),
            "ordered_children": bool(legacy.get("ordered_children", True)),
            "lifecycle": legacy.get("lifecycle", "active"),
            "revision": int(legacy.get("revision", 0)),
            "execution": copy.deepcopy(legacy.get("execution", {})),
            "extensions": extension,
        }
        registry.append(unit)
        if "state" in legacy:
            state_owner = legacy.get("state_owner", "unit_local")
            states.append({
                "state_id": f"state:{unit_id}",
                "owner_kind": state_owner,
                "owner_id": owner if state_owner == "object_shared" else unit_id,
                "value": copy.deepcopy(legacy["state"]),
                "source_revisions": copy.deepcopy(legacy.get("state", {}).get("source_revisions", {})) if isinstance(legacy.get("state"), dict) else {},
            })
        for relation in legacy.get("relations", []):
            item = copy.deepcopy(relation)
            item.setdefault("relation_id", f"relation:{len(relations) + 1:04}")
            item.setdefault("source_id", unit_id)
            relation_type = str(item.get("relation_type", "legacy:unknown"))
            if ":" not in relation_type and relation_type not in {"directed", "undirected", "contains", "cross_payload", "external"}:
                item["relation_type"] = f"legacy:{relation_type}"
            relations.append(item)
        for item in legacy.get("evidence", []):
            record = copy.deepcopy(item)
            evidence_id = str(record.get("evidence_id", ""))
            if evidence_id:
                record.setdefault("valid", True)
                record.setdefault("supports", [])
                if unit_id not in record["supports"]:
                    record["supports"].append(unit_id)
                if evidence_id in evidence:
                    existing = evidence[evidence_id]
                    existing_semantics = {key: value for key, value in existing.items() if key != "supports"}
                    record_semantics = {key: value for key, value in record.items() if key != "supports"}
                    if _canonical(existing_semantics) == _canonical(record_semantics):
                        existing["supports"] = sorted(set(existing.get("supports", [])) | set(record.get("supports", [])))
                        continue
                    # Distinct provenance or confidence must remain distinct.
                    evidence_id = f"{evidence_id}#{_digest(record)[7:15]}"
                    record["evidence_id"] = evidence_id
                evidence[evidence_id] = record
        for dependency in legacy.get("dependencies", []):
            dependencies.append({"unit_id": unit_id, "depends_on": str(dependency)})

    return {
        "schema_version": "reasonscript-reasonunit-object-reference/1.0",
        "object_identity": {"object_id": owner, "identity_domain": "ObjectIdentity"},
        "unit_registry": sorted(registry, key=lambda item: item["unit_id"]),
        "ownership_graph": [{"object_id": owner, "unit_id": item["unit_id"]} for item in sorted(registry, key=lambda item: item["unit_id"])],
        "state_registry": sorted(states, key=lambda item: item["state_id"]),
        "relation_registry": sorted(relations, key=lambda item: item["relation_id"]),
        "evidence_registry": [evidence[key] for key in sorted(evidence)],
        "lifecycle": object_lifecycle,
        "revision": 0,
        "dependency_graph": sorted(dependencies, key=lambda item: (item["unit_id"], item["depends_on"])),
        "execution_projection_policy": {"ordering": "unit_id", "exclude_lifecycle": ["suspended", "pruned", "retired", "terminated"]},
        "transaction_policy": {"atomic": True, "partial_commit_allowed": False},
        "extension_points": {},
        "legacy_snapshot": legacy_units,
    }


def _has_cycle(edges: dict[str, list[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(child) for child in edges.get(node, [])):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in sorted(edges))


def validate_wrapped_object(value: dict[str, Any], *, known_external_ids: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Return deterministically ordered RUO-C1 diagnostics."""
    diagnostics: list[dict[str, Any]] = []

    def error(code: str, stage: str, message: str, affected_ids: list[str]) -> None:
        diagnostics.append({
            "code": code, "severity": "ERROR", "stage": stage,
            "affected_ids": sorted(affected_ids), "evidence_refs": [], "message": message,
        })

    object_id = str(value.get("object_identity", {}).get("object_id", ""))
    units = value.get("unit_registry", [])
    unit_ids = [str(item.get("unit_id", "")) for item in units if isinstance(item, dict)]
    if not object_id or object_id in unit_ids or len(unit_ids) != len(set(unit_ids)):
        error("RUO-C1-003", "identity", "Object and Unit identities must be non-empty, distinct, and unique.", [object_id, *unit_ids])
    for unit in units:
        if unit.get("entity_kind") not in ENTITY_KINDS:
            error("RUO-C1-002", "classification", "Invalid ReasonEntity classification.", [str(unit.get("unit_id", ""))])
        if unit.get("owner_object_id") != object_id:
            error("RUO-C1-005", "ownership", "Each wrapped Unit must have exactly one canonical owner Object.", [str(unit.get("unit_id", ""))])
        if unit.get("lifecycle") not in LIFECYCLE_STATES:
            error("RUO-C1-010", "lifecycle", "Unknown lifecycle mapping.", [str(unit.get("unit_id", ""))])

    ownership_entries = value.get("ownership_graph", [])
    owner_counts = {unit_id: 0 for unit_id in unit_ids}
    ownership_edges: dict[str, list[str]] = {}
    for edge in ownership_entries:
        owner, child = str(edge.get("object_id", "")), str(edge.get("unit_id", ""))
        owner_counts[child] = owner_counts.get(child, 0) + 1
        ownership_edges.setdefault(owner, []).append(child)
    if any(owner_counts.get(unit_id) != 1 for unit_id in unit_ids):
        error("RUO-C1-005", "ownership", "A wrapped Unit has zero or multiple canonical owners.", unit_ids)
    if _has_cycle(ownership_edges):
        error("RUO-C1-006", "ownership", "Ownership graph contains a cycle.", unit_ids)

    containment: dict[str, list[str]] = {}
    for unit in units:
        parent = unit.get("parent_unit_id")
        if parent:
            containment.setdefault(str(parent), []).append(str(unit["unit_id"]))
        for child in unit.get("children", []):
            containment.setdefault(str(unit["unit_id"]), []).append(str(child))
    if _has_cycle(containment):
        error("RUO-C1-006", "containment", "Composite containment graph contains a cycle.", unit_ids)

    state_ids: set[str] = set()
    for state in value.get("state_registry", []):
        state_id, owner_kind, owner_id = str(state.get("state_id", "")), state.get("owner_kind"), str(state.get("owner_id", ""))
        state_ids.add(state_id)
        valid_owner = owner_kind in STATE_OWNERS and (
            (owner_kind in {"unit_local", "derived", "cached_projection", "unknown"} and owner_id in unit_ids)
            or (owner_kind == "object_shared" and owner_id == object_id)
            or owner_kind == "external_world"
        )
        if not valid_owner:
            error("RUO-C1-007", "state", "Invalid or ambiguous state ownership.", [state_id, owner_id])

    known = set(unit_ids) | set(known_external_ids)
    relation_ids: set[str] = set()
    for relation in value.get("relation_registry", []):
        relation_id = str(relation.get("relation_id", ""))
        relation_ids.add(relation_id)
        endpoints = [str(relation.get("source_id", "")), str(relation.get("target_id", ""))]
        if any(endpoint not in known for endpoint in endpoints):
            error("RUO-C1-008", "relations", "Dangling relation endpoint.", [relation_id, *endpoints])

    evidence_ids: set[str] = set()
    valid_supports = set(unit_ids) | state_ids | relation_ids
    for evidence in value.get("evidence_registry", []):
        evidence_id = str(evidence.get("evidence_id", ""))
        if not evidence_id or evidence_id in evidence_ids or any(str(target) not in valid_supports for target in evidence.get("supports", [])):
            error("RUO-C1-009", "evidence", "Evidence collision or invalid reference.", [evidence_id])
        evidence_ids.add(evidence_id)

    tensor = value.get("tensor_index_table", [])
    indexes = [entry.get("index") for entry in tensor if isinstance(entry, dict)]
    if len(indexes) != len(set(indexes)) or any(str(entry.get("unit_id", "")) not in unit_ids for entry in tensor if isinstance(entry, dict)):
        error("RUO-C1-015", "tensor", "Tensor indexes must map uniquely to stable Unit IDs.", unit_ids)
    if any(str(entry.get("unit_id", "")) == str(entry.get("index")) for entry in tensor if isinstance(entry, dict)):
        error("RUO-C1-015", "tensor", "Tensor index was used as Unit identity.", unit_ids)
    return sorted(diagnostics, key=lambda item: (item["code"], item["stage"], item["affected_ids"], item["message"]))


def _dependency_closure(value: dict[str, Any], selected: set[str]) -> set[str]:
    dependencies: dict[str, set[str]] = {}
    for edge in value.get("dependency_graph", []):
        dependencies.setdefault(str(edge["unit_id"]), set()).add(str(edge["depends_on"]))
    closure = set(selected)
    changed = True
    while changed:
        before = len(closure)
        for unit_id in list(closure):
            closure.update(dependencies.get(unit_id, set()))
        changed = len(closure) != before
    return closure


def project_existing_runtime_view(
    value: dict[str, Any],
    selected_unit_ids: Iterable[str] | None = None,
    *,
    profile: str = "existing-runtime/1.0",
    budget: int | None = None,
    priority: int = 0,
) -> dict[str, Any]:
    units = {str(item["unit_id"]): item for item in value.get("unit_registry", [])}
    requested = set(selected_unit_ids) if selected_unit_ids is not None else set(units)
    closure = _dependency_closure(value, requested)
    excluded_lifecycle = set(value.get("execution_projection_policy", {}).get("exclude_lifecycle", []))
    selected = sorted(unit_id for unit_id in closure if unit_id in units and units[unit_id].get("lifecycle") not in excluded_lifecycle)
    suspended = sorted(unit_id for unit_id in closure if unit_id in units and units[unit_id].get("lifecycle") == "suspended")
    unknown = sorted(unit_id for unit_id in closure if unit_id not in units)
    object_id = str(value["object_identity"]["object_id"])
    state_snapshot = value.get("state_registry", [])
    projection_seed = {"object_id": object_id, "revision": value.get("revision", 0), "profile": profile, "selected": selected}
    relations = [item for item in value.get("relation_registry", []) if item.get("source_id") in selected and item.get("target_id") in selected]
    projection = {
        "projection_id": "projection:" + _digest(projection_seed)[7:31],
        "profile": profile,
        "source_object_id": object_id,
        "source_object_revision": value.get("revision", 0),
        "selected_unit_ids": selected,
        "excluded_unit_ids": sorted(set(units) - set(selected)),
        "not_loaded_unit_ids": [],
        "suspended_unit_ids": suspended,
        "unknown_unit_ids": unknown,
        "state_snapshot_digest": _digest(state_snapshot),
        "relation_subset": sorted(relations, key=lambda item: str(item.get("relation_id", ""))),
        "dependency_closure": sorted(closure),
        "budget": budget,
        "priority": priority,
        "lifecycle_eligibility": {unit_id: unit_id in selected for unit_id in sorted(closure)},
        "tensor_index_table": sorted(value.get("tensor_index_table", []), key=lambda item: item["index"]),
        "deterministic_ordering": "unit_id",
    }
    projection["units"] = [copy.deepcopy(units[unit_id]) for unit_id in selected]
    return projection


def projection_is_current(value: dict[str, Any], projection: dict[str, Any]) -> bool:
    return (
        projection.get("source_object_id") == value.get("object_identity", {}).get("object_id")
        and projection.get("source_object_revision") == value.get("revision")
        and projection.get("state_snapshot_digest") == _digest(value.get("state_registry", []))
    )


def derived_state_is_stale(value: dict[str, Any], state_id: str) -> bool:
    """Compare recorded source revisions with current Unit/Object revisions."""
    state = next((item for item in value.get("state_registry", []) if item.get("state_id") == state_id), None)
    if not state or state.get("owner_kind") != "derived":
        return False
    revisions = {str(unit["unit_id"]): int(unit.get("revision", 0)) for unit in value.get("unit_registry", [])}
    revisions[str(value.get("object_identity", {}).get("object_id", ""))] = int(value.get("revision", 0))
    return any(revisions.get(str(source_id)) != recorded for source_id, recorded in state.get("source_revisions", {}).items())


def invalidate_evidence(value: dict[str, Any], affected_ids: Iterable[str], *, revision_id: str) -> list[str]:
    """Invalidate only evidence whose declared support dependency is affected."""
    affected = set(affected_ids)
    invalidated: list[str] = []
    for evidence in value.get("evidence_registry", []):
        if affected.intersection(str(item) for item in evidence.get("supports", [])):
            evidence["valid"] = False
            evidence["invalidated_by_revision"] = revision_id
            invalidated.append(str(evidence["evidence_id"]))
    return sorted(invalidated)


def query_compatibility(value: dict[str, Any], query: str, identifier: str | int | None = None) -> Any:
    """Execute the deterministic query surface required by RUO-C1."""
    units = {str(item["unit_id"]): item for item in value.get("unit_registry", [])}
    if query == "unit_by_id":
        return copy.deepcopy(units.get(str(identifier)))
    if query == "owner_of_unit":
        unit = units.get(str(identifier))
        return unit.get("owner_object_id") if unit else None
    if query == "containment_parent_and_children":
        unit = units.get(str(identifier))
        return None if unit is None else {"parent_unit_id": unit.get("parent_unit_id"), "children": sorted(unit.get("children", []))}
    if query == "state_owner_and_committed_state":
        state = next((item for item in value.get("state_registry", []) if item.get("state_id") == identifier), None)
        return copy.deepcopy(state)
    if query == "internal_and_external_relations":
        internal, external = [], []
        for relation in value.get("relation_registry", []):
            (internal if relation.get("source_id") in units and relation.get("target_id") in units else external).append(copy.deepcopy(relation))
        def relation_key(item: dict[str, Any]) -> str:
            return str(item.get("relation_id", ""))

        return {"internal": sorted(internal, key=relation_key), "external": sorted(external, key=relation_key)}
    if query == "supporting_evidence":
        return sorted((copy.deepcopy(item) for item in value.get("evidence_registry", []) if str(identifier) in [str(target) for target in item.get("supports", [])]), key=lambda item: item["evidence_id"])
    if query == "lifecycle":
        return value.get("lifecycle") if identifier == value.get("object_identity", {}).get("object_id") else units.get(str(identifier), {}).get("lifecycle")
    if query == "dependencies_and_invalidation":
        closure = _dependency_closure(value, {str(identifier)})
        return {"dependency_closure": sorted(closure), "stale_state_ids": sorted(item["state_id"] for item in value.get("state_registry", []) if derived_state_is_stale(value, item["state_id"]))}
    if query == "execution_eligible_units":
        return project_existing_runtime_view(value)["selected_unit_ids"]
    if query == "tensor_index_to_unit_id":
        entry = next((item for item in value.get("tensor_index_table", []) if item.get("index") == identifier), None)
        return entry.get("unit_id") if entry else None
    if query == "revision_diff":
        previous = value.get("extension_points", {}).get("revision_snapshots", {}).get(str(identifier))
        return None if previous is None else {"previous_revision": identifier, "current_revision": value.get("revision"), "changed": _canonical(previous) != _canonical(value)}
    raise ValueError(f"unsupported compatibility query: {query}")


def unwrap_legacy_units(value: dict[str, Any]) -> list[dict[str, Any]]:
    """Project back to the exact supported legacy snapshot."""
    return copy.deepcopy(value.get("legacy_snapshot", []))


def compare_semantics(before: Iterable[dict[str, Any]], after: Iterable[dict[str, Any]]) -> dict[str, Any]:
    left, right = list(before), list(after)
    equal = _canonical(left) == _canonical(right)
    return {
        "existing_unit_ids_preserved": [item.get("unit_id") for item in left] == [item.get("unit_id") for item in right],
        "existing_state_preserved": equal,
        "existing_relations_preserved": equal,
        "existing_evidence_preserved": equal,
        "existing_lifecycle_preserved": equal,
        "existing_execution_result_preserved": equal,
        "new_object_fields_optional_for_legacy": True,
        "semantic_loss_count": 0 if equal else 1,
    }


@dataclass
class ObjectTransaction:
    """Copy-on-write Object transaction with zero-partial-commit rollback."""

    value: dict[str, Any]

    def commit(self, state_updates: dict[str, Any], *, expected_revision: int, transaction_id: str) -> dict[str, Any]:
        before = copy.deepcopy(self.value)
        if expected_revision != before.get("revision"):
            return self._rollback(before, transaction_id, "state_conflict")
        candidate = copy.deepcopy(before)
        changed_units: set[str] = set()
        for state in candidate.get("state_registry", []):
            if state["state_id"] in state_updates:
                state["value"] = copy.deepcopy(state_updates[state["state_id"]])
                if state.get("owner_kind") == "unit_local":
                    changed_units.add(str(state.get("owner_id")))
        if set(state_updates) - {item["state_id"] for item in candidate.get("state_registry", [])}:
            return self._rollback(before, transaction_id, "unknown_state")
        diagnostics = validate_wrapped_object(candidate)
        if diagnostics:
            return self._rollback(before, transaction_id, "validation_failed")
        candidate["revision"] = int(before.get("revision", 0)) + 1
        for unit in candidate.get("unit_registry", []):
            if unit["unit_id"] in changed_units:
                unit["revision"] = int(unit.get("revision", 0)) + 1
        self.value.clear()
        self.value.update(candidate)
        return {"transaction_id": transaction_id, "committed": True, "partial_commit_count": 0, "object_revision": candidate["revision"], "changed_unit_ids": sorted(changed_units)}

    def _rollback(self, before: dict[str, Any], transaction_id: str, reason: str) -> dict[str, Any]:
        self.value.clear()
        self.value.update(before)
        return {"transaction_id": transaction_id, "committed": False, "reason": reason, "partial_commit_count": 0, "object_revision": before.get("revision"), "canonical_state_digest": _digest(before.get("state_registry", []))}
