from __future__ import annotations

import json
import subprocess

import pytest

from frontend.computation_ir import lower_program
from frontend.computation_ir.rust_bridge import find_binary
from frontend.language_surface import parse


HOST = find_binary()


def _run(observations: list[dict], **context: object) -> dict:
    program = lower_program(parse("""module M {
        calculation Answer {
            result = 42
        }
    }"""))
    request = {
        "schema": "reasonscript-runtime-request/1.0",
        "request_id": "causal-test",
        "operation": "execute",
        "program": program,
        "context": {
            "causal_evaluation": "counterfactual",
            "causal_observations": observations,
            "trace": {"enabled": False},
            "resource_root": ".",
            "capabilities": {
                "filesystem_read": False,
                "filesystem_write": False,
                "network": False,
            },
            "numeric_mode": "compat-reference",
            "limits": {},
            **context,
        },
    }
    completed = subprocess.run(
        [str(HOST)], input=json.dumps(request), text=True, capture_output=True
    )
    assert completed.returncode == 0, completed.stdout
    return json.loads(completed.stdout)["metadata"]["causal_trace"]


@pytest.mark.skipif(HOST is None, reason="reason-runtime-host binary not built")
def test_factorization_causal_chain_and_hash_are_deterministic():
    observations = [
        {"ru_id": "Verification(7)", "produces": ["FactorConfirmed(7)"]},
        {
            "ru_id": "RemainingChange",
            "requires": ["FactorConfirmed(7)"],
            "produces": ["SearchBoundChanged"],
        },
        {"ru_id": "Termination", "requires": ["SearchBoundChanged"]},
    ]
    traces = [_run(observations) for _ in range(3)]
    assert len({trace["hashes"]["causal_relation_hash"] for trace in traces}) == 1
    relations = traces[0]["relations"]
    assert any(r["source_ref"] == "Verification(7)" and r["target_ref"] == "RemainingChange" and r["relation_kind"] == "CAUSES" for r in relations)
    assert any(r["source_ref"] == "RemainingChange" and r["target_ref"] == "Termination" and r["relation_kind"] == "CAUSES" for r in relations)
    assert any(r["source_ref"] == "Verification(7)" and r["target_ref"] == "Termination" and r["relation_kind"] == "CAUSES" for r in relations)
    assert traces[0]["metrics"]["counterfactual_run_count"] == 2
    assert traces[0]["metrics"]["normal_runtime_ns"] >= 0


@pytest.mark.skipif(HOST is None, reason="reason-runtime-host binary not built")
def test_temporal_non_dependency_and_prevention_are_not_false_causes():
    trace = _run(
        [
            {"ru_id": "A", "produces": ["unrelated"]},
            {"ru_id": "B"},
            {"ru_id": "Reject", "produces": ["blocked"]},
            {"ru_id": "Action", "blocked_by": ["blocked"], "success": False},
        ]
    )
    assert any(r["source_ref"] == "A" and r["target_ref"] == "B" and r["relation_kind"] == "TEMPORAL" and r["dependency"] is False for r in trace["relations"])
    assert any(r["source_ref"] == "Reject" and r["target_ref"] == "Action" and r["relation_kind"] == "PREVENTS" and r["status"] == "CONFIRMED" for r in trace["relations"])


@pytest.mark.skipif(HOST is None, reason="reason-runtime-host binary not built")
def test_counterfactual_budget_and_missing_producer_diagnostics():
    trace = _run(
        [
            {"ru_id": "A", "produces": ["E"]},
            {"ru_id": "B", "requires": ["E", "missing"]},
        ],
        max_counterfactual_runs=0,
    )
    assert "CAUSAL-003" in trace["diagnostics"]
    assert "CAUSAL-BUDGET-001" in trace["diagnostics"]
    assert any(relation["status"] == "INSUFFICIENT" for relation in trace["relations"])
