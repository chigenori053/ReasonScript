"""Rust production acceptance tests for Relation / State Runtime v0.1."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from frontend.computation_ir import lower_program, validate_program
from frontend.computation_ir.optimizer import optimize_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.language_surface import parse
from frontend.language_surface.parser import SurfaceSyntaxError

ROOT = Path(__file__).resolve().parents[1]
HOST = find_binary()
pytestmark = pytest.mark.skipif(HOST is None, reason="native runtime host is not built")


def execute(body: str, *, mode: str = "delta", declarations: str = "", **config):
    source = f"""module M {{
      struct Row {{
        value: int
      }}
      {declarations}
      calculation Answer {{
        {body}
      }}
    }}"""
    ir = optimize_program(lower_program(parse(source)))
    assert validate_program(ir) == []
    outcome = run_ir(ir, binary=HOST, trace_enabled=True,
                     trace_config={"mode": mode, **config}, limits={"max_loop_iterations": 100_000})
    assert outcome.ok, (outcome.error_code, outcome.error_message)
    return outcome


@pytest.mark.parametrize("predicate, expected", [
    ("row.value > 10", 2),
    ("candidate.value > threshold", 2),
    ("row.value % factor != 0", 1),
    ("row.value > minimum && row.value < maximum && row.value % factor != 0", 1),
    ("!(row.value / 2 < 5.0) || row.value + 1 == 6", 4),
    ("row.value * 2 - 1 >= 21", 2),
])
def test_expression_predicates(predicate, expected):
    result = execute(f"""
        let rows = [Row {{ value: 5 }}, Row {{ value: 10 }}, Row {{ value: 11 }}, Row {{ value: 15 }}]
        let threshold = 10
        let factor = 5
        let minimum = 5
        let maximum = 15
        result = relation.count(relation.filter(rows, {predicate}))
    """)
    assert result.calculation_results == {"Answer": expected}
    assert result.metadata["runtime_metrics"]["relation_rows_scanned"] == 4


def test_predicate_captures_changing_variables_parameters_and_state_fields():
    result = execute("""
        let rows = [Row { value: 3 }, Row { value: 5 }, Row { value: 6 }, Row { value: 10 }]
        let factor = 3
        let first = Prune(rows, factor)
        factor = 5
        let state = Row { value: factor }
        let second = relation.filter(first, candidate.value % state.value != 0)
        result = second.length
    """, declarations="""
        fn Prune(rows: [Row], factor: int) -> [Row] {
            return relation.filter(rows, row.value % factor != 0)
        }
    """)
    assert result.calculation_results == {"Answer": 0}
    events = result.metadata["reasoning_trace"]
    assert [event["affected_entities"] for event in events] == [[0, 2], [0, 1]]
    assert [event["reasoning_step_id"] for event in events] == [1, 2]


@pytest.mark.parametrize("predicate, code", [
    ("row.value + 1", "REL-PRED-003"),
    ("print(row.value) == null", "REL-PRED-002"),
    ("relation.count(rows) > 0", "REL-PRED-002"),
    ("row.value > other.value", "REL-PRED-001"),
])
def test_invalid_predicates_are_rejected_before_execution(predicate, code):
    with pytest.raises(SurfaceSyntaxError, match=code):
        parse(f"""module M {{
          struct Row {{
            value: int
          }}
          calculation Answer {{
            let rows = [Row {{ value: 1 }}]
            result = relation.filter(rows, {predicate})
          }}
        }}""")


def test_native_predicate_rejects_forged_side_effect_ir_even_on_empty_rows():
    ir = lower_program(parse("""module M {
        struct Row {
            value: int
        }
        calculation Answer {
            let rows = [Row { value: 1 }]
            result = relation.filter(rows, row.value > 0)
        }
    }"""))
    predicate = ir["functions"][0]["blocks"][0]["terminator"]["value"]
    predicate["predicate"] = {"op": "call_console", "function_id": "print", "arguments": []}
    ir["functions"][0]["blocks"][0]["instructions"][0]["expr"]["elements"] = []
    result = run_ir(ir, binary=HOST)
    assert not result.ok
    assert result.error_code == "REL-PRED-002"
    assert result.console_output == []


def test_builder_constructs_ten_thousand_rows_without_full_copies():
    result = execute("""
        let builder = array.builder()
        let i = 0
        while i < 10000 {
            builder.append(Row { value: i })
            i = i + 1
        }
        let rows = builder.finish()
        result = rows[9999].value + rows.length
    """, mode="off")
    assert result.calculation_results == {"Answer": 19999}
    assert result.metadata["runtime_metrics"]["builder_appends"] == 10000
    assert result.metadata["runtime_metrics"]["builder_full_copies"] == 0
    assert result.metadata["loop_trace"] == []


def test_builder_snapshots_each_item_and_aliases_share_finish_lifetime():
    result = execute("""
        let builder = array.builder()
        let alias = builder
        let row = Row { value: 7 }
        builder.append(row)
        row.value = 99
        let rows = alias.finish()
        result = rows[0].value
    """)
    assert result.calculation_results == {"Answer": 7}
    ir = lower_program(parse("""module M {
        calculation Answer {
            let b = array.builder()
            let alias = b
            b.append(1)
            let rows = b.finish()
            alias.append(2)
            result = rows.length
        }
    }"""))
    result = run_ir(ir, binary=HOST)
    assert not result.ok
    assert result.error_code == "COLL-005"


def test_finishing_builder_inside_an_append_argument_is_a_diagnostic():
    ir = lower_program(parse("""module M {
        calculation Answer {
            let b = array.builder()
            b.append(b.finish())
            result = 0
        }
    }"""))
    result = run_ir(ir, binary=HOST)
    assert not result.ok
    assert result.error_code == "COLL-005"


def test_empty_and_unchanged_filters_do_not_create_semantic_steps():
    result = execute("""
        let rows = [Row { value: 1 }]
        let first = relation.filter(rows, row.value > 0)
        let empty = relation.filter(rows, row.value < 0)
        let still_empty = relation.filter(empty, row.value > 0)
        result = first.length + still_empty.length
    """)
    assert result.calculation_results == {"Answer": 1}
    assert len(result.metadata["reasoning_trace"]) == 1
    assert result.metadata["runtime_metrics"]["semantic_reasoning_steps"] == 1


def test_explicit_reason_units_preserve_results_and_add_layers_incrementally():
    ir = lower_program(parse("""module M {
        calculation Answer {
            reasoning.event("HYPOTHESIS_VERIFIED", 11, true)
            reasoning.event("STATE_TRANSITION", 77, 7)
            reasoning.event("TERMINATION_INFERRED", 7, true)
            result = 77
        }
    }"""))
    runs = {
        mode: run_ir(ir, binary=HOST, reason_units=mode)
        for mode in ("off", "ru", "ru_rus", "ru_rus_ruo")
    }
    assert {json.dumps(run.calculation_results, sort_keys=True) for run in runs.values()} == {'{"Answer": 77}'}
    traces = {mode: run.metadata["reason_structure_trace"] for mode, run in runs.items()}
    assert traces["off"]["reason_units"] == []
    assert len(traces["ru"]["reason_units"]) == 3
    assert traces["ru"]["reason_unit_states"] == []
    assert len(traces["ru_rus"]["reason_unit_states"]) == 3
    assert traces["ru_rus"]["reason_unit_objects"] == []
    assert len(traces["ru_rus_ruo"]["reason_unit_objects"]) == 3
    assert traces["ru"]["hashes"]["ru_sequence_hash"] == traces["ru_rus_ruo"]["hashes"]["ru_sequence_hash"]


def test_state_reads_are_not_reused_across_mutation_by_optimizer():
    result = execute("""
        let rows = [Row { value: 1 }, Row { value: 3 }]
        let state = Row { value: 2 }
        let before = state.value
        state.value = 4
        let after = state.value
        let kept = relation.filter(rows, row.value < after)
        result = before * 100 + after * 10 + kept.length
    """)
    assert result.calculation_results == {"Answer": 242}


def state_hash(state):
    """Independent reconstruction of the documented incremental hash."""
    accumulator = bytearray(32)

    def visit(path, value):
        marker = {"array_length": len(value)} if isinstance(value, list) else (
            {"object": True} if isinstance(value, dict) else value)
        encoded = json.dumps([path, marker], ensure_ascii=False, separators=(",", ":")).encode()
        digest = hashlib.sha256(encoded).digest()
        for i, byte in enumerate(digest):
            accumulator[i] ^= byte
        children = enumerate(value) if isinstance(value, list) else value.items() if isinstance(value, dict) else []
        for key, child in children:
            visit(path + [str(key)], child)

    for name, value in state.items():
        visit([name], value)
    return "sha256-xor-leaves/1:" + hashlib.sha256(accumulator).hexdigest()


def replay(state, changes):
    for change in changes:
        parts = [part.replace("~1", "/").replace("~0", "~") for part in change["path"].split("/")[1:]]
        owner = state
        for part in parts[:-1]:
            owner = owner[int(part)] if isinstance(owner, list) else owner[part]
        key = int(parts[-1]) if isinstance(owner, list) else parts[-1]
        operation = change["operation"]
        if operation in {"remove", "replace"}:
            assert owner[key] == change["old"]
        if operation == "remove":
            if isinstance(owner, list):
                owner.pop(key)
            else:
                del owner[key]
        elif operation == "add" and isinstance(owner, list):
            owner.insert(key, copy.deepcopy(change["new"]))
        else:
            owner[key] = copy.deepcopy(change["new"])


def verify_trace(events):
    states = {}
    parents = {}
    for event in events:
        frame = event["frame_id"]
        if frame in states:
            assert event["parent_event_id"] == parents[frame]
            assert state_hash(states[frame]) == event["previous_state_hash"]
            replay(states[frame], event["changes"])
        else:
            assert event["parent_event_id"] is None
            states[frame] = copy.deepcopy(event["checkpoint"])
        assert state_hash(states[frame]) == event["resulting_state_hash"]
        if "checkpoint" in event:
            assert states[frame] == event["checkpoint"]
        parents[frame] = event["event_id"]
    return states


def test_delta_replays_nested_loops_mutable_aliases_and_suspended_callers():
    result = execute("""
        let rows = [Row { value: 0 }, Row { value: 1 }, Row { value: 2 }]
        let alias = rows
        let i = 0
        while i < 2 {
            let j = 0
            while j < 2 {
                let item = alias[j]
                item.value = item.value + 1
                j = j + 1
            }
            Bump(rows)
            i = i + 1
        }
        rows = relation.filter(rows, row.value > 2)
        result = rows.length
    """, checkpoint_interval=2, declarations="""
        fn Bump(rows: [Row]) -> int {
            let third = rows[2]
            third.value = third.value + 1
            return third.value
        }
    """)
    assert result.calculation_results == {"Answer": 2}
    states = verify_trace(result.metadata["loop_trace"])
    state = next(iter(states.values()))
    assert [row["fields"]["value"] for row in state["rows"]] == [3, 4]
    assert [row["fields"]["value"] for row in state["alias"]] == [2, 3, 4]


def test_large_array_delta_is_compact_and_deterministic():
    values = ", ".join(["0"] * 5000)
    body = f"""
        let values = [{values}]
        let alias = values
        let i = 0
        while i < 300 {{
            alias[i] = i + 1
            i = i + 1
        }}
        result = values[299]
    """
    outcomes = [execute(body, checkpoint_interval=0) for _ in range(3)]
    trace = outcomes[0].metadata["loop_trace"]
    assert all(result.calculation_results == {"Answer": 300} for result in outcomes)
    assert all(result.metadata["loop_trace"] == trace for result in outcomes)
    assert all("previous_state" not in event and "updated_state" not in event for event in trace)
    assert all(not isinstance(change["new"], list) for event in trace for change in event["changes"])
    verify_trace(trace)
    full = execute(body, mode="full")
    assert len(json.dumps(trace)) < len(json.dumps(full.metadata["loop_trace"])) / 10


def test_trace_budget_stops_recording_without_stopping_execution():
    result = execute("""
        let i = 0
        while i < 500 {
            reasoning.event("HYPOTHESIS_VERIFIED", i, true)
            i = i + 1
        }
        result = i
    """, max_bytes=1024)
    assert result.calculation_results == {"Answer": 500}
    assert result.metadata["runtime_metrics"]["trace_bytes"] <= 1024
    assert [diagnostic["code"] for diagnostic in result.metadata["trace_diagnostics"]] == ["TRACE-BUDGET-001"]


def test_sampled_trace_retains_first_periodic_and_last_events():
    result = execute("""
        let i = 0
        while i < 1000 {
            i = i + 1
        }
        result = i
    """, mode="sampled")
    ids = [event["event_id"] for event in result.metadata["loop_trace"]]
    assert ids == sorted(set(range(1, 101)) | set(range(100, 1001, 100)) | set(range(901, 1001)))


def test_semantic_steps_are_independent_of_loop_iterations_and_preserve_evidence():
    result = execute("""
        let i = 0
        while i < 10 {
            i = i + 1
        }
        reasoning.event("HYPOTHESIS_VERIFIED", "factor", Row { value: 3 })
        result = reasoning.event("TERMINATION_INFERRED", "done", true)
    """)
    assert result.calculation_results == {"Answer": 2}
    metrics = result.metadata["runtime_metrics"]
    assert metrics["loop_iterations"] == 10
    assert metrics["semantic_reasoning_steps"] == 2
    assert result.metadata["reasoning_trace"][0]["evidence"] == {"type_name": "Row", "fields": {"value": 3}}


def test_new_trace_and_event_machine_interfaces_validate():
    # The suite already uses jsonschema for schema conformance; keep the
    # native implementation independent of any Python runtime evaluator.
    jsonschema = pytest.importorskip("jsonschema")
    source = (ROOT / "examples/v0_5/009_relation_state_pruning.rsn").read_text()
    outcome = run_ir(lower_program(parse(source)), binary=HOST, trace_enabled=True)
    assert outcome.ok
    delta_schema = json.loads((ROOT / "schemas/state_delta_trace.schema.json").read_text())
    event_schema = json.loads((ROOT / "schemas/semantic_reasoning_event.schema.json").read_text())
    for event in outcome.metadata["loop_trace"]:
        jsonschema.validate(event, delta_schema)
    for event in outcome.metadata["reasoning_trace"]:
        jsonschema.validate(event, event_schema)
    verify_trace(outcome.metadata["loop_trace"])
