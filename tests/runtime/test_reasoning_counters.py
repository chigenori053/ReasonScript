"""P0-1: native runtime counters are measured, present, and consistent."""

from __future__ import annotations

from tests.runtime.conftest import execute

SIEVE = """
    let builder = array.builder()
    let i = 1
    while i <= 30 {
        builder.append(Row { value: i })
        i = i + 1
    }
    let rows = builder.finish()
    let factor = 3
    let kept = relation.filter(rows, row.value % factor != 0)
    let total = relation.count(kept)
    let first = kept[0].value
    reasoning.event("HYPOTHESIS_VERIFIED", "factor", factor)
    reasoning.event("HYPOTHESIS_REJECTED", "candidate", first)
    result = total + first
"""

REQUIRED = [
    "vm_instruction_count", "reasoning_step_count", "reasoning_event_count", "relation_dispatch_count",
    "relation_filter_count", "relation_filter_rows_scanned", "relation_predicate_eval_count",
    "relation_count_count", "array_read_count", "array_write_count", "struct_field_read_count",
    "struct_field_write_count", "allocation_count", "allocated_bytes", "state_transition_count",
    "branch_count", "loop_iteration_count", "runtime_execution_ns", "hypothesis_test_count",
    "candidate_pruned_count", "reasoning_event_type_counts",
    # pre-P0 keys stay for existing consumers
    "loop_iterations", "semantic_reasoning_steps", "builder_appends", "builder_full_copies",
    "relation_rows_scanned", "trace_bytes", "trace_mode",
]


def test_counters_are_present_and_consistent():
    outcome = execute(SIEVE)
    assert outcome.ok, (outcome.error_code, outcome.error_message)
    assert outcome.calculation_results == {"Answer": 21}
    m = outcome.metadata["runtime_metrics"]
    for key in REQUIRED:
        assert key in m, key
    assert m["loop_iteration_count"] == m["loop_iterations"] == 30
    assert m["relation_filter_count"] == 1
    assert m["relation_filter_rows_scanned"] == m["relation_rows_scanned"] == m["relation_predicate_eval_count"] == 30
    assert m["relation_count_count"] == 1
    assert m["relation_dispatch_count"] == 2
    assert m["array_write_count"] == 30  # builder appends
    assert m["array_read_count"] == 1  # kept[0]
    assert m["struct_field_read_count"] == 31  # 30 predicate reads (fast path counts them too) + kept[0].value
    assert m["reasoning_step_count"] == m["semantic_reasoning_steps"] == 3  # 2 explicit + CANDIDATE_PRUNED
    assert m["reasoning_event_count"] == 3
    assert m["reasoning_event_type_counts"] == {"CANDIDATE_PRUNED": 1, "HYPOTHESIS_VERIFIED": 1, "HYPOTHESIS_REJECTED": 1}
    assert m["hypothesis_test_count"] == 2
    assert m["candidate_pruned_count"] == 10
    assert m["vm_instruction_count"] > m["loop_iteration_count"]
    assert m["branch_count"] >= 30
    assert m["state_transition_count"] == 38  # 30 x `i = i + 1` + 8 `let`/`result` bindings
    assert m["allocation_count"] > 0 and m["allocated_bytes"] > 0
    assert m["runtime_execution_ns"] > 0
    assert "predicate_execution_ns" not in m  # only under --profile-runtime


def test_profile_runtime_adds_section_timers():
    outcome = execute(SIEVE, profile_runtime=True)
    m = outcome.metadata["runtime_metrics"]
    for key in ("predicate_execution_ns", "relation_execution_ns", "reasoning_event_ns", "trace_execution_ns"):
        assert key in m, key
    assert m["relation_execution_ns"] >= m["predicate_execution_ns"]


def test_failed_runs_still_report_metrics():
    outcome = execute("""
        let rows = [Row { value: 1 }]
        result = rows[5].value
    """)
    assert outcome.error_code == "RT-INDEX-002"
    assert outcome.metadata["termination_reason"] == "runtime_error"
    assert outcome.metadata["runtime_metrics"]["vm_instruction_count"] > 0
