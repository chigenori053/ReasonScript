"""Internal Reason Entity model (RS-RE-FSM-001).

This package is Surface-syntax independent: it has no dependency on the
Parser or on `ru:`/`rus:`/`ruo:`/`derive:` surface constructs, which are
introduced in a later Phase (E1). It exists so the Canonical Entity ID
scheme and the Entity declaration/relation registry can be built and
tested standalone first (Phase F2/E0), per RS-RE-FSM-001 ADR-101/102/103.
"""

from .identity import CanonicalIdError, canonical_entity_id, parse_canonical_entity_id
from .kinds import EntityKind, PersistencePolicy, TransitionPolicy
from .registry import EntityRecord, EntityRegistryError, EntityTable

__all__ = [
    "CanonicalIdError",
    "canonical_entity_id",
    "parse_canonical_entity_id",
    "EntityKind",
    "PersistencePolicy",
    "TransitionPolicy",
    "EntityRecord",
    "EntityRegistryError",
    "EntityTable",
]
