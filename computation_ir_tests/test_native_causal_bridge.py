from __future__ import annotations

import json
import subprocess

import pytest

from frontend.computation_ir import lower_program
from frontend.computation_ir.rust_bridge import find_binary
from frontend.language_surface import parse


HOST = find_binary()


def _run_native() -> dict:
    program = lower_program(parse("""module Factorization {
        struct Candidate { value: int }
        calculation Factors {
            let candidates = [Candidate { value: 5 }, Candidate { value: 7 }]
            let factors = relation.filter(candidates, candidate.value == 7)
            reasoning.event("TERMINATION_INFERRED", 7, true)
            result = factors.length
        }
    }"""))
    request = {
        "schema": "reasonscript-runtime-request/1.0",
        "request_id": "native-causal-bridge",
        "operation": "execute",
        "program": program,
        "context": {
            "resource_root": ".",
            "capabilities": {
                "filesystem_read": False,
                "filesystem_write": False,
                "network": False,
            },
            "limits": {},
            "trace": {"enabled": False},
            "numeric_mode": "compat-reference",
            "executable_reason_units": "full",
            "causal_evaluation": "counterfactual",
            "causal_observation_source": "native",
        },
    }
    completed = subprocess.run(
        [str(HOST)], input=json.dumps(request), text=True, capture_output=True
    )
    assert completed.returncode == 0, completed.stdout
    return json.loads(completed.stdout)


@pytest.mark.skipif(HOST is None, reason="reason-runtime-host binary not built")
def test_native_factorization_producer_consumer_cause_and_legacy_projection():
    payload = _run_native()
    assert payload["calculation_results"] == {"Factors": 1}
    bridge = payload["metadata"]["causal_bridge"]
    assert bridge["source"] == "native"
    assert bridge["diagnostics"] == []
    assert bridge["metrics"]["observation_coverage_ratio"] == 1.0
    observations = bridge["observations"]
    assert any(item["produces"] for item in observations)
    assert any(item["requires"] for item in observations)
    assert len(observations) == len(payload["metadata"]["reason_unit_trace"]["reason_units"])
    assert any(unit["source"] == "legacy_reasoning_event" for unit in payload["metadata"]["reason_unit_trace"]["reason_units"])
    relations = payload["metadata"]["causal_trace"]["relations"]
    assert any(item["relation_kind"] == "CAUSES" and item["status"] == "CONFIRMED" for item in relations)
    assert any(item["relation_kind"] == "TEMPORAL" and item["dependency"] is False for item in relations)


@pytest.mark.skipif(HOST is None, reason="reason-runtime-host binary not built")
def test_native_bridge_and_causal_hashes_are_three_run_deterministic():
    runs = [_run_native() for _ in range(3)]
    assert len({run["metadata"]["causal_bridge"]["observation_hash"] for run in runs}) == 1
    assert len({run["metadata"]["causal_trace"]["hashes"]["causal_relation_hash"] for run in runs}) == 1


@pytest.mark.skipif(HOST is None, reason="reason-runtime-host binary not built")
def test_native_source_rejects_disabled_and_count_ru_modes():
    program = lower_program(parse("""module M {
        calculation Answer {
            result = 1
        }
    }"""))
    for mode, code in (("off", "CAUSAL-BRIDGE-007"), ("count", "CAUSAL-BRIDGE-008")):
        request = {
            "schema": "reasonscript-runtime-request/1.0",
            "request_id": "invalid-native-bridge",
            "operation": "execute",
            "program": program,
            "context": {
                "resource_root": ".",
                "capabilities": {},
                "limits": {},
                "trace": {"enabled": False},
                "numeric_mode": "compat-reference",
                "executable_reason_units": mode,
                "causal_evaluation": "dependency",
                "causal_observation_source": "native",
            },
        }
        completed = subprocess.run([str(HOST)], input=json.dumps(request), text=True, capture_output=True)
        assert completed.returncode == 1
        assert json.loads(completed.stdout)["diagnostics"][0]["code"] == code
