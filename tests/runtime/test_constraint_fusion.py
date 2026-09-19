"""Constraint Fusion v0.1: `context.constraint_fusion` folds prime
`NotDivisibleBy(p)` constraints into the CandidateSpace's generator
instead of storing them as residual constraints (spec
`ReasonScript_Constraint_Fusion_v0_1.md`). Fusion is opt-in and defaults
to off (`tests/runtime/test_candidate_*.py` already cover that default
path byte-for-byte); this file covers Model E == Model F equivalence,
the fusion-specific counters and events, and determinism with fusion on."""

from __future__ import annotations

import pytest

from tests.runtime.conftest import execute

TIMING_KEYS = {
    "fast_path_count", "fast_path_enabled", "runtime_execution_ns", "allocation_count",
    "allocated_bytes", "peak_live_bytes",
}

SPACE = """
    let space = candidate_space.wheel6(5, 300)
    space = relation.filter(space, row % 5 != 0)
    space = relation.filter(space, row % 7 != 0)
    let sum = 0
    while !candidate_space.is_exhausted(space) {
        sum = sum + candidate_space.next(space)
    }
    result = sum
"""


def metrics(outcome) -> dict:
    assert outcome.ok, (outcome.error_code, outcome.error_message)
    return outcome.metadata["runtime_metrics"]


def comparable(outcome) -> dict:
    return {
        "result": outcome.calculation_results,
        "reasoning_trace": outcome.metadata["reasoning_trace"],
        "loop_trace": outcome.metadata["loop_trace"],
    }


def test_fusion_produces_the_same_result_with_fewer_skips_and_no_constraint_eval():
    off = execute(SPACE, constraint_fusion=False)
    on = execute(SPACE, constraint_fusion=True)
    assert on.calculation_results == off.calculation_results  # spec Level 42
    m_off, m_on = metrics(off), metrics(on)
    assert m_on["candidate_generated_count"] == m_off["candidate_generated_count"]
    assert m_on["candidate_skipped_count"] == 0  # excluded values are never generated at all
    assert m_off["candidate_skipped_count"] > 0
    assert m_on["candidate_constraint_eval_count"] == 0
    assert m_off["candidate_constraint_eval_count"] > 0
    assert m_on["residual_constraint_count"] == 0
    assert m_on["fused_constraint_count"] == 2
    assert m_on["fused_modulus"] == 210  # lcm(6, 5, 7)
    assert m_on["constraint_fusion_count"] == 2
    assert m_on["constraint_fusion_rebuild_count"] == 2
    assert m_on["fusion_fallback_count"] == 0
    assert m_on["reasoning_event_type_counts"] == {
        "CANDIDATE_SPACE_CREATED": 1, "CANDIDATE_SPACE_EXHAUSTED": 1,
        "CONSTRAINT_FUSED": 2, "GENERATOR_REBUILT": 2,
    }
    assert m_off["reasoning_event_type_counts"] == {
        "CANDIDATE_SPACE_CREATED": 1, "CANDIDATE_SPACE_EXHAUSTED": 1, "CONSTRAINT_ADDED": 2,
    }


def test_fusion_hypothesis_sequence_matches_non_fused():
    def hypotheses(outcome):
        return [(e["event_type"], e["evidence"]) for e in outcome.metadata["reasoning_trace"] if e["event_type"].startswith("HYPOTHESIS")]

    body = """
        let space = candidate_space.wheel6(5, candidate_space.isqrt(5005 * 99991))
        let remaining = 5005 * 99991
        let searching = true
        while searching {
            if candidate_space.is_exhausted(space) {
                searching = false
            } else {
                let c = candidate_space.next(space)
                if c * c > remaining {
                    searching = false
                } else {
                    if remaining % c == 0 {
                        while remaining % c == 0 {
                            reasoning.event("HYPOTHESIS_VERIFIED", "factor", c)
                            remaining = int(remaining / c)
                        }
                        let factor = c
                        space = relation.filter(space, row % factor != 0)
                    } else {
                        reasoning.event("HYPOTHESIS_REJECTED", "candidate", c)
                    }
                }
            }
        }
        result = remaining
    """
    off = execute(body, mode="delta", constraint_fusion=False)
    on = execute(body, mode="delta", constraint_fusion=True)
    assert off.calculation_results == on.calculation_results  # spec Level 42
    assert hypotheses(off) == hypotheses(on)  # spec Level 43
    assert metrics(on)["candidate_skipped_count"] < metrics(off)["candidate_skipped_count"]


def test_fusion_falls_back_to_residual_over_the_modulus_budget():
    body = """
        let space = candidate_space.range(1, 1000000)
        space = relation.filter(space, row % 2 != 0)
        space = relation.filter(space, row % 3 != 0)
        space = relation.filter(space, row % 5 != 0)
        space = relation.filter(space, row % 7 != 0)
        space = relation.filter(space, row % 11 != 0)
        space = relation.filter(space, row % 13 != 0)
        result = candidate_space.next(space)
    """
    fallback_body = body.replace(
        "result = candidate_space.next(space)",
        "space = relation.filter(space, row % 17 != 0)\n        result = candidate_space.next(space)",
    )
    on = execute(body, constraint_fusion=True)
    m = metrics(on)
    assert m["fused_modulus"] == 30_030  # 2*3*5*7*11*13, the default budget
    assert m["constraint_fusion_count"] == 6
    fallback = execute(fallback_body, constraint_fusion=True)
    mf = metrics(fallback)
    assert mf["fused_modulus"] == 30_030  # unchanged: 17 would exceed the budget
    assert mf["residual_constraint_count"] == 1
    assert mf["fusion_fallback_count"] == 1
    assert mf["reasoning_event_type_counts"]["FUSION_FALLBACK"] == 1


def test_composite_modulus_stays_residual_with_fusion_on():
    outcome = execute("""
        let space = relation.filter(candidate_space.range(1, 50), row % 15 != 0)
        result = candidate_space.materialize(space)
    """, constraint_fusion=True)
    assert outcome.calculation_results == {"Answer": [v for v in range(1, 51) if v % 15 != 0]}
    m = metrics(outcome)
    assert m["residual_constraint_count"] == 1
    assert m["fused_constraint_count"] == 0


def test_fusion_determinism_across_runs_and_fast_path_modes():
    runs = [comparable(execute(SPACE, mode="delta", constraint_fusion=True)) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    assert comparable(execute(SPACE, mode="delta", constraint_fusion=True, fast_path=False)) == runs[0]


@pytest.mark.parametrize("order", [(5, 7), (7, 5)])
def test_fusion_is_order_invariant(order):
    p, q = order
    body = f"""
        let space = candidate_space.wheel6(5, 100)
        space = relation.filter(space, row % {p} != 0)
        space = relation.filter(space, row % {q} != 0)
        result = candidate_space.materialize(space)
    """
    outcome = execute(body, constraint_fusion=True)
    assert outcome.calculation_results == {"Answer": [v for v in range(5, 101) if v % 5 != 0 and v % 7 != 0 and (v % 6 in (1, 5))]}
