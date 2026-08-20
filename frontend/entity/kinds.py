"""Reason Entity kind and policy enums (RS-RE-FSM-001 §3.2, §4)."""

from __future__ import annotations

from enum import Enum


class EntityKind(str, Enum):
    RU = "AtomicReasonUnit"
    RUS = "ReasonUnitStructure"
    RUO = "ReasonUnitObject"
    DERIVE = "DerivedReasonUnit"


class TransitionPolicy(str, Enum):
    INITIALIZE_ONLY = "InitializeOnly"
    EXPLICIT = "Explicit"


class PersistencePolicy(str, Enum):
    SESSION = "Session"
    PERSISTENT = "Persistent"


# RUO-U1 lifecycle vocabulary (toolchain/reasonunit_object/model.py
# LIFECYCLE), reused verbatim so a Reason Entity's lifecycle field is
# structurally compatible with an RUO-U1 projection (ADR-101).
LIFECYCLE_STATES = frozenset({
    "proposed", "active", "suspended", "reactivated", "replaced",
    "pruned", "retired", "converged", "terminated", "deleted",
})
