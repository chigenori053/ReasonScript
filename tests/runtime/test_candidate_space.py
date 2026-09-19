"""Lazy / symbolic candidate space v0.1: core semantics (spec sections 7-15
and 17), runtime metrics (section 47), events (section 26) and the boundary
cases of section 54. Every program runs on the native host."""

from __future__ import annotations

import pytest

from frontend.language_surface import parse
from frontend.language_surface.parser import SurfaceSyntaxError
from tests.runtime.conftest import execute

WHEEL6_5_40 = [5, 7, 11, 13, 17, 19, 23, 25, 29, 31, 35, 37]


def metrics(outcome) -> dict:
    assert outcome.ok, (outcome.error_code, outcome.error_message)
    return outcome.metadata["runtime_metrics"]


def test_wheel6_next_yields_the_materialized_sequence_without_materializing():
    outcome = execute("""
        let space = candidate_space.wheel6(5, 40)
        let builder = array.builder()
        while !candidate_space.is_exhausted(space) {
            builder.append(candidate_space.next(space))
        }
        result = builder.finish()
    """)
    assert outcome.calculation_results == {"Answer": WHEEL6_5_40}
    m = metrics(outcome)
    assert m["candidate_space_estimated_size"] == 12
    assert m["candidate_generated_count"] == m["candidate_space_next_count"] == 12
    assert m["candidate_skipped_count"] == m["candidate_materialized_count"] == 0
    assert m["candidate_constraint_count"] == m["candidate_constraint_eval_count"] == 0
    assert m["candidate_symbolically_excluded_count"] == 0
    assert m["reasoning_event_type_counts"] == {"CANDIDATE_SPACE_CREATED": 1, "CANDIDATE_SPACE_EXHAUSTED": 1}
    assert m["reasoning_step_count"] == 2


def test_range_exclude_and_materialize():
    outcome = execute("""
        let space = candidate_space.range(1, 10)
        let odds = candidate_space.exclude_multiples_of(space, 2)
        result = candidate_space.materialize(odds)
    """)
    assert outcome.calculation_results == {"Answer": [1, 3, 5, 7, 9]}
    m = metrics(outcome)
    assert m["candidate_materialized_count"] == 5
    assert m["candidate_constraint_count"] == 1
    assert m["candidate_constraint_eval_count"] == 10
    assert m["candidate_symbolically_excluded_count"] is None  # modulo exclusions are never estimated
    assert m["reasoning_event_type_counts"]["CONSTRAINT_ADDED"] == 1
    assert "CANDIDATE_PRUNED" not in m["reasoning_event_type_counts"]


def test_relation_count_is_symbolic_for_the_unvisited_range():
    outcome = execute("""
        let space = candidate_space.wheel6(5, 100)
        let first = candidate_space.next(space)
        result = relation.count(space)
    """)
    assert outcome.calculation_results == {"Answer": 31}  # 32 wheel values in [5, 100] minus the returned 5
    assert metrics(outcome)["relation_count_count"] == 1


def test_relation_count_refuses_a_hidden_scan_over_constraints():
    outcome = execute("""
        let space = candidate_space.exclude_multiples_of(candidate_space.range(1, 100), 3)
        result = relation.count(space)
    """)
    assert outcome.error_code == "CS-COUNT-001"


def test_next_on_an_exhausted_space_is_a_diagnostic():
    outcome = execute("""
        let space = candidate_space.range(1, 1)
        let a = candidate_space.next(space)
        result = candidate_space.next(space)
    """)
    assert outcome.error_code == "CS-003"
    assert outcome.metadata["runtime_metrics"]["reasoning_event_type_counts"]["CANDIDATE_SPACE_EXHAUSTED"] == 1


def test_reset_returns_a_fresh_cursor_without_touching_the_original():
    outcome = execute("""
        let space = candidate_space.range(1, 3)
        let a = candidate_space.next(space)
        let fresh = candidate_space.reset(space)
        result = candidate_space.next(fresh) * 10 + candidate_space.next(space)
    """)
    assert outcome.calculation_results == {"Answer": 12}


