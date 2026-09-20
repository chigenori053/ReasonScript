"""Lightweight RUS v0.1: runtime-owned reasoning state, end to end.

Every input is ReasonScript source + N + runtime context. Transitions, revisions,
state values and causal relations are never supplied by the tests; they are
checked against an independent Python model of the reasoning (`oracle`).
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from math import isqrt, prod
from pathlib import Path

import pytest

from frontend.computation_ir import lower_program
from frontend.computation_ir.rust_bridge import find_binary
from frontend.language_surface import parse

HOST = find_binary()
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TEMPLATE = (HERE / "golden_reasoning_state" / "factorize.rsn.template").read_text(encoding="utf-8")
GOLDEN = json.loads((HERE / "golden_reasoning_state" / "golden.json").read_text(encoding="utf-8"))
pytestmark = pytest.mark.skipif(HOST is None, reason="reason-runtime-host binary not built")

CONTEXT = {
    "resource_root": ".",
    "capabilities": {},
    "limits": {},
    "trace": {"enabled": False},
    "numeric_mode": "compat-reference",
    **GOLDEN["context"],
}


def request(source: str, **context) -> dict:
    return {
        "schema": "reasonscript-runtime-request/1.0",
        "request_id": "reasoning-state",
        "operation": "execute",
        "program": lower_program(parse(source)),
        "context": {**CONTEXT, **context},
    }


def execute(source: str, *, expect_ok: bool = True, **context) -> dict:
    completed = subprocess.run(
        [str(HOST)], input=json.dumps(request(source, **context)), text=True, capture_output=True
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is expect_ok, completed.stdout + completed.stderr
    return payload


def factorize(n: int, **context) -> dict:
    return execute(TEMPLATE.replace("__N__", str(n)), **context)


MINIMAL = "module M {\n  calculation R {\n    result = 1\n  }\n}"


def events(body: str, **context) -> dict:
    lines = "\n".join(f"    {line}" for line in body.splitlines())
    return execute(f"module M {{\n  calculation R {{\n{lines}\n    result = 1\n  }}\n}}", **context)


def state(payload: dict) -> dict:
    return payload["metadata"]["reasoning_state"]


def transitions(payload: dict) -> list[dict]:
    return payload["metadata"]["state_causality"]["transitions"]


def relations(payload: dict, kind: str) -> list[dict]:
    return [r for r in payload["metadata"]["state_causality"]["relations"] if r["relation_kind"] == kind]


def units(payload: dict) -> dict[str, dict]:
    return {u["id"]: u for u in payload["metadata"]["reason_unit_trace"]["reason_units"]}


def evidence(payload: dict) -> dict[str, dict]:
    return {e["id"]: e for e in payload["metadata"]["reason_unit_trace"]["evidence"]}


def factors(payload: dict) -> list[int]:
    return [int(e["message"].split()[1]) for e in payload["console_output"]]


def oracle(n: int) -> dict:
    """Independent trial-division model of the state the runtime must derive."""
    remaining, bound, candidate, current = n, isqrt(n), 2, None
    sequence, found, steps, enabled = [], [], [], []
    while candidate * candidate <= remaining:
        if current != candidate:
            sequence.append(["current_candidate"])
            current = candidate
        if remaining % candidate == 0:
            new = remaining // candidate
            sequence.append(
                [name for name, old, now in (("remaining", remaining, new), ("search_bound", bound, isqrt(new))) if old != now]
            )
            steps.append({"factor": candidate, "remaining": [remaining, new], "search_bound": [bound, isqrt(new)]})
            enabled.append("HYPOTHESIS" if candidate * candidate <= new else "GOAL_EVALUATION")
            found.append(candidate)
            remaining, bound = new, isqrt(new)
        else:
            candidate += 1
    if remaining > 1:
        found.append(remaining)
    sequence.append(["goal_status"])
    return {
        "n": n,
        "factors": found,
        "revision_count": len(sequence),
        "changed_field_sequence": sequence,
        "final_state": {
            "remaining": remaining,
            "search_bound": bound,
            "current_candidate": current,
            "active_constraint_count": 0,
            "goal_status": "REACHED",
        },
        "factor_steps": steps,
        "enables_after_factor": enabled,
    }


def state_hash(revision: int, fields: dict) -> str:
    canonical = {"revision": revision, "fields": dict(sorted(fields.items()))}
    return "sha256:" + hashlib.sha256(json.dumps(canonical, separators=(",", ":")).encode()).hexdigest()


# --- Group A: initialization -------------------------------------------------


def test_group_a_initial_state_is_revision_zero_without_transition():
    payload = events('reasoning.event("REASON_STATE_CREATED", 77, "factorization")')
    assert transitions(payload) == []
    assert state(payload)["revision"] == 0
    assert state(payload)["fields"] == {
        "remaining": 77,
        "search_bound": 8,
        "current_candidate": None,
        "active_constraint_count": 0,
        "goal_status": "ACTIVE",
    }
    assert state(payload)["hash"] == state(payload)["initial_hash"]


def test_reasoning_state_defaults_to_off_and_ignores_events():
    payload = factorize(77, state_causality="off")
    assert state(payload)["mode"] == "off"
    assert state(payload)["revision"] == 0
    assert state(payload)["fields"]["remaining"] is None
    assert payload["metadata"]["state_causality"]["mode"] == "off"


def test_lightweight_state_runs_without_state_causality_and_matches_full_mode():
    alone = factorize(77, state_causality="off", reasoning_state="lightweight")
    full = factorize(77)
    assert state(alone)["mode"] == "lightweight"
    assert state(alone)["hash"] == state(full)["hash"]
    assert transitions(alone) == [] and alone["metadata"]["state_causality"]["relations"] == []


def test_configuration_errors():
    def failure(**context):
        payload = execute(MINIMAL, expect_ok=False, **context)
        return payload["diagnostics"][0]["code"]

    assert failure(state_causality="off", reasoning_state="lightweight", executable_reason_units="off") == "RUS-005"
    assert failure(state_causality="off", reasoning_state="lightweight", executable_reason_units="count") == "RUS-005"
    assert failure(reasoning_state="sometimes") == "RTH-PROTO-004"
    assert failure(state_causality="trace", executable_reason_units="count") == "STATE-CAUSAL-001"


# --- Groups B-D at program level: atomic update and no-op ---------------------


def test_groups_b_c_d_single_atomic_and_noop_updates_from_real_execution():
    payload = factorize(84)
    by_fields = [t["changed_fields"] for t in transitions(payload)]
    assert ["current_candidate"] in by_fields
    assert by_fields.count(["remaining", "search_bound"]) == 3
    # atomic: remaining and search_bound of one factor share one transition / revision
    first = next(t for t in transitions(payload) if "remaining" in t["changed_fields"])
    assert (first["before_values"], first["after_values"]) == (
        {"remaining": 84, "search_bound": 9},
        {"remaining": 42, "search_bound": 6},
    )
    assert first["revision_after"] == first["revision_before"] + 1
    # 2 is re-adopted twice and TERMINATION_INFERRED repeats REACHED: no-ops
    assert state(payload)["metrics"]["reasoning_state_noop_update_count"] == 3
    assert state(payload)["revision"] == len(transitions(payload)) == 6
    revisions = [(t["revision_before"], t["revision_after"]) for t in transitions(payload)]
    assert revisions == [(i, i + 1) for i in range(6)]


# --- Groups E-F: provenance ---------------------------------------------------


def test_groups_e_f_every_transition_has_a_real_source_ru_and_factor_evidence():
    payload = factorize(77)
    known_units, known_evidence = units(payload), evidence(payload)
    for transition in transitions(payload):
        assert transition["source_ru"] in known_units
        assert all(ref in known_evidence for ref in transition["evidence_refs"])
    confirmed = next(t for t in transitions(payload) if "remaining" in t["changed_fields"])
    kinds = {known_evidence[ref]["kind"] for ref in confirmed["evidence_refs"]}
    assert kinds == {"FACTOR_CONFIRMED"}
    assert all(known_evidence[ref]["source_ru"] == confirmed["source_ru"] for ref in confirmed["evidence_refs"])
    # Candidate adoption via legacy events has no Evidence; coverage reports that honestly.
    coverage = payload["metadata"]["state_causality"]["metrics"]
    assert coverage["state_transition_coverage"] == 1.0
    assert 0 < coverage["state_evidence_coverage"] < 1.0


# --- Groups G-K, P: the real factorization of 77 ------------------------------


def test_groups_g_h_i_j_real_factorization_of_77():
    payload = factorize(77)
    assert factors(payload) == [7, 11]
    assert payload["calculation_results"] == {"Result": 11}
    remaining = [t for t in transitions(payload) if "remaining" in t["changed_fields"]]
    assert len(remaining) == 1
    assert remaining[0]["changed_fields"] == ["remaining", "search_bound"]
    assert remaining[0]["before_values"] == {"remaining": 77, "search_bound": 8}
    assert remaining[0]["after_values"] == {"remaining": 11, "search_bound": 3}
    assert state(payload)["fields"] == {
        "remaining": 11,
        "search_bound": 3,
        "current_candidate": 7,
        "active_constraint_count": 0,
        "goal_status": "REACHED",
    }
    # the program's own variable and the runtime source of truth agree
    assert payload["calculation_results"]["Result"] == state(payload)["fields"]["remaining"]


def test_group_k_and_p_full_causal_chain_for_the_semiprime():
    payload = factorize(77)
    known_units, known_evidence = units(payload), evidence(payload)
    ordered = transitions(payload)
    remaining = next(t for t in ordered if "remaining" in t["changed_fields"])
    verification = known_units[remaining["source_ru"]]
    assert (verification["kind"], verification["terminal_status"], verification["subject"]) == ("VERIFICATION", "VERIFIED", 7)
    produced = [
        r for r in payload["metadata"]["reason_unit_trace"]["relations"]
        if r["kind"] == "PRODUCES" and r["source_ref"] == verification["id"]
    ]
    assert [known_evidence[r["target_ref"]]["kind"] for r in produced] == ["FACTOR_CONFIRMED"]
    assert [r["target_ref"] for r in produced] == remaining["evidence_refs"]
    assert [relation["source_ref"] for relation in relations(payload, "CAUSES_STATE_CHANGE") if relation["target_ref"] == remaining["id"]] == [verification["id"]]
    (enabled,) = [r for r in relations(payload, "ENABLES") if r["source_ref"] == remaining["id"]]
    assert known_units[enabled["target_ref"]]["kind"] == "GOAL_EVALUATION"
    goal = next(t for t in ordered if "goal_status" in t["changed_fields"])
    assert ordered.index(goal) > ordered.index(remaining)
    assert known_units[goal["source_ru"]]["kind"] == "GOAL_EVALUATION"
    (terminates,) = relations(payload, "TERMINATES")
    assert terminates["source_ref"] == goal["id"]
    assert known_units[terminates["target_ref"]]["kind"] == "TERMINATION_CHECK"
    # minimal: one factor update, one goal update, one termination (plus candidate adoption)
    assert [t["changed_fields"] for t in ordered].count(["remaining", "search_bound"]) == 1
    assert [t["changed_fields"] for t in ordered].count(["goal_status"]) == 1
    # the same relations are merged into the causal trace, with revision provenance
    merged = {(r["source_ref"], r["target_ref"], r["relation_kind"]) for r in payload["metadata"]["causal_trace"]["relations"]}
    for relation in payload["metadata"]["state_causality"]["relations"]:
        assert (relation["source_ref"], relation["target_ref"], relation["relation_kind"]) in merged
    provenance = relations(payload, "CAUSES_STATE_CHANGE")[-1]["provenance"]
    assert provenance["changed_fields"] == ["goal_status"]
    assert provenance["state_revision_after"] == provenance["state_revision_before"] + 1


# --- Group L: rejected factors ------------------------------------------------


def test_group_l_rejected_candidates_never_update_remaining_or_confirm_a_factor():
    payload = factorize(77)
    known_units, known_evidence = units(payload), evidence(payload)
    rejected = {uid for uid, unit in known_units.items() if unit["terminal_status"] == "REJECTED"}
    assert len(rejected) == 5  # 2..6
    assert rejected.isdisjoint({t["source_ru"] for t in transitions(payload)})
    confirmed_sources = {e["source_ru"] for e in known_evidence.values() if e["kind"] == "FACTOR_CONFIRMED"}
    assert rejected.isdisjoint(confirmed_sources)
    assert {t["source_ru"] for t in transitions(payload) if "remaining" in t["changed_fields"]} == confirmed_sources


def test_inconsistent_verification_is_diagnosed_and_does_not_touch_remaining():
    payload = events(
        'reasoning.event("REASON_STATE_CREATED", 77, "factorization")\n'
        'reasoning.event("HYPOTHESIS_VERIFIED", 5, true)'
    )
    assert state(payload)["diagnostics"] == ["RUS-003"]
    assert state(payload)["fields"]["remaining"] == 77
    assert state(payload)["revision"] == 0


def test_reinitializing_after_a_transition_is_rejected():
    payload = events(
        'reasoning.event("REASON_STATE_CREATED", 77, "factorization")\n'
        'reasoning.event("HYPOTHESIS_CREATED", 7, 77)\n'
        'reasoning.event("REASON_STATE_CREATED", 12, "factorization")'
    )
    assert state(payload)["diagnostics"] == ["RUS-004"]
    assert (state(payload)["revision"], state(payload)["fields"]["remaining"]) == (1, 77)


# --- Group M: determinism -----------------------------------------------------


def test_group_m_hashes_are_three_run_deterministic():
    runs = [factorize(84) for _ in range(3)]
    fingerprints = {
        (
            state(run)["hash"],
            run["metadata"]["state_causality"]["hashes"]["state_transition_hash"],
            run["metadata"]["causal_bridge"]["observation_hash"],
            run["metadata"]["causal_trace"]["hashes"]["causal_relation_hash"],
        )
        for run in runs
    }
    assert len(fingerprints) == 1
    assert all(len(value) == 71 for value in next(iter(fingerprints)))


def test_state_hash_is_canonical_and_history_replays_from_artifacts_alone():
    payload = factorize(84)
    fields = {"remaining": 84, "search_bound": 9, "current_candidate": None, "active_constraint_count": 0, "goal_status": "ACTIVE"}
    assert state(payload)["initial_hash"] == state_hash(0, fields)
    revision = 0
    for transition in transitions(payload):
        assert transition["revision_before"] == revision
        for name, before in transition["before_values"].items():
            assert fields[name] == before
        fields |= transition["after_values"]
        revision = transition["revision_after"]
    assert (revision, fields) == (state(payload)["revision"], state(payload)["fields"])
    assert state_hash(revision, fields) == state(payload)["hash"]


# --- Groups N-O and the golden dataset ----------------------------------------


def assert_matches(payload: dict, expected: dict) -> None:
    assert factors(payload) == expected["factors"]
    assert state(payload)["revision"] == expected["revision_count"]
    assert [t["changed_fields"] for t in transitions(payload)] == expected["changed_field_sequence"]
    assert state(payload)["fields"] == expected["final_state"]
    assert state(payload)["diagnostics"] == payload["metadata"]["state_causality"]["diagnostics"] == []
    known_units = units(payload)
    factor_transitions = [t for t in transitions(payload) if "remaining" in t["changed_fields"]]
    assert [(known_units[t["source_ru"]]["subject"], [t["before_values"]["remaining"], t["after_values"]["remaining"]]) for t in factor_transitions] == [
        (step["factor"], step["remaining"]) for step in expected["factor_steps"]
    ]
    # the next reasoning RU enabled by each factor update (first ENABLES target)
    first_enabled = [
        known_units[next(r for r in relations(payload, "ENABLES") if r["source_ref"] == t["id"])["target_ref"]]["kind"]
        for t in factor_transitions
    ]
    assert first_enabled == expected["enables_after_factor"]


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda case: f"N={case['n']}")
def test_golden_dataset_matches_runtime_and_the_independent_oracle(case):
    assert oracle(case["n"]) == case
    payload = factorize(case["n"])
    assert_matches(payload, case)
    assert prod(case["factors"]) == case["n"]


def test_golden_inputs_contain_no_hand_written_state():
    assert set(GOLDEN["context"]) == {
        "executable_reason_units", "causal_evaluation", "causal_observation_source", "state_causality",
    }
    assert set(GOLDEN["cases"][0]) >= {"n", "factors", "revision_count", "changed_field_sequence", "final_state"}
    assert "reasoning.event" in TEMPLATE and "StateTransition" not in TEMPLATE and "causal_observations" not in json.dumps(CONTEXT)


def test_group_n_multiple_factors_have_ordered_revisions():
    payload = factorize(84)
    assert factors(payload) == [2, 2, 3, 7]
    assert [t["after_values"]["remaining"] for t in transitions(payload) if "remaining" in t["changed_fields"]] == [42, 21, 7]
    assert [t["after_values"]["search_bound"] for t in transitions(payload) if "remaining" in t["changed_fields"]] == [6, 4, 2]


def test_group_o_prime_makes_no_remaining_update():
    payload = factorize(97)
    assert factors(payload) == [97]
    assert not any("remaining" in t["changed_fields"] for t in transitions(payload))
    assert state(payload)["fields"]["remaining"] == 97 and state(payload)["fields"]["goal_status"] == "REACHED"


@pytest.mark.parametrize("n", range(2, 90))
def test_runtime_state_equals_independent_oracle_for_every_small_n(n):
    payload = factorize(n)
    assert_matches(payload, oracle(n))


# --- Native relation.filter path (migrated off manual state hooks) ------------


def test_relation_filter_with_a_real_divisibility_predicate_drives_state_natively():
    payload = execute(
        """module Factorization {
            struct Candidate { value: int }
            calculation Factors {
                let n = 77
                let candidates = [Candidate { value: 2 }, Candidate { value: 5 }, Candidate { value: 7 }, Candidate { value: 8 }]
                let factors = relation.filter(candidates, n % candidate.value == 0)
                result = factors.length
            }
        }"""
    )
    assert payload["calculation_results"] == {"Factors": 1}
    sequence = [t["changed_fields"] for t in transitions(payload)]
    # rows are processed in order: 7 is accepted (constraint) before 8 is adopted
    assert sequence == [["current_candidate"]] * 3 + [["active_constraint_count"], ["current_candidate"], ["goal_status"]]
    assert state(payload)["fields"]["active_constraint_count"] == 1
    assert state(payload)["fields"]["goal_status"] == "REACHED"
    known_units = units(payload)
    assert known_units[transitions(payload)[-1]["source_ru"]]["kind"] == "GOAL_EVALUATION"
    assert relations(payload, "TERMINATES") and relations(payload, "ENABLES")


def test_filter_without_accepted_rows_creates_no_goal_or_termination():
    payload = execute(
        """module Factorization {
            struct Candidate { value: int }
            calculation Factors {
                let candidates = [Candidate { value: 2 }, Candidate { value: 5 }]
                result = relation.filter(candidates, 77 % candidate.value == 0).length
            }
        }"""
    )
    assert payload["calculation_results"] == {"Factors": 0}
    assert [t["changed_fields"] for t in transitions(payload)] == [["current_candidate"]] * 2
    assert state(payload)["fields"]["goal_status"] == "ACTIVE"
    assert relations(payload, "TERMINATES") == []


# --- Hash / artifact compatibility with the pre-optimization runtime ---------------

R0_DIGESTS = json.loads((HERE / "golden_reasoning_state" / "r0_digests.json").read_text(encoding="utf-8"))


def without_timing(value):
    """The response minus wall-clock fields."""
    if isinstance(value, dict):
        return {k: without_timing(v) for k, v in value.items() if not k.endswith("_ns") and k != "counterfactual_cost_ratio"}
    if isinstance(value, list):
        return [without_timing(v) for v in value]
    return value


def test_responses_and_hashes_are_identical_to_the_pre_optimization_runtime():
    hash_paths = {
        "reasoning_state_hash": ("reasoning_state", "hash"),
        "initial_hash": ("reasoning_state", "initial_hash"),
        "state_transition_hash": ("state_causality", "hashes", "state_transition_hash"),
        "causal_observation_hash": ("causal_bridge", "observation_hash"),
        "causal_relation_hash": ("causal_trace", "hashes", "causal_relation_hash"),
    }
    assert R0_DIGESTS["context"] == GOLDEN["context"] and len(R0_DIGESTS["cases"]) == 94
    for n, expected in R0_DIGESTS["cases"].items():
        payload = factorize(int(n), limits={"max_loop_iterations": 1_000_000})
        for name, path in hash_paths.items():
            value = payload["metadata"]
            for key in path:
                value = value[key]
            assert value == expected["hashes"][name], (n, name)
        digest = hashlib.sha256(json.dumps(without_timing(payload), separators=(",", ":")).encode()).hexdigest()
        assert digest == expected["response_sha256"], n


def test_response_phase_metrics_are_reported_and_the_hot_path_reports_zero_json():
    payload = factorize(84)
    for name in ("state_transition_materialization_ns", "provenance_materialization_ns", "transition_hash_ns"):
        assert payload["metadata"]["state_causality"]["metrics"][name] >= 0
    assert state(payload)["metrics"]["state_hash_ns"] >= 0


# --- Schemas --------------------------------------------------------------------


def test_artifacts_validate_against_the_published_schemas():
    jsonschema = pytest.importorskip("jsonschema")
    load = lambda name: json.loads((ROOT / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))  # noqa: E731
    for n in (77, 84, 97):
        payload = factorize(n)
        jsonschema.validate(state(payload), load("reasoning_state"))
        jsonschema.validate(payload["metadata"]["state_causality"], load("state_causality"))
        for transition in transitions(payload):
            jsonschema.validate(transition, load("state_transition"))
        for relation in payload["metadata"]["causal_trace"]["relations"]:
            jsonschema.validate(relation, load("causal_relation"))
    off = factorize(77, state_causality="off")
    jsonschema.validate(state(off), load("reasoning_state"))
    request = load("runtime_request")["properties"]["context"]["properties"]["reasoning_state"]
    assert request == {"enum": ["off", "lightweight"]}


def test_runtime_requests_validate_against_the_published_request_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((ROOT / "schemas" / "runtime_request.schema.json").read_text(encoding="utf-8"))
    source = TEMPLATE.replace("__N__", "77")
    for context in (
        {},
        {"state_causality": "trace"},
        {"state_causality": "off", "reasoning_state": "lightweight"},
        {"reasoning_state": "off", "benchmark_metrics": True},
    ):
        jsonschema.validate(request(source, **context), schema)
    for invalid in ({"reasoning_state": "sometimes"}, {"state_causality": "sometimes"}, {"not_a_context_key": 1}):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(request(source, **invalid), schema)


# --- Phase F: the manual hook is gone ------------------------------------------


def test_no_manual_state_transition_hook_remains_in_the_runtime():
    sources = list((ROOT / "ReasonRuntime" / "crates").glob("*/src/**/*.rs"))
    assert sources
    for path in sources:
        runtime_code = path.read_text(encoding="utf-8").split("#[cfg(test)]")[0]
        assert "record_state_transition" not in runtime_code, path
        # RuntimeReasoningState is the only place a StateTransition is constructed.
        if path.name != "reasoning_state.rs":
            assert not re.search(r"\bStateTransition\s*\{", runtime_code), path
