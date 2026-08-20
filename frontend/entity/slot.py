"""RU Slot runtime and propose-validate-commit state transitions
(RS-RE-FSM-001 §9.1, §9.2, §3.8, §3.9, §3.10, §17).

Standalone and Surface-syntax independent (Phase E0): driven entirely
through :class:`EntityEnvironment`'s Python API, not a parsed AST. The
Surface Runtime wiring (Phase E1) drives this same API from
`<-` / `derive:` evaluation instead of calling it directly as done here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .kinds import EntityKind, TransitionPolicy
from .registry import EntityRecord, EntityTable

# Best-effort runtime type check for declared value_type labels. An unknown
# label is not an error -- it is simply not checked (Surface types beyond
# this small set are the Surface layer's responsibility, not the Entity
# runtime's).
_LABEL_PYTHON_TYPES: dict[str, tuple[type, ...]] = {
    "Int": (int,),
    "Float": (int, float),
    "Bool": (bool,),
    "String": (str,),
}


class EntitySlotError(ValueError):
    """Raised on RE-STATE-001 / RE-STATE-002 / RE-TYPE-001 / RE-TYPE-002 violations."""


@dataclass
class RUSlot:
    slot_id: int
    canonical_entity_id: str
    kind: EntityKind
    value_type: Any
    current_value: Any
    transition_policy: TransitionPolicy
    revision: int = 0
    provenance_ref: str | None = None
    materialized: bool = False


@dataclass
class EntityEnvironment:
    """RU Slot table + deterministic instruction trace for one compilation
    unit's Entity declarations and transitions."""

    table: EntityTable = field(default_factory=EntityTable)
    _slots: dict[str, RUSlot] = field(default_factory=dict)
    _derive_evaluators: dict[str, Callable[[], Any]] = field(default_factory=dict)
    _derive_cache: dict[str, tuple[tuple[int, ...], Any]] = field(default_factory=dict)
    _next_slot_id: int = 1
    instructions: list[dict[str, Any]] = field(default_factory=list)

    def declare(
        self,
        record: EntityRecord,
        *,
        initial_value: Any = None,
        derive_evaluator: Callable[[], Any] | None = None,
    ) -> RUSlot:
        self.table.declare(record)
        transition_policy = (
            TransitionPolicy.INITIALIZE_ONLY
            if record.kind is EntityKind.DERIVE
            else TransitionPolicy.EXPLICIT
        )
        slot = RUSlot(
            slot_id=self._next_slot_id,
            canonical_entity_id=record.canonical_id,
            kind=record.kind,
            value_type=record.value_type,
            current_value=initial_value,
            transition_policy=transition_policy,
        )
        self._next_slot_id += 1
        self._slots[record.canonical_id] = slot
        self.instructions.append({
            "op": "DeclareEntity",
            "entity": record.canonical_id,
            "kind": record.kind.value,
            "type": record.value_type,
        })
        if record.kind is EntityKind.DERIVE:
            if derive_evaluator is None:
                raise EntitySlotError(
                    f"RE-DERIVE-002 derived entity requires an evaluator: {record.canonical_id}"
                )
            self._derive_evaluators[record.canonical_id] = derive_evaluator
            self.instructions.append({
                "op": "DeclareDerivedEntity",
                "entity": record.canonical_id,
                "dependencies": list(record.dependencies),
                "strategy": "on_read",
            })
        elif initial_value is not None:
            self.instructions.append({
                "op": "InitializeEntityState",
                "entity": record.canonical_id,
                "value": initial_value,
                "revision": 0,
            })
        return slot

    def declare_structure(self, record: EntityRecord) -> RUSlot:
        self.table.declare(record)
        slot = RUSlot(
            slot_id=self._next_slot_id,
            canonical_entity_id=record.canonical_id,
            kind=record.kind,
            value_type=record.value_type,
            current_value=None,
            transition_policy=TransitionPolicy.EXPLICIT,
        )
        self._next_slot_id += 1
        self._slots[record.canonical_id] = slot
        self.instructions.append({
            "op": "CreateStructure" if record.kind is EntityKind.RUS else "CreateObject",
            "entity": record.canonical_id,
            "kind": record.kind.value,
        })
        return slot

    def read(self, canonical_id: str) -> Any:
        slot = self._require_slot(canonical_id)
        if slot.kind is not EntityKind.DERIVE:
            return slot.current_value
        record = self.table.get(canonical_id)
        assert record is not None
        dependency_revisions = tuple(
            self._require_slot(dependency).revision for dependency in record.dependencies
        )
        cached = self._derive_cache.get(canonical_id)
        if cached is not None and cached[0] == dependency_revisions:
            return cached[1]
        self.instructions.append({"op": "ReadEntityState", "entity": canonical_id})
        value = self._derive_evaluators[canonical_id]()
        self.instructions.append({
            "op": "EvaluateDerivedEntity",
            "entity": canonical_id,
            "dependency_revisions": list(dependency_revisions),
            "value": value,
        })
        slot.current_value = value
        self._derive_cache[canonical_id] = (dependency_revisions, value)
        return value

    def propose_transition(
        self, canonical_id: str, proposed_value: Any, *, site: str
    ) -> RUSlot:
        """Propose -> validate -> commit a state transition (§17 atomicity):
        on any failure, `current_value` and `revision` are left unchanged."""
        slot = self._require_slot(canonical_id)
        record = self.table.get(canonical_id)
        assert record is not None
        if slot.kind is EntityKind.DERIVE:
            raise EntitySlotError(
                f"RE-STATE-002 cannot transition a derived entity: {canonical_id}"
            )
        self.instructions.append({
            "op": "ProposeEntityTransition",
            "entity": canonical_id,
            "site": site,
            "previous": slot.current_value,
            "proposed": proposed_value,
        })
        allowed = _LABEL_PYTHON_TYPES.get(record.value_type)
        if allowed is not None and not isinstance(proposed_value, allowed):
            raise EntitySlotError(
                f"RE-TYPE-002 transition value type mismatch for {canonical_id}: "
                f"expected {record.value_type}, received {type(proposed_value).__name__}"
            )
        self.instructions.append({
            "op": "ValidateEntityTransition",
            "entity": canonical_id,
            "site": site,
            "expected_type": record.value_type,
        })
        slot.current_value = proposed_value
        slot.revision += 1
        self.instructions.append({
            "op": "CommitEntityTransition",
            "entity": canonical_id,
            "site": site,
            "revision_delta": 1,
        })
        return slot

    def materialize(self, canonical_id: str) -> RUSlot:
        """Promote a lightweight RU Slot to a fully materialized Entity
        (§9.2). Idempotent and semantics-preserving (§9.3): does not touch
        canonical_id, current_value, revision, or instruction history."""
        slot = self._require_slot(canonical_id)
        slot.materialized = True
        return slot

    def slot(self, canonical_id: str) -> RUSlot:
        return self._require_slot(canonical_id)

    def _require_slot(self, canonical_id: str) -> RUSlot:
        slot = self._slots.get(canonical_id)
        if slot is None:
            raise EntitySlotError(f"RE-STATE-001 uninitialized entity: {canonical_id}")
        return slot