def test_isqrt_is_exact():
    outcome = execute("""
        result = candidate_space.isqrt(24) * 100 + candidate_space.isqrt(25) * 10 + candidate_space.isqrt(26)
    """)
    assert outcome.calculation_results == {"Answer": 455}
    assert execute("result = candidate_space.isqrt(0 - 1)").error_code == "CS-005"


@pytest.mark.parametrize("body, expected, estimated", [
    # empty space
    ("let s = candidate_space.wheel6(10, 5)\n result = candidate_space.is_exhausted(s)", True, 0),
    # single candidate
    ("let s = candidate_space.range(7, 7)\n result = candidate_space.materialize(s)", [7], 1),
    # very large upper bound: creation and one next stay O(1)
    ("let s = candidate_space.wheel6(5, 1000000000000)\n result = candidate_space.next(s)", 5, 333333333332),
])
def test_boundary_domains(body, expected, estimated):
    outcome = execute(body)
    assert outcome.calculation_results == {"Answer": expected}
    m = metrics(outcome)
    assert m["candidate_space_estimated_size"] == estimated
    assert m["candidate_materialized_count"] <= 1


def test_all_candidates_excluded_counts_every_skip():
    outcome = execute("""
        let s = candidate_space.exclude_multiples_of(candidate_space.range(1, 10), 1)
        result = candidate_space.is_exhausted(s)
    """)
    assert outcome.calculation_results == {"Answer": True}
    m = metrics(outcome)
    assert m["candidate_skipped_count"] == m["candidate_generated_skipped_count"] == 10
    assert m["candidate_generated_count"] == 0


def test_contradictory_bounds_exhaust_immediately_with_exact_exclusion_count():
    outcome = execute("""
        let s = relation.filter(candidate_space.range(1, 100), row > 100 && row < 10)
        result = candidate_space.is_exhausted(s)
    """)
    assert outcome.calculation_results == {"Answer": True}
    m = metrics(outcome)
    assert m["candidate_constraint_count"] == 2
    assert m["candidate_symbolically_excluded_count"] == 100
    assert m["candidate_skipped_count"] == 0


def test_many_constraints_and_repeated_constraint_deduplicate():
    outcome = execute("""
        let s = candidate_space.range(1, 100)
        let m = 2
        while m <= 21 {
            s = candidate_space.exclude_multiples_of(s, m)
            s = candidate_space.exclude_multiples_of(s, m)
            m = m + 1
        }
        result = candidate_space.materialize(s)
    """)
    assert outcome.calculation_results == {"Answer": [1, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97]}
    m = metrics(outcome)
    assert m["candidate_constraint_count"] == 20
    assert m["reasoning_event_type_counts"]["CONSTRAINT_ADDED"] == 40


def test_surface_type_checks():
    def check(body: str):
        parse(f"module M {{\n calculation Answer {{\n{body}\n }}\n}}")  # parse validates the surface

    check("let s = candidate_space.wheel6(5, 40)\n let n = candidate_space.next(s) + 1\n result = relation.count(relation.filter(s, row % 3 != 0))")
    with pytest.raises(SurfaceSyntaxError, match="CS-001"):
        check("result = candidate_space.wheel6(5)")
    with pytest.raises(SurfaceSyntaxError, match="CS-002"):
        check("result = candidate_space.next(5)")
    with pytest.raises(SurfaceSyntaxError, match="CS-002"):
        check("result = candidate_space.range(1, 2.5)")
    with pytest.raises(SurfaceSyntaxError, match="REL-004"):
        check("let s = candidate_space.range(1, 9)\n result = relation.filter_eq(s, \"value\", 3)")
    with pytest.raises(SurfaceSyntaxError, match="REL-PRED-003"):
        check("let s = candidate_space.range(1, 9)\n result = relation.filter(s, row % 3)")
