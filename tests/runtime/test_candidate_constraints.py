"""Lazy / symbolic candidate space v0.1: `relation.filter` lowered to
symbolic constraints (spec sections 18-20), evidence-driven constraint
additions (11), canonical ordering and deduplication (31, 56), cursor
monotonicity across constraint additions (58-59), and exact-or-null
symbolic exclusion counts (29)."""

from __future__ import annotations

import pytest

from tests.runtime.conftest import execute

CAPTURES = """
    let factor = 5
    let state = Row { value: 7 }
"""

PREDICATES = {
    "row == 7": lambda v: v == 7,
    "row != 7": lambda v: v != 7,
    "row < 10": lambda v: v < 10,
    "row <= 10": lambda v: v <= 10,
    "row > 50": lambda v: v > 50,
    "row >= 50": lambda v: v >= 50,
    "10 < row": lambda v: 10 < v,
    "row % 3 == 1": lambda v: v % 3 == 1,
    "row % factor != 0": lambda v: v % 5 != 0,
    "row % state.value != 0": lambda v: v % 7 != 0,
    "!(row % 5 == 0)": lambda v: not v % 5 == 0,
    "row % 2 != 0 && row % 3 != 0": lambda v: v % 2 != 0 and v % 3 != 0,
    "row % 2 == 0 || row % 3 == 0": lambda v: v % 2 == 0 or v % 3 == 0,
    "!(row % 2 == 0 || row % 3 == 0)": lambda v: not (v % 2 == 0 or v % 3 == 0),
    "row > 10 && row % 7 == 0 && row != 21": lambda v: v > 10 and v % 7 == 0 and v != 21,
}


def metrics(outcome) -> dict:
    assert outcome.ok, (outcome.error_code, outcome.error_message)
    return outcome.metadata["runtime_metrics"]


@pytest.mark.parametrize("predicate", list(PREDICATES))
def test_symbolic_predicates_match_the_reference_set(predicate):
    outcome = execute(f"""
        {CAPTURES}
        let space = relation.filter(candidate_space.range(1, 60), {predicate})
        result = candidate_space.materialize(space)
    """)
    assert outcome.calculation_results == {"Answer": [v for v in range(1, 61) if PREDICATES[predicate](v)]}
    m = metrics(outcome)
    assert m["relation_filter_count"] == 1
    assert m["relation_filter_rows_scanned"] == 0  # no scan: the filter became a constraint
    assert m["candidate_constraint_count"] >= 1
    assert m["reasoning_event_type_counts"].get("CONSTRAINT_ADDED") == 1
    assert "CANDIDATE_PRUNED" not in m["reasoning_event_type_counts"]


@pytest.mark.parametrize("predicate", ["row * 2 > 10", "row / 2 < 5.0", "row % 0 == 1", "row % factor == row"])
def test_unsupported_predicates_are_rejected_not_scanned(predicate):
    outcome = execute(f"""
        {CAPTURES}
        result = candidate_space.materialize(relation.filter(candidate_space.range(1, 60), {predicate}))
    """)
    assert outcome.error_code == "CS-PRED-001"


def test_exclude_multiples_of_and_filter_canonicalize_to_one_constraint():
    outcome = execute("""
        let factor = 5
        let space = candidate_space.exclude_multiples_of(candidate_space.wheel6(5, 100), factor)
        space = relation.filter(space, row % factor != 0)
        space = relation.filter(space, !(row % factor == 0))
        result = candidate_space.materialize(space)
    """, mode="delta")
    assert outcome.calculation_results == {"Answer": [7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 49, 53, 59, 61, 67, 71, 73, 77, 79, 83, 89, 91, 97]}
    m = metrics(outcome)
    assert m["candidate_constraint_count"] == 1
    assert m["reasoning_event_type_counts"]["CONSTRAINT_ADDED"] == 3
    added = [e for e in outcome.metadata["reasoning_trace"] if e["event_type"] == "CONSTRAINT_ADDED"]
    assert [e["evidence"] for e in added] == ["value % 5 != 0"] * 3
    assert [e["metadata"]["added"] for e in added] == [1, 0, 0]
    assert all(e["metadata"]["constraint_count"] == 1 for e in added)


