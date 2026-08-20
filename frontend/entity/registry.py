"""EntityTable: declaration registry, ownership/dependency graphs, cycle and
collision detection (RS-RE-FSM-001 §4.1, §7.3, §14: RE-ID-001, RE-RUS-001,
RE-DERIVE-001, RE-REL-001).

Standalone and Surface-syntax independent (Phase F2/E0): entries are added
through :meth:`EntityTable.declare`, not derived from a parsed AST.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .kinds import EntityKind


class EntityRegistryError(ValueError):
    """Raised on RE-ID-001 / RE-RUS-001 / RE-DERIVE-001 / RE-REL-001 violations."""


@dataclass(frozen=True)
class EntityRecord:
    canonical_id: str
    kind: EntityKind
    identifier: str
    owner_id: str | None
    dependencies: tuple[str, ...] = ()
    value_type: Any = None


@dataclass
class EntityTable:
    """Declaration registry for one compilation unit (module or fixture)."""

    _entities: dict[str, EntityRecord] = field(default_factory=dict)
    # owner_id -> ordered member canonical_ids (RUS/RUO containment)
    _members: dict[str, list[str]] = field(default_factory=dict)
    # relation_id -> (source, target)
    _relations: dict[str, tuple[str, str]] = field(default_factory=dict)

    def declare(self, record: EntityRecord) -> None:
        if record.canonical_id in self._entities:
            raise EntityRegistryError(
                f"RE-ID-001 canonical id already registered: {record.canonical_id}"
            )
        if record.owner_id is not None and record.owner_id not in self._entities:
            raise EntityRegistryError(
                f"RE-OWNER-001 unknown owner: {record.owner_id}"
            )
        if record.kind in (EntityKind.RUS, EntityKind.RUO) and record.owner_id is not None:
            owner = self._entities[record.owner_id]
            if owner.kind not in (EntityKind.RUS, EntityKind.RUO):
                raise EntityRegistryError(
                    f"RE-OWNER-001 owner is not a structure/object: {record.owner_id}"
                )
            if self._creates_containment_cycle(record.owner_id, record.canonical_id):
                raise EntityRegistryError(
                    f"RE-RUS-001 containment cycle detected: {record.canonical_id}"
                )
        if record.kind is EntityKind.DERIVE:
            for dependency in record.dependencies:
                if dependency not in self._entities and dependency != record.canonical_id:
                    raise EntityRegistryError(
                        f"RE-REL-001 unknown derive dependency: {dependency}"
                    )
            if self._creates_dependency_cycle(record.canonical_id, record.dependencies):
                raise EntityRegistryError(
                    f"RE-DERIVE-001 circular derive dependency: {record.canonical_id}"
                )
        self._entities[record.canonical_id] = record
        if record.owner_id is not None:
            self._members.setdefault(record.owner_id, []).append(record.canonical_id)

    def declare_relation(
        self, relation_id: str, source: str, target: str
    ) -> None:
        if relation_id in self._relations:
            raise EntityRegistryError(
                f"RE-ID-001 relation id already registered: {relation_id}"
            )
        if source not in self._entities:
            raise EntityRegistryError(f"RE-REL-001 unknown relation source: {source}")
        if target not in self._entities:
            raise EntityRegistryError(f"RE-REL-001 unknown relation target: {target}")
        self._relations[relation_id] = (source, target)

    def get(self, canonical_id: str) -> EntityRecord | None:
        return self._entities.get(canonical_id)

    def __contains__(self, canonical_id: str) -> bool:
        return canonical_id in self._entities

    def members_of(self, owner_id: str) -> tuple[str, ...]:
        return tuple(self._members.get(owner_id, ()))

    def declaration_order(self) -> tuple[str, ...]:
        """Insertion order -- the deterministic order used for IR/plan emission."""
        return tuple(self._entities)

    def relations(self) -> tuple[tuple[str, str, str], ...]:
        return tuple(
            (relation_id, source, target)
            for relation_id, (source, target) in self._relations.items()
        )

    def _creates_containment_cycle(self, owner_id: str, new_member_id: str) -> bool:
        # A cycle exists if new_member_id is already an ancestor of owner_id
        # through the containment (owner -> members) chain.
        visiting = {owner_id}
        frontier = [owner_id]
        while frontier:
            current = frontier.pop()
            if current == new_member_id:
                return True
            for member in self._members.get(current, ()):
                if member not in visiting:
                    visiting.add(member)
                    frontier.append(member)
        return False

    def _creates_dependency_cycle(
        self, derived_id: str, dependencies: tuple[str, ...]
    ) -> bool:
        # `declare` only accepts dependencies that already exist (or the
        # entity's own id, for self-reference), so a multi-node cycle can
        # never actually reach this traversal in the current single-pass
        # registration model: the "back" edge of any A<->B cycle is always
        # rejected earlier as an unknown dependency. Self-reference is the
        # only reachable case today; the general traversal is kept correct
        # in case a future two-pass registration API allows forward
        # references.
        # Depth-first search over the derive-dependency edges, including the
        # not-yet-inserted `derived_id -> dependencies` edge under test.
        visiting: set[str] = set()
        visited: set[str] = set()

        def edges_of(node: str) -> tuple[str, ...]:
            if node == derived_id:
                return dependencies
            record = self._entities.get(node)
            return record.dependencies if record is not None else ()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for dependency in edges_of(node):
                if visit(dependency):
                    return True
            visiting.remove(node)
            visited.add(node)
            return False

        return visit(derived_id)
