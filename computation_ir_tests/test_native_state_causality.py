from __future__ import annotations

import json
import subprocess

import pytest

from frontend.computation_ir import lower_program
from frontend.computation_ir.rust_bridge import find_binary
from frontend.language_surface import parse


HOST = find_binary()


def _run() -> dict:
    program = lower_program(parse("""module Factorization {
        struct Candidate { value: int }
        calculation Factors {
            let candidates = [Candidate { value: 5 }, Candidate { value: 7 }]
            let factors = relation.filter(candidates, candidate.value == 7)
            result = factors.length
        }
    }"""))
    request = {
        "schema": "reasonscript-runtime-request/1.0",
        "request_id": "native-state-causality",
        "operation": "execute",
        "program": program,
        "context": {
            "resource_root": ".",
            "capabilities": {},
            "limits": {},
            "trace": {"enabled": False},
            "numeric_mode": "compat-reference",
            "executable_reason_units": "full",
            "causal_evaluation": "counterfactual",
            "causal_observation_source": "native",
            "state_causality": "full",
        },
    }
    completed = subprocess.run(
        [str(HOST)], input=json.dumps(request), text=True, capture_output=True
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


@pytest.mark.skipif(HOST is None, reason="reason-runtime-host binary not built")
def test_factorization_state_chain_is_derived_from_runtime_execution():
    payload = _run()
    assert payload["calculation_results"] == {"Factors": 1}
    state = payload["metadata"]["state_causality"]
    assert state["diagnostics"] == []
    assert state["metrics"]["state_transition_count"] == 4
    assert state["metrics"]["state_transition_coverage"] == 1.0
    assert state["metrics"]["state_evidence_coverage"] == 1.0
    fields = [transition["changed_fields"] for transition in state["transitions"]]
    assert ["current_candidate"] in fields
    assert ["active_constraint_count"] in fields
    assert ["goal_status"] in fields
    assert all(transition["source_ru"] for transition in state["transitions"])
    kinds = {relation["relation_kind"] for relation in state["relations"]}
    assert {"CAUSES_STATE_CHANGE", "ENABLES", "TERMINATES"} <= kinds
    assert {"CAUSES_STATE_CHANGE", "ENABLES", "TERMINATES"} <= {
        relation["relation_kind"]
        for relation in payload["metadata"]["causal_trace"]["relations"]
    }


@pytest.mark.skipif(HOST is None, reason="reason-runtime-host binary not built")
def test_rejected_verification_does_not_create_factor_state_change():
    payload = _run()
    trace = payload["metadata"]["reason_unit_trace"]
    rejected = {
        unit["id"]
        for unit in trace["reason_units"]
        if unit["terminal_status"] == "REJECTED"
    }
    active_constraint_sources = {
        transition["source_ru"]
        for transition in payload["metadata"]["state_causality"]["transitions"]
        if "active_constraint_count" in transition["changed_fields"]
    }
    assert rejected.isdisjoint(active_constraint_sources)


@pytest.mark.skipif(HOST is None, reason="reason-runtime-host binary not built")
def test_state_observation_and_causal_hashes_are_three_run_deterministic():
    runs = [_run() for _ in range(3)]
    assert len({run["metadata"]["state_causality"]["hashes"]["state_transition_hash"] for run in runs}) == 1
    assert len({run["metadata"]["causal_bridge"]["observation_hash"] for run in runs}) == 1
    assert len({run["metadata"]["causal_trace"]["hashes"]["causal_relation_hash"] for run in runs}) == 1
