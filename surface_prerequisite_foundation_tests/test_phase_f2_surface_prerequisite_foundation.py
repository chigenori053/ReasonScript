"""Phase F2 — Surface Prerequisite Foundation tests (RS-RE-FSM-001 §13).

New surface syntax (`ru:`/`rus:`/`ruo:`/`derive:`/`<-`) is NOT enabled in
this Phase. These tests cover only the prerequisite groundwork: operator
continuation in the parser (D-6), `<-` lexing, the standalone Entity
identity/registry modules, and the diagnostics category wiring.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from frontend.entity import (
    CanonicalIdError,
    EntityKind,
    EntityRecord,
    EntityRegistryError,
    EntityTable,
    canonical_entity_id,
    parse_canonical_entity_id,
)
from frontend.language_surface.lexer import tokenize
from toolchain.diagnostics import category_for_code
from toolchain.pipeline import PipelineError, validate_source

PATH = Path("phase_f2.rsn")


def compiles(source: str) -> None:
    validate_source(source, PATH)


# --- F2-1: operator continuation (D-6) --------------------------------------


def test_trailing_operator_continuation_is_accepted() -> None:
    compiles(
        """
        module M {
          calculation C {
            let t = 20.0
            let comfort = t > 18.0 &&
              t < 26.0
            result = comfort
          }
        }
        """
    )


def test_trailing_comma_continuation_is_accepted() -> None:
    compiles(
        """
        module M {
          calculation C {
            let values = [1,
              2,
              3]
            result = values
          }
        }
        """
    )


def test_incomplete_expression_before_closing_brace_still_fails() -> None:
    # The `}` that closes the calculation body must never be consumed as a
    # continuation line, even though `result =` ends in `=`.
    with pytest.raises(PipelineError):
        compiles(
            """
            module M {
              calculation C {
                result =
              }
            }
            """
        )


def test_multiline_struct_literal_inside_call_still_parses() -> None:
    # Regression guard: the `}` continuation guard must not block legitimate
    # nested struct literals that close inside an open paren/bracket.
    compiles(
        """
        module M {
          struct Point {
            x: int
            y: int
          }
          fn Sum(p: Point) -> int {
            return p.x + p.y
          }
          calculation C {
            result = Sum(
              Point {
                x: 1,
                y: 2
              }
            )
          }
        }
        """
    )


# --- F2-2: `<-` lexing -------------------------------------------------------


def test_arrow_minus_is_tokenized_as_a_single_operator() -> None:
    tokens = [
        token for token in tokenize("score <- 0.8")
        if token.token_type.value not in {"EOF", "NewLine"}
    ]
    values = [(token.token_type.value, token.value) for token in tokens]
    assert ("Operator", "<-") in values


def test_less_than_negative_with_space_stays_two_operators() -> None:
    tokens = [
        token for token in tokenize("a < -1")
        if token.token_type.value not in {"EOF", "NewLine"}
    ]
    values = [(token.token_type.value, token.value) for token in tokens]
    assert values == [
        ("Identifier", "a"),
        ("Operator", "<"),
        ("Operator", "-"),
        ("Number", "1"),
    ]


def test_state_transition_syntax_is_still_unsupported_before_e1() -> None:
    # `<-` is lexed, but E1 has not wired a parser dispatch for it yet.
    with pytest.raises(PipelineError):
        compiles(
            """
            module M {
              calculation C {
                let score = 0.5
                score <- 0.8
                result = score
              }
            }
            """
        )


# --- F2-3: Canonical Entity ID + EntityTable (standalone, Parser-free) -----


def test_canonical_entity_id_for_module_level_ru() -> None:
    canonical_id = canonical_entity_id(
        kind=EntityKind.RU, module="GreetingLearning", identifier="learning_rate"
    )
    assert canonical_id == "ruo:unit:ru:GreetingLearning.learning_rate"


def test_canonical_entity_id_for_ruo_uses_object_prefix() -> None:
    canonical_id = canonical_entity_id(
        kind=EntityKind.RUO, module="M", identifier="learner"
    )
    assert canonical_id.startswith("ruo:object:ruo:")


def test_canonical_entity_id_with_package_and_owner_path() -> None:
    canonical_id = canonical_entity_id(
        kind=EntityKind.RU,
        package="app",
        module="GreetingLearning",
        owner_path=("greeting_relation",),
        identifier="token_relation",
    )
    assert canonical_id == "ruo:unit:ru:app.GreetingLearning.greeting_relation.token_relation"


def test_canonical_entity_id_rejects_invalid_identifier() -> None:
    with pytest.raises(CanonicalIdError):
        canonical_entity_id(kind=EntityKind.RU, module="M", identifier="not valid")


def test_parse_canonical_entity_id_round_trips() -> None:
    canonical_id = canonical_entity_id(
        kind=EntityKind.DERIVE, module="M", identifier="training_active"
    )
    parsed = parse_canonical_entity_id(canonical_id)
    assert parsed["kind"] is EntityKind.DERIVE
    assert parsed["path"] == ("M", "training_active")


def test_parse_canonical_entity_id_rejects_kind_prefix_mismatch() -> None:
    with pytest.raises(CanonicalIdError):
        parse_canonical_entity_id("ruo:object:ru:M.x")


def test_entity_table_rejects_duplicate_canonical_id() -> None:
    table = EntityTable()
    record = EntityRecord(
        canonical_id="ruo:unit:ru:M.x", kind=EntityKind.RU, identifier="x", owner_id=None
    )
    table.declare(record)
    with pytest.raises(EntityRegistryError, match="RE-ID-001"):
        table.declare(record)


def test_entity_table_rejects_unknown_owner() -> None:
    table = EntityTable()
    with pytest.raises(EntityRegistryError, match="RE-OWNER-001"):
        table.declare(
            EntityRecord(
                canonical_id="ruo:unit:ru:M.rus.x",
                kind=EntityKind.RU,
                identifier="x",
                owner_id="ruo:unit:rus:M.rus",
            )
        )


def test_entity_table_tracks_membership_in_declaration_order() -> None:
    table = EntityTable()
    table.declare(
        EntityRecord(
            canonical_id="ruo:unit:rus:M.rus", kind=EntityKind.RUS, identifier="rus", owner_id=None
        )
    )
    for name in ("a", "b", "c"):
        table.declare(
            EntityRecord(
                canonical_id=f"ruo:unit:ru:M.rus.{name}",
                kind=EntityKind.RU,
                identifier=name,
                owner_id="ruo:unit:rus:M.rus",
            )
        )
    assert table.members_of("ruo:unit:rus:M.rus") == (
        "ruo:unit:ru:M.rus.a", "ruo:unit:ru:M.rus.b", "ruo:unit:ru:M.rus.c",
    )


def test_entity_table_rejects_self_referential_derive() -> None:
    # Declarations happen in a single left-to-right pass (matching the
    # Surface language's own no-forward-reference rule), so a multi-node
    # A<->B dependency cycle can never reach the cycle detector: the "back"
    # edge is always caught first as RE-REL-001 (unknown dependency). Only
    # direct self-reference is a reachable cycle shape.
    table = EntityTable()
    with pytest.raises(EntityRegistryError, match="RE-DERIVE-001"):
        table.declare(
            EntityRecord(
                canonical_id="ruo:unit:derive:M.a",
                kind=EntityKind.DERIVE,
                identifier="a",
                owner_id=None,
                dependencies=("ruo:unit:derive:M.a",),
            )
        )


def test_entity_table_rejects_forward_referenced_derive_dependency() -> None:
    # A dependency on a not-yet-declared Entity is rejected as unknown, not
    # silently accepted as a forward reference.
    table = EntityTable()
    with pytest.raises(EntityRegistryError, match="RE-REL-001"):
        table.declare(
            EntityRecord(
                canonical_id="ruo:unit:derive:M.a",
                kind=EntityKind.DERIVE,
                identifier="a",
                owner_id=None,
                dependencies=("ruo:unit:derive:M.b",),
            )
        )


def test_entity_table_relations_require_known_endpoints() -> None:
    table = EntityTable()
    table.declare(
        EntityRecord(canonical_id="ruo:unit:ru:M.x", kind=EntityKind.RU, identifier="x", owner_id=None)
    )
    with pytest.raises(EntityRegistryError, match="RE-REL-001"):
        table.declare_relation("ruo:relation:M.r1", "ruo:unit:ru:M.x", "ruo:unit:ru:M.missing")


def test_entity_table_declaration_order_is_insertion_order() -> None:
    table = EntityTable()
    ids = ["ruo:unit:ru:M.c", "ruo:unit:ru:M.a", "ruo:unit:ru:M.b"]
    for canonical_id in ids:
        table.declare(
            EntityRecord(
                canonical_id=canonical_id,
                kind=EntityKind.RU,
                identifier=canonical_id.rsplit(".", 1)[-1],
                owner_id=None,
            )
        )
    assert table.declaration_order() == tuple(ids)


# --- F2-4: diagnostics category wiring --------------------------------------


def test_re_prefixed_codes_map_to_semantic_category() -> None:
    assert category_for_code("RE-DECL-001") == "Semantic"


def test_existing_category_mapping_is_unaffected() -> None:
    assert category_for_code("TYPE-001") == "Type"
    assert category_for_code("FN-005") == "Function"
