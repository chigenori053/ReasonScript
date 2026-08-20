"""EntityTable / EntityEnvironment -> Reason IR `metadata.reason_entities`
and ExecutionPlan `entity_plan` (RS-RE-FSM-001 §3.6, §3.7, ADR-103).

`entities` and `relations` arrays are normalized to canonical_id ascending
order (matching `toolchain.reasonunit_object.model.canonicalize`'s
registry-array sort convention). `instructions` preserve declaration/
execution order verbatim -- that ordering is semantically meaningful
(design §3.6) and must not be re-sorted.
"""

from __future__ import annotations

from typing import Any

from .kinds import EntityKind, TransitionPolicy
from .model import implicit_containment_relations
from .registry import EntityTable
from .slot import EntityEnvironment

REASON_ENTITY_SCHEMA_VERSION = "reasonscript-reason-entity/0.1"
ENTITY_PLAN_SCHEMA_VERSION = "reasonscript-reason-entity-plan/0.1"


def _entity_payload(
    table: EntityTable, canonical_id: str, *, environment: EntityEnvironment | None = None
) -> dict[str, Any] | None:
    record = table.get(canonical_id)
    if record is None:
        return None
    if environment is not None:
        slot = environment.slot(canonical_id)
        transition_policy = slot.transition_policy.value
        revision = slot.revision
    else:
        transition_policy = (
            TransitionPolicy.INITIALIZE_ONLY
            if record.kind is EntityKind.DERIVE
            else TransitionPolicy.EXPLICIT
        ).value
        revision = 0
    return {
        "canonical_id": record.canonical_id,
        "kind": record.kind.value,
        "identifier": record.identifier,
        "owner_id": record.owner_id,
        "value_type": record.value_type,
        "declared_type": record.declared_type,
        "transition_policy": transition_policy,
        "persistence_policy": record.persistence_policy.value,
        "lifecycle": record.lifecycle,
        "revision": revision,
        "members": list(table.members_of(canonical_id)),
        "dependencies": list(record.dependencies),
    }


def lower_entities(
    table: EntityTable, *, environment: EntityEnvironment | None = None
) -> dict[str, Any]:
    """Build the `metadata.reason_entities` Reason IR payload for `table`.

    Pass `environment` to populate `transition_policy`/`revision` from the
    live RU Slot state; without it, both are the Phase E0 static defaults.
    """
    entities = [
        payload
        for canonical_id in table.declaration_order()
        if (payload := _entity_payload(table, canonical_id, environment=environment)) is not None
    ]
    entities.sort(key=lambda entity: entity["canonical_id"])
    relations = [
        relation.to_dict() for relation in implicit_containment_relations(table)
    ]
    relations.sort(key=lambda relation: relation["relation_id"])
    return {
        "schema_version": REASON_ENTITY_SCHEMA_VERSION,
        "entities": entities,
        "relations": relations,
    }


def lower_environment(environment: EntityEnvironment) -> dict[str, Any]:
    """Build the `metadata.reason_entities` payload including the
    deterministic `instructions` trail recorded by `EntityEnvironment`."""
    payload = lower_entities(environment.table, environment=environment)
    payload["instructions"] = list(environment.instructions)
    return payload


def entity_plan_for(environment: EntityEnvironment) -> dict[str, Any]:
    """Build the ExecutionPlan `entity_plan` fragment for `environment`."""
    declaration_order = list(environment.table.declaration_order())
    transition_sequence: list[dict[str, Any]] = []
    boundaries: dict[str, list[str]] = {}
    for index, instruction in enumerate(environment.instructions, start=1):
        if instruction["op"] != "CommitEntityTransition":
            continue
        entity = instruction["entity"]
        site = instruction["site"]
        transition_sequence.append({
            "order": index,
            "entity": entity,
            "site": site,
            "atomic_boundary": site,
            "revision_delta": instruction["revision_delta"],
        })
        boundary_entities = boundaries.setdefault(site, [])
        if entity not in boundary_entities:
            boundary_entities.append(entity)
    atomic_boundaries = [
        {"boundary_id": site, "entities": entities, "rollback_on_failure": True}
        for site, entities in boundaries.items()
    ]
    derived_evaluation = [
        {
            "entity": canonical_id,
            "strategy": "on_read",
            "dependencies": list(record.dependencies),
        }
        for canonical_id in declaration_order
        if (record := environment.table.get(canonical_id)) is not None
        and record.kind is EntityKind.DERIVE
    ]
    return {
        "schema_version": ENTITY_PLAN_SCHEMA_VERSION,
        "declaration_order": declaration_order,
        "transition_sequence": transition_sequence,
        "atomic_boundaries": atomic_boundaries,
        "derived_evaluation": derived_evaluation,
        "evidence_collection_points": [],
        "projection_boundaries": [],
    }
