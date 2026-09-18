"""P0-5: reasoning.event OFF / COUNT / FULL and lazy materialization."""

from __future__ import annotations

from tests.runtime.conftest import execute

EVENTS = """
    let rows = [Row { value: 2 }, Row { value: 3 }, Row { value: 4 }]
    let step = reasoning.event("HYPOTHESIS_VERIFIED", "factor", 2)
    let kept = relation.filter(rows, row.value % 2 != 0)
    let last = reasoning.event("TERMINATION_INFERRED", "prime", 3)
    result = step * 10 + last
"""


def test_off_records_nothing_and_returns_step_zero():
    outcome = execute(EVENTS, mode="delta", reasoning_event_mode="off")
    assert outcome.calculation_results == {"Answer": 0}
    m = outcome.metadata["runtime_metrics"]
    assert m["reasoning_step_count"] == m["reasoning_event_count"] == 0
    assert m["reasoning_event_type_counts"] == {}
    assert outcome.metadata["reasoning_trace"] == []
    assert m["reasoning_event_mode"] == "off"


def test_count_keeps_counters_but_builds_no_events():
    outcome = execute(EVENTS, mode="delta", reasoning_event_mode="count")
    assert outcome.calculation_results == {"Answer": 13}
    m = outcome.metadata["runtime_metrics"]
    assert m["reasoning_step_count"] == 3
    assert m["reasoning_event_type_counts"] == {"CANDIDATE_PRUNED": 1, "HYPOTHESIS_VERIFIED": 1, "TERMINATION_INFERRED": 1}
    assert m["candidate_pruned_count"] == 2
    assert outcome.metadata["reasoning_trace"] == []
    # the state trace itself is unaffected by the event mode
    full = execute(EVENTS, mode="delta", reasoning_event_mode="full")
    assert outcome.metadata["loop_trace"] == full.metadata["loop_trace"]


def test_full_matches_the_pre_p0_trace_payload():
    outcome = execute(EVENTS, mode="delta", reasoning_event_mode="full")
    events = outcome.metadata["reasoning_trace"]
    assert [event["event_type"] for event in events] == ["HYPOTHESIS_VERIFIED", "CANDIDATE_PRUNED", "TERMINATION_INFERRED"]
    assert events[1]["affected_entities"] == [0, 2]
    assert events[1]["metadata"] == {"before_count": 3, "after_count": 1, "removed_count": 2}
    assert [event["reasoning_step_id"] for event in events] == [1, 2, 3]
    assert outcome.metadata["runtime_metrics"]["reasoning_event_mode"] == "full"


def test_defaults_follow_trace_mode():
    with_trace = execute(EVENTS, mode="delta")
    without_trace = execute(EVENTS, mode="off")
    assert with_trace.metadata["runtime_metrics"]["reasoning_event_mode"] == "full"
    assert without_trace.metadata["runtime_metrics"]["reasoning_event_mode"] == "count"
    assert without_trace.metadata["reasoning_trace"] == []
    assert without_trace.metadata["runtime_metrics"]["reasoning_step_count"] == 3


def test_semantic_events_disabled_is_off():
    outcome = execute(EVENTS, mode="delta", semantic_events=False)
    assert outcome.calculation_results == {"Answer": 0}
    assert outcome.metadata["runtime_metrics"]["reasoning_event_mode"] == "off"


def test_invalid_mode_is_a_protocol_error():
    outcome = execute(EVENTS, reasoning_event_mode="verbose")
    assert outcome.error_code == "RTH-PROTO-005"


def test_summary_trace_mode_is_off_plus_counts():
    outcome = execute(EVENTS, mode="summary")
    assert outcome.ok
    m = outcome.metadata["runtime_metrics"]
    assert m["trace_mode"] == "off"
    assert m["reasoning_event_type_counts"]["HYPOTHESIS_VERIFIED"] == 1
    assert outcome.metadata["loop_trace"] == [] and outcome.metadata["reasoning_trace"] == []