def test_constraint_order_does_not_change_the_candidate_sequence():
    def run(first: str, second: str):
        return execute(f"""
            let space = candidate_space.range(1, 50)
            space = relation.filter(space, {first})
            space = relation.filter(space, {second})
            let builder = array.builder()
            while !candidate_space.is_exhausted(space) {{
                builder.append(candidate_space.next(space))
            }}
            result = builder.finish()
        """)

    a = run("row % 3 != 0", "row != 10 && row > 4")
    b = run("row > 4 && row != 10", "row % 3 != 0")
    assert a.calculation_results == b.calculation_results == {"Answer": [v for v in range(5, 51) if v % 3 != 0 and v != 10]}
    assert metrics(a)["candidate_generated_count"] == metrics(b)["candidate_generated_count"]
    assert metrics(a)["candidate_skipped_count"] == metrics(b)["candidate_skipped_count"]


def test_evidence_mid_iteration_only_affects_future_candidates():
    outcome = execute("""
        let space = candidate_space.range(1, 20)
        let a = candidate_space.next(space)
        let b = candidate_space.next(space)
        space = relation.filter(space, row % 2 != 0)
        let c = candidate_space.next(space)
        let d = candidate_space.next(space)
        result = a * 1000 + b * 100 + c * 10 + d
    """)
    assert outcome.calculation_results == {"Answer": 1235}
    m = metrics(outcome)
    assert m["candidate_generated_count"] == 4
    assert m["candidate_skipped_count"] == 1  # only 4 was generated and rejected; 1 and 2 were never revisited


def test_lookahead_is_rechecked_after_a_constraint_is_added():
    outcome = execute("""
        let space = candidate_space.range(1, 10)
        let a = candidate_space.next(space)
        let more = candidate_space.is_exhausted(space)
        space = candidate_space.exclude_multiples_of(space, 2)
        let b = candidate_space.next(space)
        result = a * 10 + b
    """)
    assert outcome.calculation_results == {"Answer": 13}
    m = metrics(outcome)
    assert m["candidate_skipped_count"] == 1
    assert m["candidate_generated_count"] == 2


def test_symbolic_exclusion_count_is_exact_for_bounds_and_null_otherwise():
    bounds = execute("""
        let space = relation.filter(candidate_space.wheel6(5, 100), row > 90)
        result = candidate_space.materialize(space)
    """)
    assert bounds.calculation_results == {"Answer": [91, 95, 97]}
    assert metrics(bounds)["candidate_symbolically_excluded_count"] == 29
    mixed = execute("""
        let space = relation.filter(candidate_space.wheel6(5, 100), row > 90)
        space = candidate_space.exclude_multiples_of(space, 5)
        space = relation.filter(space, row < 97)
        result = candidate_space.materialize(space)
    """)
    assert mixed.calculation_results == {"Answer": [91]}
    m = metrics(mixed)
    assert m["candidate_symbolically_excluded_count"] is None
    assert m["candidate_constraint_count"] == 3


def test_array_filters_keep_their_scan_semantics_and_pruning_events():
    outcome = execute("""
        let builder = array.builder()
        let i = 1
        while i <= 10 {
            builder.append(Row { value: i })
            i = i + 1
        }
        let rows = relation.filter(builder.finish(), row.value % 2 != 0)
        result = relation.count(rows)
    """)
    assert outcome.calculation_results == {"Answer": 5}
    m = metrics(outcome)
    assert m["relation_filter_rows_scanned"] == 10
    assert m["candidate_pruned_count"] == m["candidate_materialized_pruned_count"] == 5
    assert m["reasoning_event_type_counts"] == {"CANDIDATE_PRUNED": 1}
    assert m["candidate_constraint_count"] == 0
