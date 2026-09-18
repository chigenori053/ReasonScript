"""P0-3/P0-4: the Fast Path and the Generic Path must be indistinguishable
in results, reasoning events, state traces, counters, and diagnostics."""

from __future__ import annotations

import pytest

from tests.runtime.conftest import execute

ROWS = "let rows = [Row { value: 5 }, Row { value: 10 }, Row { value: 11 }, Row { value: 15 }, Row { value: 30 }]"

PREDICATES = [
    "row.value > 10",
    "candidate.value > threshold",
    "row.value % factor != 0",
    "row.value % 5 == 0",
    "row.value > minimum && row.value < maximum && row.value % factor != 0",
    "row.value == 10 || row.value == 15",
    "!(row.value % factor == 0)",
    "row.value % state.value != 0",
    # left as Generic Path: arithmetic other than modulo, float division
    "!(row.value / 2 < 5.0) || row.value + 1 == 6",
    "row.value * 2 - 1 >= 21",
]

TIMING_KEYS = {"fast_path_count", "fast_path_enabled", "runtime_execution_ns", "allocation_count", "allocated_bytes", "peak_live_bytes"}


def both(body: str, mode: str = "delta"):
    fast = execute(body, mode=mode, fast_path=True)
    generic = execute(body, mode=mode, fast_path=False)
    return fast, generic


def comparable(metrics: dict) -> dict:
    return {key: value for key, value in metrics.items() if key not in TIMING_KEYS}


@pytest.mark.parametrize("predicate", PREDICATES)
def test_filter_predicates_match_generic_path(predicate):
    fast, generic = both(f"""
        {ROWS}
        let threshold = 10
        let factor = 5
        let minimum = 5
        let maximum = 15
        let state = Row {{ value: 3 }}
        let kept = relation.filter(rows, {predicate})
        result = relation.count(kept) * 100 + kept.length
    """)
    assert fast.ok and generic.ok, (fast.error_message, generic.error_message)
    assert fast.calculation_results == generic.calculation_results
    assert fast.metadata["reasoning_trace"] == generic.metadata["reasoning_trace"]
    assert fast.metadata["loop_trace"] == generic.metadata["loop_trace"]
    assert comparable(fast.metadata["runtime_metrics"]) == comparable(generic.metadata["runtime_metrics"])
    assert generic.metadata["runtime_metrics"]["fast_path_count"] == 0
    assert fast.metadata["runtime_metrics"]["fast_path_enabled"] is True


def test_fast_path_is_actually_taken_for_simple_predicates():
    fast, _ = both(f"""
        {ROWS}
        let factor = 5
        result = relation.count(relation.filter(rows, row.value % factor != 0))
    """)
    assert fast.calculation_results == {"Answer": 1}
    # 5 predicate rows + 1 relation.count
    assert fast.metadata["runtime_metrics"]["fast_path_count"] == 6


def test_errors_are_identical_on_both_paths():
    body = f"""
        {ROWS}
        let zero = 0
        result = relation.count(relation.filter(rows, row.value % zero != 0))
    """
    fast, generic = both(body, mode="off")
    assert (fast.error_code, fast.error_message) == (generic.error_code, generic.error_message) == (
        "RT-ARITH-001", "division or modulo by zero")


def test_short_circuit_matches_generic_path():
    # The right operand can never be reached on rows where the left decides,
    # so a modulo-by-zero there must not raise on either path.
    fast, generic = both(f"""
        {ROWS}
        let zero = 0
        result = relation.count(relation.filter(rows, row.value > 100 && row.value % zero == 0))
    """, mode="off")
    assert fast.ok and generic.ok
    assert fast.calculation_results == generic.calculation_results == {"Answer": 0}


def test_binding_restores_shadowed_local():
    fast, generic = both("""
        let rows = [Row { value: 1 }, Row { value: 2 }]
        let row = Row { value: 99 }
        let kept = relation.filter(rows, row.value > 1)
        result = row.value * 10 + kept.length
    """)
    assert fast.calculation_results == generic.calculation_results == {"Answer": 991}


def test_relation_count_fast_path_matches_generic():
    fast, generic = both("""
        let rows = [Row { value: 1 }, Row { value: 2 }]
        let empty = relation.filter(rows, row.value > 5)
        result = relation.count(rows) * 10 + relation.count(empty)
    """)
    assert fast.calculation_results == generic.calculation_results == {"Answer": 20}
    assert fast.metadata["runtime_metrics"]["relation_count_count"] == 2
