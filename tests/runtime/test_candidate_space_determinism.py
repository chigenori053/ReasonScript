"""Lazy / symbolic candidate space v0.1: Model E (lazy sieve reasoning)
against Model D (materialized sieve reasoning) -- same result (Level A),
same hypothesis sequence (Level B), no materialization proportional to the
candidate space (Level C), and determinism across runs and Fast Path modes
(section 30)."""

from __future__ import annotations

import pytest

from tests.runtime.conftest import execute

DECLARATIONS = """
    struct Candidate {
        value: int
    }
"""

SMALL_PRIMES = """
    let remaining = __N__
    while remaining % 2 == 0 {
        reasoning.event("HYPOTHESIS_VERIFIED", "factor", 2)
        remaining = int(remaining / 2)
    }
    while remaining % 3 == 0 {
        reasoning.event("HYPOTHESIS_VERIFIED", "factor", 3)
        remaining = int(remaining / 3)
    }
"""

# Model D: the v1.3 SpecTest sieve-reasoning program (materialized wheel-6
# space as Array<Struct>, bulk relation.filter on a verified factor).
MODEL_D = SMALL_PRIMES + """
    let builder = array.builder()
    let cand = 5
    let use_plus2 = true
    while cand * cand <= remaining {
        builder.append(Candidate { value: cand })
        if use_plus2 {
            cand = cand + 2
            use_plus2 = false
        } else {
            cand = cand + 4
            use_plus2 = true
        }
    }
    let candidates = builder.finish()
    let idx = 0
    let total = relation.count(candidates)
    while idx < total {
        let c = candidates[idx].value
        if c * c > remaining {
            idx = total
        } else {
            if remaining % c == 0 {
                while remaining % c == 0 {
                    reasoning.event("HYPOTHESIS_VERIFIED", "factor", c)
                    remaining = int(remaining / c)
                }
                let factor = c
                candidates = relation.filter(candidates, candidate.value % factor != 0)
                total = relation.count(candidates)
            } else {
                reasoning.event("HYPOTHESIS_REJECTED", "candidate", c)
                idx = idx + 1
            }
        }
    }
    if remaining > 1 {
        reasoning.event("TERMINATION_INFERRED", "prime", remaining)
    }
    result = remaining
"""

# Model E: identical reasoning, lazy candidate representation.
MODEL_E = SMALL_PRIMES + """
    let space = candidate_space.wheel6(5, candidate_space.isqrt(remaining))
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
    if remaining > 1 {
        reasoning.event("TERMINATION_INFERRED", "prime", remaining)
    }
    result = remaining
"""

CASES = {
    "prime": 1000003,
    "semiprime": 97 * 8111,
    "semiprime_near_equal": 10007 * 10009,
    "repeated_factor": 7 ** 6,
    "highly_composite": 720720,
    "mixed": 2 * 3 * 5 * 7 * 11 * 13 * 17 * 19 * 23,
    "square_boundary": 1009 * 1009,
    "trivial": 1,
}

TIMING_KEYS = {"fast_path_count", "fast_path_enabled", "runtime_execution_ns", "allocation_count", "allocated_bytes", "peak_live_bytes"}


def run(model: str, n: int, **options):
    outcome = execute(model.replace("__N__", str(n)), declarations=DECLARATIONS, **{"mode": "delta", **options})
    assert outcome.ok, (outcome.error_code, outcome.error_message)
    return outcome


def hypotheses(outcome) -> list[tuple[str, int]]:
    return [(e["event_type"], e["evidence"]) for e in outcome.metadata["reasoning_trace"] if e["event_type"].startswith("HYPOTHESIS")]


def comparable(outcome) -> dict:
    return {
        "result": outcome.calculation_results,
        "reasoning_trace": outcome.metadata["reasoning_trace"],
        "loop_trace": outcome.metadata["loop_trace"],
        "metrics": {k: v for k, v in outcome.metadata["runtime_metrics"].items() if k not in TIMING_KEYS},
    }


@pytest.mark.parametrize("n", list(CASES.values()), ids=list(CASES))
def test_model_e_matches_model_d_result_and_hypothesis_sequence(n):
    d, e = run(MODEL_D, n), run(MODEL_E, n)
    assert e.calculation_results == d.calculation_results  # Level A
    assert hypotheses(e) == hypotheses(d)  # Level B
    md, me = d.metadata["runtime_metrics"], e.metadata["runtime_metrics"]
    assert me["hypothesis_test_count"] == md["hypothesis_test_count"]
    # Level C: nothing materialized, no per-candidate writes, and every
    # generated candidate was tested -- except the one that ended the
    # search by the sqrt bound when the space was not exhausted.
    assert me["candidate_materialized_count"] == 0
    assert me["array_write_count"] == me["builder_appends"] == 0
    rejected = me["reasoning_event_type_counts"].get("HYPOTHESIS_REJECTED", 0)
    wheel_factors = {evidence for kind, evidence in hypotheses(e) if kind == "HYPOTHESIS_VERIFIED" and evidence >= 5}
    bound_exit = 0 if "CANDIDATE_SPACE_EXHAUSTED" in me["reasoning_event_type_counts"] else 1
    assert me["candidate_generated_count"] == rejected + len(wheel_factors) + bound_exit
    assert me["relation_filter_rows_scanned"] == 0
    assert me["vm_instruction_count"] <= md["vm_instruction_count"]


def test_model_e_is_deterministic_across_runs_and_fast_path_modes():
    n = CASES["highly_composite"]
    runs = [comparable(run(MODEL_E, n)) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    assert comparable(run(MODEL_E, n, fast_path=False)) == runs[0]


def test_model_e_physical_work_scales_with_hypotheses_not_with_the_space():
    """5*7*11*13*p: after the four small factors the search stops at
    sqrt(p), so the initial wheel-6 space (sqrt(5005 p)) is ~70x larger than
    the hypotheses actually tested. Model D's allocations grow with the
    space, Model E's only with the hypotheses (spec Level C / section 24)."""
    small, big = 5 * 7 * 11 * 13 * 99991, 5 * 7 * 11 * 13 * 999999937
    d_small, d_big = run(MODEL_D, small, mode="off"), run(MODEL_D, big, mode="off")
    e_small, e_big = run(MODEL_E, small, mode="off"), run(MODEL_E, big, mode="off")
    m = lambda outcome, key: outcome.metadata["runtime_metrics"][key]  # noqa: E731
    space_growth = m(e_big, "candidate_space_estimated_size") - m(e_small, "candidate_space_estimated_size")
    tests_growth = m(e_big, "hypothesis_test_count") - m(e_small, "hypothesis_test_count")
    assert space_growth > 50 * tests_growth
    assert m(e_big, "candidate_materialized_count") == m(e_big, "relation_filter_rows_scanned") == 0
    d_growth = m(d_big, "allocation_count") - m(d_small, "allocation_count")
    e_growth = m(e_big, "allocation_count") - m(e_small, "allocation_count")
    assert d_growth > 5 * space_growth
    assert e_growth < tests_growth + 64
    assert m(e_big, "vm_instruction_count") < m(d_big, "vm_instruction_count") / 10
