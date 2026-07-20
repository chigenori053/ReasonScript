"""Domain-independent, JSON-compatible RUO-U1 logical reference model."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import unicodedata
from typing import Any, Iterable


CORE_PREFIXES = {
    "object": "ruo:object:", "unit": "ruo:unit:", "payload": "ruo:payload:",
    "state": "ruo:state:", "relation": "ruo:relation:", "evidence": "ruo:evidence:",
    "constraint": "ruo:constraint:", "revision": "ruo:revision:",
    "transaction": "ruo:transaction:", "projection": "ruo:projection:",
}
PAYLOAD_PROFILES = {
    "ruo.payload.scalar/1", "ruo.payload.text/1", "ruo.payload.numeric/1",
    "ruo.payload.temporal/1", "ruo.payload.spatial/1", "ruo.payload.graph/1",
    "ruo.payload.tensor-ref/1", "ruo.payload.binary-ref/1", "ruo.payload.abstract/1",
}
STATE_CLASSES = {"unit_local", "object_shared", "derived", "external", "cached", "unknown"}
RELATION_CLASSES = {"internal", "cross_payload", "cross_object", "external", "project_local"}
KNOWLEDGE_STATES = {"loaded", "not_loaded", "unavailable", "redacted", "unknown", "omitted_by_profile"}
VALUE_PRESENCE = {"present", "not_loaded", "unknown", "redacted", "external"}
LIFECYCLE = {"proposed", "active", "suspended", "reactivated", "replaced", "pruned", "retired", "converged", "terminated", "deleted"}


def canonicalize(value: Any) -> str:
    """Return normative U1 test-carrier JSON; set-like registries sort by identity."""
    def normalize(item: Any, parent: str = "") -> Any:
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("non-finite numeric value")
        if isinstance(item, str):
            return unicodedata.normalize("NFC", item)
        if isinstance(item, dict):
            return {key: normalize(item[key], key) for key in sorted(item)}
        if isinstance(item, list):
            values = [normalize(child, parent) for child in item]
            if parent.endswith("_registry") or parent in {
                "units", "payloads", "states", "relations", "constraints",
                "projection_descriptors", "extension_registry", "root_units",
                "selected_units", "excluded_entities",
            }:
                def identity(child: Any) -> str:
                    if not isinstance(child, dict):
                        return str(child)
                    for key in ("entity_id", "payload_id", "state_id", "relation_id", "evidence_id", "constraint_id", "projection_id", "namespace"):
                        if key in child:
                            return str(child[key])
                    return json.dumps(child, sort_keys=True, ensure_ascii=False)
                return sorted(values, key=identity)
            return values
        return item
    return json.dumps(normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonicalize(value).encode()).hexdigest()


def _cycle(edges: dict[str, set[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(child) for child in sorted(edges.get(node, set()))):
            return True
        visiting.remove(node); visited.add(node)
        return False
    return any(visit(node) for node in sorted(edges))


def validate_object(value: dict[str, Any], *, limits: dict[str, int] | None = None) -> list[dict[str, Any]]:
    """Validate loaded facts only and return stable RUO-U1 diagnostics."""
    limits = {"object_bytes": 2_000_000, "entities": 10_000, "containment_depth": 128,
              "relations": 10_000, "evidence": 10_000, "extensions_bytes": 250_000,
              "diagnostics": 1_000, **(limits or {})}
    found: list[dict[str, Any]] = []
    def error(code: str, stage: str, message: str, *ids: str, profile: str | None = None) -> None:
        item: dict[str, Any] = {"code": code, "severity": "ERROR", "stage": stage,
            "affected_ids": sorted(filter(None, ids)), "evidence_refs": [], "message": message}
        if profile: item["profile_or_namespace"] = profile
        if len(found) < limits["diagnostics"]: found.append(item)
    try:
        size = len(canonicalize(value).encode())
    except (ValueError, TypeError):
        error("RUO-U1-009", "normalization", "Canonical values must be finite and JSON-compatible.")
        size = 0
    registries = {name: value.get(name, []) for name in ("units", "payloads", "states", "relations", "constraints", "evidence_registry", "projection_descriptors")}
    if size > limits["object_bytes"] or sum(len(v) for v in registries.values() if isinstance(v, list)) > limits["entities"]:
        error("RUO-U1-027", "resources", "Configured Object resource limit exceeded.")
    object_id = str(value.get("object_identity", {}).get("entity_id", ""))
    if not object_id.startswith(CORE_PREFIXES["object"]):
        error("RUO-U1-004", "identity", "Invalid Object identity namespace.", object_id)
    identities: dict[str, str] = {object_id: "object"} if object_id else {}
    key_by_registry = {"units": "entity_id", "payloads": "payload_id", "states": "state_id", "relations": "relation_id", "constraints": "constraint_id", "evidence_registry": "evidence_id", "projection_descriptors": "projection_id"}
    prefix_by_registry = {"units": "unit", "payloads": "payload", "states": "state", "relations": "relation", "constraints": "constraint", "evidence_registry": "evidence", "projection_descriptors": "projection"}
    for registry, items in registries.items():
        if not isinstance(items, list): error("RUO-U1-003", "entity", "Registry must be a list.", registry); continue
        for entity in items:
            entity_id = str(entity.get(key_by_registry[registry], "")) if isinstance(entity, dict) else ""
            if not entity_id.startswith(CORE_PREFIXES[prefix_by_registry[registry]]):
                error("RUO-U1-004", "identity", "Invalid or missing entity namespace.", entity_id)
            if entity_id in identities:
                error("RUO-U1-004", "identity", "Identity collision.", entity_id)
            identities[entity_id] = registry
    units = {item.get("entity_id"): item for item in registries["units"] if isinstance(item, dict)}
    payloads = {item.get("payload_id"): item for item in registries["payloads"] if isinstance(item, dict)}
    local_ids = set(identities)
    parents: dict[str, str] = {}
    containment: dict[str, set[str]] = {}
    for unit_id, unit in units.items():
        if unit.get("owner_object_id") != object_id:
            error("RUO-U1-005", "ownership", "Local Unit must have exactly one Object owner.", str(unit_id))
        children = unit.get("children", [])
        if unit.get("entity_kind") == "atomic_reasonunit" and children:
            error("RUO-U1-003", "containment", "Atomic Unit cannot contain children.", str(unit_id))
        for child in children:
            if child in parents and parents[child] != unit_id:
                error("RUO-U1-005", "containment", "Unit has multiple containment parents.", str(child))
            parents[str(child)] = str(unit_id); containment.setdefault(str(unit_id), set()).add(str(child))
    if _cycle(containment): error("RUO-U1-006", "containment", "Containment graph contains a cycle.", *units)
    roots = set(value.get("root_units", []))
    reachable = set(roots)
    while True:
        expanded = reachable | {child for parent in reachable for child in containment.get(parent, set())}
        if expanded == reachable: break
        reachable = expanded
    unattached = set(value.get("partial_loading", {}).get("unattached_retained_entities", []))
    missing_reach = set(units) - reachable - unattached
    if missing_reach: error("RUO-U1-005", "containment", "Local Units must be root-reachable or retained unattached.", *missing_reach)
    for payload_id, payload in payloads.items():
        profile = payload.get("profile_id")
        if payload.get("owner_id") not in local_ids or payload.get("value_presence") not in VALUE_PRESENCE or profile not in PAYLOAD_PROFILES:
            error("RUO-U1-007", "payload", "Invalid Payload envelope, owner, presence, or profile.", str(payload_id), profile=str(profile))
        if profile in {"ruo.payload.numeric/1", "ruo.payload.spatial/1"} and payload.get("value_presence") == "present":
            body = payload.get("value", {})
            if not body.get("unit") or not body.get("reference_frame"):
                error("RUO-U1-009", "payload", "Numeric/spatial interpretation requires unit and reference frame.", str(payload_id), profile=str(profile))
        if profile == "ruo.payload.text/1" and payload.get("value_presence") == "present" and not payload.get("value", {}).get("offset_indexing"):
            error("RUO-U1-008", "payload", "Text offsets require an indexing convention.", str(payload_id), profile=str(profile))
        if profile == "ruo.payload.tensor-ref/1" and any(not isinstance(row.get("index"), int) for row in payload.get("value_ref", {}).get("unit_index_map", [])):
            error("RUO-U1-021", "payload", "Tensor index cannot be semantic identity.", str(payload_id))
    for state in registries["states"]:
        if state.get("state_class") not in STATE_CLASSES or state.get("owner_id") not in local_ids:
            error("RUO-U1-010", "state", "Invalid state ownership class or owner.", str(state.get("state_id", "")))
        if state.get("state_class") in {"derived", "cached"} and state.get("validity") == "current":
            revisions = state.get("source_revisions", {})
            current = {entity_id: entity.get("last_modified_revision") for entity_id, entity in units.items()}
            if any(current.get(key) != rev for key, rev in revisions.items()):
                error("RUO-U1-014", "state", "Stale state cannot be presented as current.", str(state.get("state_id", "")))
    for relation in registries["relations"]:
        relation_id = str(relation.get("relation_id", "")); klass = relation.get("relation_class")
        if klass not in RELATION_CLASSES: error("RUO-U1-011", "relation", "Invalid relation class.", relation_id)
        status = relation.get("endpoint_resolution", "resolved")
        if status == "resolved" and klass in {"internal", "cross_payload"} and (relation.get("source_id") not in local_ids or relation.get("target_id") not in local_ids):
            error("RUO-U1-011", "relation", "Resolved local relation has a dangling endpoint.", relation_id)
        if status not in {"resolved", "not_loaded", "unavailable", "unknown"}:
            error("RUO-U1-011", "relation", "Invalid endpoint resolution status.", relation_id)
    evidence_ids = {item.get("evidence_id") for item in registries["evidence_registry"]}
    for evidence in registries["evidence_registry"]:
        if not evidence.get("provenance") or ("confidence" in evidence and not evidence.get("confidence_contract")):
            error("RUO-U1-012", "evidence", "Evidence requires provenance and a confidence contract when confidence is present.", str(evidence.get("evidence_id", "")))
    for registry in ("payloads", "states", "relations", "constraints"):
        for entity in registries[registry]:
            missing = set(entity.get("evidence_refs", entity.get("provenance_refs", []))) - evidence_ids
            if missing: error("RUO-U1-012", "evidence", "Unknown evidence reference.", *map(str, missing))
    dependencies: dict[str, set[str]] = {}
    cycle_policy = value.get("dependency_cycle_policy")
    for edge in value.get("dependency_graph", []): dependencies.setdefault(str(edge.get("source_id")), set()).add(str(edge.get("target_id")))
    if _cycle(dependencies) and not cycle_policy:
        error("RUO-U1-013", "dependency", "Dependency cycle requires a registered evaluation policy.")
    namespaces = {item.get("namespace"): item for item in value.get("extension_registry", [])}
    for entity in [value, *[item for items in registries.values() for item in items]]:
        for namespace, extension in entity.get("extensions", {}).items():
            contract = namespaces.get(namespace)
            if contract is None and isinstance(extension, dict) and extension.get("critical"):
                error("RUO-U1-019", "extension", "Unknown critical extension.", profile=str(namespace))
            if namespace.startswith("ruo:"):
                error("RUO-U1-019", "extension", "Extensions cannot claim core authority.", profile=str(namespace))
    if value.get("lifecycle_state") not in LIFECYCLE: error("RUO-U1-015", "lifecycle", "Invalid Object lifecycle state.", object_id)
    return sorted(found, key=lambda x: (x["code"], x["stage"], x["affected_ids"], x["message"]))


def dependency_closure(value: dict[str, Any], changed: Iterable[str], *, reverse: bool = True) -> list[str]:
    edges: dict[str, set[str]] = {}
    for edge in value.get("dependency_graph", []):
        source, target = str(edge["source_id"]), str(edge["target_id"])
        key, child = (target, source) if reverse else (source, target)
        edges.setdefault(key, set()).add(child)
    closure = set(map(str, changed)); pending = list(closure)
    while pending:
        for child in sorted(edges.get(pending.pop(), set())):
            if child not in closure: closure.add(child); pending.append(child)
    return sorted(closure)


def generate_execution_projection(value: dict[str, Any], selected: Iterable[str] | None = None) -> dict[str, Any]:
    eligible = sorted(item["entity_id"] for item in value.get("units", []) if item.get("lifecycle_state") in {"active", "reactivated"})
    selected_ids = sorted(set(selected or eligible) & set(eligible))
    payload_ids = sorted(item["payload_id"] for item in value.get("payloads", []) if item.get("owner_id") in selected_ids or item.get("owner_id") == value["object_identity"]["entity_id"])
    projection_id = "ruo:projection:" + hashlib.sha256(canonicalize([value["object_identity"]["entity_id"], value["current_revision"], selected_ids]).encode()).hexdigest()[:24]
    return {"projection_id": projection_id, "source_object_id": value["object_identity"]["entity_id"], "source_revision": value["current_revision"], "profile": "ruo.execution/1", "selected_units": selected_ids, "selected_payloads": payload_ids, "excluded_entities": sorted(set(eligible) - set(selected_ids)), "state_snapshot_digest": canonical_digest(value.get("states", [])), "dependency_closure": dependency_closure(value, selected_ids, reverse=False), "relation_subset": sorted(r["relation_id"] for r in value.get("relations", []) if r.get("source_id") in selected_ids and r.get("target_id") in selected_ids), "tensor_index_table": [{"index": i, "entity_id": entity_id} for i, entity_id in enumerate(selected_ids)], "ordering": "stable_identity", "mutates_object": False}


def projection_is_current(value: dict[str, Any], projection: dict[str, Any]) -> bool:
    return projection.get("source_object_id") == value.get("object_identity", {}).get("entity_id") and projection.get("source_revision") == value.get("current_revision") and projection.get("state_snapshot_digest") == canonical_digest(value.get("states", []))


def query_object(value: dict[str, Any], query: str, argument: str | None = None) -> Any:
    registries = [value.get(name, []) for name in ("units", "payloads", "states", "relations", "constraints", "evidence_registry", "projection_descriptors")]
    all_entities = [value.get("object_identity", {})] + [item for registry in registries for item in registry]
    id_keys = ("entity_id", "payload_id", "state_id", "relation_id", "constraint_id", "evidence_id", "projection_id")
    if query == "entity_by_id": return next((item for item in all_entities if argument in [item.get(k) for k in id_keys]), None)
    if query == "owner":
        item = query_object(value, "entity_by_id", argument); return item.get("owner_object_id", item.get("owner_id")) if item else None
    if query == "children": return sorted(next((u.get("children", []) for u in value.get("units", []) if u.get("entity_id") == argument), []))
    if query == "payloads_by_owner": return sorted((p for p in value.get("payloads", []) if p.get("owner_id") == argument), key=lambda p: p["payload_id"])
    if query == "supporting_evidence": return sorted((e for e in value.get("evidence_registry", []) if argument in e.get("supports", [])), key=lambda e: e["evidence_id"])
    if query == "execution_eligible_units": return generate_execution_projection(value)["selected_units"]
    if query == "knowledge_status": return value.get("partial_loading", {}).get("entity_status", {}).get(argument, "loaded" if argument in {next((item.get(k) for k in id_keys if item.get(k)), None) for item in all_entities} else "absent")
    if query == "extensions": return sorted((item for item in value.get("extension_registry", []) if argument is None or item.get("namespace") == argument), key=lambda x: x["namespace"])
    if query == "invalidation_closure": return dependency_closure(value, [argument] if argument else [])
    raise ValueError(f"unknown universal query: {query}")


class ObjectTransaction:
    def __init__(self, value: dict[str, Any]): self.value = value
    def commit(self, proposal: dict[str, Any], *, source_revision: str, transaction_id: str) -> dict[str, Any]:
        before = copy.deepcopy(self.value); before_digest = canonical_digest(before)
        if source_revision != self.value.get("current_revision") or not transaction_id.startswith("ruo:transaction:"):
            return {"committed": False, "diagnostic": "RUO-U1-016", "partial_commit_count": 0, "canonical_state_digest": before_digest}
        candidate = copy.deepcopy(self.value)
        updates = proposal.get("state_updates", {})
        states = {state["state_id"]: state for state in candidate.get("states", [])}
        if any(state_id not in states for state_id in updates):
            return {"committed": False, "diagnostic": "RUO-U1-017", "partial_commit_count": 0, "canonical_state_digest": before_digest}
        new_revision = f"ruo:revision:{int(str(source_revision).rsplit(':', 1)[-1]) + 1}"
        for state_id, state_value in updates.items(): states[state_id]["value"] = copy.deepcopy(state_value); states[state_id]["last_modified_revision"] = new_revision
        candidate["current_revision"] = new_revision
        candidate.setdefault("revisions", []).append({"revision_id": new_revision, "transaction_id": transaction_id, "source_revision": source_revision, "changed_entities": sorted(updates)})
        diagnostics = validate_object(candidate)
        if diagnostics: return {"committed": False, "diagnostic": diagnostics[0]["code"], "partial_commit_count": 0, "canonical_state_digest": before_digest}
        self.value.clear(); self.value.update(candidate)
        return {"committed": True, "revision_id": new_revision, "partial_commit_count": 0, "invalidation_closure": dependency_closure(candidate, updates)}
