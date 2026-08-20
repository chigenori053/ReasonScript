"""Phase E0 — Internal Reason Entity Model acceptance tests
(RS-RE-FSM-001 §13 Phase E0).

Builds the RS-RE-FSM-001 Appendix A example (module GreetingLearning) using
only the `frontend.entity` internal API -- no Surface Parser, no `ru:`/
`rus:`/`derive:`/`<-` syntax. Demonstrates that RU, RUS, and Derived RU can
all be generated and validated standalone, per the Phase E0 acceptance
criterion. (RUO is exercised separately below: it is not part of Appendix
A, and E0's RUO-U1 projection intentionally does not support nesting an
RUO inside another RUO-U1 object -- see frontend/entity/model.py.)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conformance.schema_validator import SchemaValidator
from frontend.entity import (
    EntityEnvironment,
    EntityKind,
    EntityRecord,
    EntityRegistryError,
    EntityRelation,
    EntitySlotError,
    EntityTable,
    canonical_entity_id,
    entity_plan_for,
    implicit_containment_relations,
    lower_environment,
    parse_canonical_entity_id,
    project_to_ruo_u1,
)
from toolchain.reasonunit_object.model import validate_object

SCHEMAS = SchemaValidator(Path(__file__).resolve().parents[1] / "schemas")

RUS_MEMBERS = (
    "token_relation",
    "position_relation",
    "politeness_relation",
    "syntactic_relation",
    "context_relation",
)


def build_appendix_a_fixture() -> EntityEnvironment:
    """Assemble the Appendix A `module GreetingLearning` Entity graph
    directly through the internal API (no Surface syntax)."""
    module = "GreetingLearning"
    table = EntityTable()
    env = EntityEnvironment(table=table)

    learning_rate_id = canonical_entity_id(kind=EntityKind.RU, module=module, identifier="learning_rate")
    env.declare(
        EntityRecord(
            canonical_id=learning_rate_id, kind=EntityKind.RU, identifier="learning_rate",
            owner_id=None, value_type="Float", declared_type="Float",
        ),
        initial_value=0.01,
    )

    current_step_id = canonical_entity_id(kind=EntityKind.RU, module=module, identifier="current_step")
    env.declare(
        EntityRecord(
            canonical_id=current_step_id, kind=EntityKind.RU, identifier="current_step",
            owner_id=None, value_type="Int", declared_type="Int",
        ),
        initial_value=0,
    )

    loss_id = canonical_entity_id(kind=EntityKind.RU, module=module, identifier="loss")
    env.declare(
        EntityRecord(
            canonical_id=loss_id, kind=EntityKind.RU, identifier="loss",
            owner_id=None, value_type="Tensor", declared_type="Tensor",
        ),
        initial_value=0.0,  # Tensor runtime wiring is Phase E1; a scalar
        # surrogate is enough to exercise Entity transition mechanics here.
    )

    relation_id = canonical_entity_id(kind=EntityKind.RUS, module=module, identifier="greeting_relation")
    env.declare_structure(
        EntityRecord(canonical_id=relation_id, kind=EntityKind.RUS, identifier="greeting_relation", owner_id=None)
    )
    for name in RUS_MEMBERS:
        member_id = canonical_entity_id(
            kind=EntityKind.RU, module=module, owner_path=("greeting_relation",), identifier=name
        )
        env.declare(
            EntityRecord(
                canonical_id=member_id, kind=EntityKind.RU, identifier=name,
                owner_id=relation_id, value_type="Float",
            ),
            initial_value=0.0,
        )

    training_active_id = canonical_entity_id(kind=EntityKind.DERIVE, module=module, identifier="training_active")
    env.declare(
        EntityRecord(
            canonical_id=training_active_id, kind=EntityKind.DERIVE, identifier="training_active",
            owner_id=None, dependencies=(current_step_id,),
        ),
        derive_evaluator=lambda: env.read(current_step_id) < 100,
    )

    # `calculation Train { while training_active { loss <- TrainStep(...); current_step <- current_step + 1 } }`
    # simulated for a small, deterministic number of iterations.
    for step in range(1, 4):
        assert env.read(training_active_id) is True
        env.propose_transition(loss_id, 1.0 / step, site=f"Train#{step}")
        env.propose_transition(current_step_id, step, site=f"Train#{step}")

    return env


@pytest.fixture()
def fixture_environment() -> EntityEnvironment:
    return build_appendix_a_fixture()


def test_all_entity_kinds_are_present_without_surface_syntax(fixture_environment: EntityEnvironment) -> None:
    kinds = {
        fixture_environment.table.get(canonical_id).kind  # type: ignore[union-attr]
        for canonical_id in fixture_environment.table.declaration_order()
    }
    assert kinds == {EntityKind.RU, EntityKind.RUS, EntityKind.DERIVE}


def test_rus_membership_matches_appendix_a() -> None:
    env = build_appendix_a_fixture()
    relation_id = canonical_entity_id(kind=EntityKind.RUS, module="GreetingLearning", identifier="greeting_relation")
    members = env.table.members_of(relation_id)
    assert [member.rsplit(".", 1)[-1] for member in members] == list(RUS_MEMBERS)


def test_derived_entity_reevaluates_on_each_read() -> None:
    env = build_appendix_a_fixture()
    current_step_id = canonical_entity_id(kind=EntityKind.RU, module="GreetingLearning", identifier="current_step")
    training_active_id = canonical_entity_id(kind=EntityKind.DERIVE, module="GreetingLearning", identifier="training_active")
    assert env.read(training_active_id) is True
    for _ in range(100):
        env.propose_transition(current_step_id, 100, site="ForceInactive")
    assert env.read(training_active_id) is False


def test_derived_entity_cannot_be_transitioned_directly() -> None:
    env = build_appendix_a_fixture()
    training_active_id = canonical_entity_id(kind=EntityKind.DERIVE, module="GreetingLearning", identifier="training_active")
    with pytest.raises(EntitySlotError, match="RE-STATE-002"):
        env.propose_transition(training_active_id, False, site="Illegal")


def test_transition_on_uninitialized_entity_is_rejected() -> None:
    env = EntityEnvironment()
    with pytest.raises(EntitySlotError, match="RE-STATE-001"):
        env.propose_transition("ruo:unit:ru:M.x", 1, site="S")


def test_transition_type_mismatch_leaves_state_and_revision_unchanged() -> None:
    # §17 atomicity: a failed transition must not partially update state.
    env = build_appendix_a_fixture()
    learning_rate_id = canonical_entity_id(kind=EntityKind.RU, module="GreetingLearning", identifier="learning_rate")
    slot_before = env.slot(learning_rate_id)
    value_before, revision_before = slot_before.current_value, slot_before.revision
    with pytest.raises(EntitySlotError, match="RE-TYPE-002"):
        env.propose_transition(learning_rate_id, "not a float", site="Bad")
    slot_after = env.slot(learning_rate_id)
    assert slot_after.current_value == value_before
    assert slot_after.revision == revision_before


def test_materialize_is_semantics_preserving() -> None:
    env = build_appendix_a_fixture()
    learning_rate_id = canonical_entity_id(kind=EntityKind.RU, module="GreetingLearning", identifier="learning_rate")
    before = env.slot(learning_rate_id)
    value_before, revision_before = before.current_value, before.revision
    instructions_before = len(env.instructions)
    env.materialize(learning_rate_id)
    after = env.slot(learning_rate_id)
    assert after.materialized is True
    assert after.current_value == value_before
    assert after.revision == revision_before
    assert len(env.instructions) == instructions_before


# --- Reason IR / ExecutionPlan generation and determinism -----------------


def test_reason_ir_payload_validates_against_schema(fixture_environment: EntityEnvironment) -> None:
    payload = lower_environment(fixture_environment)
    SCHEMAS.validate_file(payload, "reason_entity.schema.json")


def test_reason_ir_payload_contains_propose_validate_commit_triple() -> None:
    env = build_appendix_a_fixture()
    payload = lower_environment(env)
    ops_by_entity: dict[str, list[str]] = {}
    for instruction in payload["instructions"]:
        ops_by_entity.setdefault(instruction["entity"], []).append(instruction["op"])
    current_step_id = canonical_entity_id(kind=EntityKind.RU, module="GreetingLearning", identifier="current_step")
    ops = ops_by_entity[current_step_id]
    # `<-` must never be lowered to a bare overwrite (design §18): the
    # three-instruction transition triple must always be present together.
    for triple_start in range(len(ops) - 2):
        if ops[triple_start] == "ProposeEntityTransition":
            assert ops[triple_start:triple_start + 3] == [
                "ProposeEntityTransition", "ValidateEntityTransition", "CommitEntityTransition",
            ]


def test_entity_plan_declaration_order_and_atomic_boundaries(fixture_environment: EntityEnvironment) -> None:
    plan = entity_plan_for(fixture_environment)
    assert plan["schema_version"] == "reasonscript-reason-entity-plan/0.1"
    # 3 module-level RU + 1 RUS + 5 RUS-member RU + 1 DERIVE = 10.
    assert len(plan["declaration_order"]) == 10
    boundary_ids = {boundary["boundary_id"] for boundary in plan["atomic_boundaries"]}
    assert boundary_ids == {"Train#1", "Train#2", "Train#3"}
    assert plan["derived_evaluation"] == [{
        "entity": canonical_entity_id(kind=EntityKind.DERIVE, module="GreetingLearning", identifier="training_active"),
        "strategy": "on_read",
        "dependencies": [canonical_entity_id(kind=EntityKind.RU, module="GreetingLearning", identifier="current_step")],
    }]


def test_three_independent_generations_are_byte_identical() -> None:
    def canonical_bytes() -> bytes:
        env = build_appendix_a_fixture()
        document = {
            "reason_entities": lower_environment(env),
            "entity_plan": entity_plan_for(env),
        }
        return json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")

    runs = [canonical_bytes() for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


# --- RUO-U1 structural compatibility ---------------------------------------


def test_ruo_u1_projection_has_zero_diagnostics(fixture_environment: EntityEnvironment) -> None:
    document = project_to_ruo_u1(fixture_environment.table, object_identifier="GreetingLearning")
    diagnostics = validate_object(document)
    assert diagnostics == []


def test_ruo_u1_projection_rejects_nested_ruo() -> None:
    table = EntityTable()
    ruo_id = canonical_entity_id(kind=EntityKind.RUO, module="M", identifier="learner")
    table.declare(EntityRecord(canonical_id=ruo_id, kind=EntityKind.RUO, identifier="learner", owner_id=None))
    with pytest.raises(ValueError, match="RE-RUO-002"):
        project_to_ruo_u1(table, object_identifier="M")


# --- Canonical ID / registry sanity (exercised together, standalone) -------


def test_canonical_id_round_trips_through_the_whole_fixture(fixture_environment: EntityEnvironment) -> None:
    for canonical_id in fixture_environment.table.declaration_order():
        record = fixture_environment.table.get(canonical_id)
        assert record is not None
        parsed = parse_canonical_entity_id(canonical_id)
        assert parsed["kind"] is record.kind


def test_implicit_containment_relations_are_part_of_type(fixture_environment: EntityEnvironment) -> None:
    relations = implicit_containment_relations(fixture_environment.table)
    assert len(relations) == len(RUS_MEMBERS)
    assert all(isinstance(relation, EntityRelation) for relation in relations)
    assert all(relation.relation_type == "PartOf" for relation in relations)


def test_duplicate_declaration_is_rejected() -> None:
    table = EntityTable()
    record = EntityRecord(canonical_id="ruo:unit:ru:M.x", kind=EntityKind.RU, identifier="x", owner_id=None)
    table.declare(record)
    with pytest.raises(EntityRegistryError, match="RE-ID-001"):
        table.declare(record)
