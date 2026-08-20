"""EntityRelation and RUO-U1 compatibility projection (RS-RE-FSM-001 §4.6,
§11, ADR-101).

`registry.EntityRecord` already plays the role the design calls
`ReasonEntityDecl` (§3.2) -- it was built first, in Phase F2, before this
module existed, and splitting it out now would be a pure rename with no
behavioral change to already-tested code. This module covers what F2 did
not yet build: a typed relation representation, and the projection of an
:class:`~frontend.entity.registry.EntityTable` into an RUO-U1-shaped
document that `toolchain.reasonunit_object.model.validate_object` accepts
(the Phase E0 acceptance criterion).

RUO nesting (an Entity of kind RUO containing further RUO members) is
intentionally out of scope for this projection: RUO-U1 models exactly one
Object per document, and Reason Entity Object -> Object nesting semantics
are deferred (design doc §10 Q4/Q5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from toolchain.reasonunit_object.model import CORE_PREFIXES

from .kinds import EntityKind
from .registry import EntityTable


@dataclass(frozen=True)
class EntityRelation:
    relation_id: str
    source: str
    target: str
    relation_type: str
    relation_class: str = "internal"
    validity: str = "declared"
    evidence_refs: tuple[str, ...] = ()
    provenance_ref: str | None = None
    revision: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "source": self.source,
            "target": self.target,
            "relation_type": self.relation_type,
            "relation_class": self.relation_class,
            "validity": self.validity,
            "evidence_refs": list(self.evidence_refs),
            "provenance_ref": self.provenance_ref,
            "revision": self.revision,
        }


def implicit_containment_relations(table: EntityTable) -> tuple[EntityRelation, ...]:
    """PartOf relations derived from RUS/RUO membership (design §10.1,
    §11). v0.1 scope: only membership-derived relations are produced;
    explicit Relation declaration syntax is deferred (design §10 Q6)."""
    relations: list[EntityRelation] = []
    for owner_id in table.declaration_order():
        record = table.get(owner_id)
        if record is None or record.kind not in (EntityKind.RUS, EntityKind.RUO):
            continue
        for member_id in table.members_of(owner_id):
            relations.append(
                EntityRelation(
                    relation_id=f"{CORE_PREFIXES['relation']}{owner_id.split(':', 2)[-1]}.{member_id.rsplit('.', 1)[-1]}.member",
                    source=owner_id,
                    target=member_id,
                    relation_type="PartOf",
                    relation_class="internal",
                )
            )
    return tuple(relations)


_ENTITY_KIND_TO_U1_UNIT_KIND = {
    EntityKind.RU: "atomic_reasonunit",
    EntityKind.DERIVE: "atomic_reasonunit",
    EntityKind.RUS: "composite_reasonunit",
}


def project_to_ruo_u1(
    table: EntityTable,
    *,
    object_identifier: str,
    lifecycle_state: str = "active",
) -> dict[str, Any]:
    """Project every RU/RUS/DERIVE Entity in `table` as `units` owned by one
    synthetic RUO-U1 Object, so `validate_object()` can certify structural
    compatibility (design §3.2 ADR-101, Phase E0 acceptance criterion).

    Entities of kind RUO are rejected: an inner RUO would need its own
    nested `object_identity`, which this flat, single-Object shape does
    not model (see module docstring).
    """
    object_id = f"{CORE_PREFIXES['object']}{object_identifier}"
    base = {
        "schema_version": "1.0",
        "created_revision": "ruo:revision:0",
        "last_modified_revision": "ruo:revision:0",
        "lifecycle_state": lifecycle_state,
        "extensions": {},
    }
    units: list[dict[str, Any]] = []
    root_units: list[str] = []
    for canonical_id in table.declaration_order():
        record = table.get(canonical_id)
        assert record is not None
        if record.kind is EntityKind.RUO:
            raise ValueError(
                f"RE-RUO-002 nested RUO cannot be projected into a single RUO-U1 object: {canonical_id}"
            )
        units.append({
            **base,
            "entity_id": canonical_id,
            "entity_kind": _ENTITY_KIND_TO_U1_UNIT_KIND[record.kind],
            "owner_object_id": object_id,
            "children": list(table.members_of(canonical_id)),
        })
        if record.owner_id is None:
            root_units.append(canonical_id)
    relations = [
        {
            **base,
            "relation_id": relation.relation_id,
            "entity_kind": "relation",
            "relation_type": f"ruo.relation:{relation.relation_type.lower()}/1",
            "relation_class": relation.relation_class,
            "source_id": relation.source,
            "target_id": relation.target,
            "directionality": "directed",
            "multiplicity": "one-to-many",
            "endpoint_resolution": "resolved",
            "evidence_refs": list(relation.evidence_refs),
        }
        for relation in implicit_containment_relations(table)
    ]
    return {
        "model_version": "reasonscript-reasonunit-object/1.0",
        "object_identity": {
            **base,
            "entity_id": object_id,
            "entity_kind": "reasonunit_object",
        },
        "object_type": "ruo.object:reason-entity-projection",
        "lifecycle_state": lifecycle_state,
        "current_revision": "ruo:revision:0",
        "revisions": [{
            "revision_id": "ruo:revision:0",
            "transaction_id": "ruo:transaction:initial",
            "source_revision": None,
            "changed_entities": [],
        }],
        "root_units": root_units,
        "units": units,
        "payloads": [],
        "states": [],
        "relations": relations,
        "constraints": [],
        "evidence_registry": [],
        "dependency_graph": [],
        "extension_registry": [],
        "projection_descriptors": [],
        "partial_loading": {
            "is_partial": False,
            "entity_status": {},
            "unattached_retained_entities": [],
        },
        "extensions": {},
    }
