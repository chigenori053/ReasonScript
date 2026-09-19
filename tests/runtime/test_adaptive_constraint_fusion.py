"""Adaptive / Cost-Aware Constraint Fusion v0.1: `context.constraint_fusion
= "adaptive"` (Model G) decides per constraint whether fusing pays off,
via a cheap O(1) cost estimate, instead of always fusing when possible
(`"always"`, Constraint Fusion v0.1 / Model F) or never (`"off"`, default,
Model E). See `ReasonScript_Adaptive_Cost_Aware_Constraint_Fusion_v0_1.md`."""

from __future__ import annotations

from tests.runtime.conftest import execute

TIMING_KEYS = {
    "fast_path_count", "fast_path_enabled", "runtime_execution_ns", "allocation_count",
    "allocated_bytes", "peak_live_bytes",
}


def metrics(outcome) -> dict:
    assert outcome.ok, (outcome.error_code, outcome.error_message)
    return outcome.metadata["runtime_metrics"]


def comparable(outcome) -> dict:
    return {
        "result": outcome.calculation_results,
        "reasoning_trace": outcome.metadata["reasoning_trace"],
        "loop_trace": outcome.metadata["loop_trace"],
    }


def test_off_always_and_adaptive_agree_on_result_and_hypothesis_sequence():
    """A small search space where the cost estimate rejects fusing 5 and 7
    (spec completion judgement 1): all three policies must still agree."""
    body = """
        let space = candidate_space.wheel6(5, 40)
        space = relation.filter(space, row % 5 != 0)
        space = relation.filter(space, row % 7 != 0)
        result = candidate_space.materialize(space)
    """
    off, always, adaptive = (execute(body, constraint_fusion=p) for p in ("off", "always", "adaptive"))
    assert off.calculation_results == always.calculation_results == adaptive.calculation_results
    m_off, m_always, m_adaptive = metrics(off), metrics(always), metrics(adaptive)
    assert m_off["fused_constraint_count"] == 0
    assert m_always["fused_constraint_count"] == 2
    # Level A: for a tiny search space (40), Adaptive should reject both --
    # the estimator's own conservative bias (spec section 71).
    assert m_adaptive["fusion_rejected_cost_count"] >= 1


def test_adaptive_selects_fusion_for_a_large_search_space():
    body = """
        let space = candidate_space.wheel6(5, 5000000)
        space = relation.filter(space, row % 5 != 0)
        space = relation.filter(space, row % 7 != 0)
        result = candidate_space.next(space)
    """
    outcome = execute(body, constraint_fusion="adaptive")
    m = metrics(outcome)
    assert m["fused_constraint_count"] == 2  # both selected
    assert m["fusion_selected_count"] == 2
    assert m["fusion_rejected_cost_count"] == 0
    assert m["constraint_fusion_policy"] == "adaptive"


def test_worst_case_regression_from_always_fusion_is_recovered():
    """highly_composite_24b-equivalent: a small absolute candidate count
    with several small factors -- Constraint Fusion v0.1's own worst
    regression case (Always much slower than Off). Adaptive should reject
    fusing here (spec completion judgement 2's semantics -- G should not
    behave like F in this exact regime)."""
    body = """
        let remaining = 720720
        let space = candidate_space.wheel6(5, candidate_space.isqrt(remaining))
        space = relation.filter(space, row % 5 != 0)
        space = relation.filter(space, row % 7 != 0)
        space = relation.filter(space, row % 11 != 0)
        space = relation.filter(space, row % 13 != 0)
        result = candidate_space.is_exhausted(space)
    """
    always = execute(body, constraint_fusion="always")
    adaptive = execute(body, constraint_fusion="adaptive")
    assert always.calculation_results == adaptive.calculation_results
    m_always, m_adaptive = metrics(always), metrics(adaptive)
    assert m_always["fused_constraint_count"] == 4  # Always fuses all four
    # Adaptive fuses strictly fewer of them for this tiny remaining-candidate case.
    assert m_adaptive["fused_constraint_count"] < m_always["fused_constraint_count"]
    assert m_adaptive["fusion_rejected_cost_count"] > 0


def test_adaptive_does_not_reject_everything():
    """spec completion judgement 4 / section 107: an Adaptive policy that
    always chooses residual is not a valid implementation."""
    outcome = execute("""
        let space = candidate_space.wheel6(5, 10000000)
        space = relation.filter(space, row % 5 != 0)
        result = candidate_space.next(space)
    """, constraint_fusion="adaptive")
    assert metrics(outcome)["fusion_selected_count"] > 0


def test_adaptive_determinism_across_runs_and_fast_path_modes():
    body = """
        let space = candidate_space.wheel6(5, 2000000)
        space = relation.filter(space, row % 5 != 0)
        space = relation.filter(space, row % 7 != 0)
        space = relation.filter(space, row % 101 != 0)
        result = candidate_space.next(space)
    """
    runs = [comparable(execute(body, mode="delta", constraint_fusion="adaptive")) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    assert comparable(execute(body, mode="delta", constraint_fusion="adaptive", fast_path=False)) == runs[0]


def test_cursor_preserved_across_adaptive_decisions():
    outcome = execute("""
        let space = candidate_space.wheel6(5, 2000000)
        let a = candidate_space.next(space)
        let b = candidate_space.next(space)
        space = relation.filter(space, row % 5 != 0)
        space = relation.filter(space, row % 101 != 0)
        let c = candidate_space.next(space)
        result = a * 1000000 + b * 1000 + c
    """, constraint_fusion="adaptive")
    assert outcome.calculation_results == {"Answer": 5007011}  # a=5, b=7, c=11: none revisited


def test_invalid_constraint_fusion_value_is_a_diagnostic():
    outcome = execute("result = 1", constraint_fusion="bogus")
    assert outcome.error_code == "RTH-PROTO-006"
