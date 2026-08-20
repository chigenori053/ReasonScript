"""`RE-*` diagnostic factories (RS-RE-FSM-001 §14).

Thin convenience wrappers over `toolchain.diagnostics.diagnostic_from_parts`
-- category resolution ("RE" -> "Semantic") is already wired there (Phase
F2-4), so this module only supplies the code/message/metadata shape for
each Reason Entity diagnostic kind. Returns `toolchain.diagnostics.Diagnostic`
so these compose directly into the existing `reasonscript-diagnostics/1.0`
pipeline once the Surface layer (Phase E1) raises them from real source
positions.
"""

from __future__ import annotations

from toolchain.diagnostics import Diagnostic, diagnostic_from_parts


def duplicate_declaration(
    canonical_id: str, *, file: str, line: int | None = None, column: int | None = None
) -> Diagnostic:
    return diagnostic_from_parts(
        code="RE-DECL-001",
        message=f"Reason Entity already declared in this scope: {canonical_id}",
        file=file, line=line, column=column,
        metadata={"canonical_id": canonical_id},
    )


def initializer_type_mismatch(
    canonical_id: str, *, expected: str, received: str,
    file: str, line: int | None = None, column: int | None = None,
) -> Diagnostic:
    return diagnostic_from_parts(
        code="RE-TYPE-001",
        message=(
            f"Initializer type mismatch for {canonical_id}: "
            f"expected {expected}, received {received}"
        ),
        file=file, line=line, column=column,
        metadata={"canonical_id": canonical_id, "expected_type": expected, "received_type": received},
    )


def transition_type_mismatch(
    canonical_id: str, *, expected: str, received: str,
    file: str, line: int | None = None, column: int | None = None,
) -> Diagnostic:
    return diagnostic_from_parts(
        code="RE-TYPE-002",
        message=(
            f"Transition value type mismatch for {canonical_id}: "
            f"expected {expected}, received {received}"
        ),
        file=file, line=line, column=column,
        metadata={"canonical_id": canonical_id, "expected_type": expected, "received_type": received},
    )


def uninitialized_transition(
    canonical_id: str, *, file: str, line: int | None = None, column: int | None = None
) -> Diagnostic:
    return diagnostic_from_parts(
        code="RE-STATE-001",
        message=f"Cannot transition an uninitialized Reason Entity: {canonical_id}",
        file=file, line=line, column=column,
        metadata={"canonical_id": canonical_id},
    )


def derived_entity_direct_transition(
    canonical_id: str, *, file: str, line: int | None = None, column: int | None = None
) -> Diagnostic:
    return diagnostic_from_parts(
        code="RE-STATE-002",
        message=f"Cannot transition a Derived Reason Entity directly: {canonical_id}",
        file=file, line=line, column=column,
        metadata={"canonical_id": canonical_id},
    )


def entity_reassignment_via_equals(
    canonical_id: str, *, file: str, line: int | None = None, column: int | None = None
) -> Diagnostic:
    return diagnostic_from_parts(
        code="RE-STATE-003",
        message=f"Reason Entity `{canonical_id}` must be updated with `<-`, not `=`",
        file=file, line=line, column=column,
        metadata={"canonical_id": canonical_id},
    )


def canonical_id_collision(
    canonical_id: str, *, file: str, line: int | None = None, column: int | None = None
) -> Diagnostic:
    return diagnostic_from_parts(
        code="RE-ID-001",
        message=f"Canonical Entity ID collision: {canonical_id}",
        file=file, line=line, column=column,
        metadata={"canonical_id": canonical_id},
    )


def invalid_ownership_reference(
    canonical_id: str, owner_id: str, *, file: str, line: int | None = None, column: int | None = None
) -> Diagnostic:
    return diagnostic_from_parts(
        code="RE-OWNER-001",
        message=f"Invalid ownership boundary reference: {canonical_id} -> {owner_id}",
        file=file, line=line, column=column,
        metadata={"canonical_id": canonical_id, "owner_id": owner_id},
    )


def containment_cycle(
    canonical_id: str, *, file: str, line: int | None = None, column: int | None = None
) -> Diagnostic:
    return diagnostic_from_parts(
        code="RE-RUS-001",
        message=f"ReasonUnit Structure containment cycle detected at: {canonical_id}",
        file=file, line=line, column=column,
        metadata={"canonical_id": canonical_id},
    )


def implicit_rus_to_ruo_promotion(
    canonical_id: str, *, file: str, line: int | None = None, column: int | None = None
) -> Diagnostic:
    return diagnostic_from_parts(
        code="RE-RUO-001",
        message=f"Implicit RUS -> RUO promotion is not allowed: {canonical_id}",
        file=file, line=line, column=column,
        metadata={"canonical_id": canonical_id},
    )


def unresolved_relation_endpoint(
    relation_id: str, endpoint: str, *, file: str, line: int | None = None, column: int | None = None
) -> Diagnostic:
    return diagnostic_from_parts(
        code="RE-REL-001",
        message=f"Relation `{relation_id}` references an unknown Entity: {endpoint}",
        file=file, line=line, column=column,
        metadata={"relation_id": relation_id, "endpoint": endpoint},
    )


def non_deterministic_lowering(
    construct: str, *, file: str, line: int | None = None, column: int | None = None
) -> Diagnostic:
    return diagnostic_from_parts(
        code="RE-LOWER-001",
        message=f"Construct cannot be deterministically lowered: {construct}",
        file=file, line=line, column=column,
        metadata={"construct": construct},
    )


def derive_dependency_cycle(
    canonical_id: str, *, file: str, line: int | None = None, column: int | None = None
) -> Diagnostic:
    return diagnostic_from_parts(
        code="RE-DERIVE-001",
        message=f"Circular Derived Entity dependency at: {canonical_id}",
        file=file, line=line, column=column,
        metadata={"canonical_id": canonical_id},
    )
