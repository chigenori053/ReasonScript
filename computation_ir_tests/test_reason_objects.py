"""RUS / RUO Runtime Integration v0.1: semantic projection over the runtime state.

The projection is checked against an independent Python model of the reasoning
(`oracle_objects`) and by validators that use the response artifacts alone.
"""

from __future__ import annotations

import hashlib
import json
from math import isqrt

import pytest

from computation_ir_tests import test_reasoning_state as base

pytestmark = pytest.mark.skipif(base.HOST is None, reason="reason-runtime-host binary not built")

OBJECTS = {"reason_objects": "rus_ruo"}
GOAL_HASHES = ("reasoning_state_hash", "state_transition_hash", "causal_relation_hash", "rus_sequence_hash", "ruo_graph_hash")


def run(n: int, mode: str = "rus_ruo", **context) -> dict:
    return base.factorize(n, reason_objects=mode, **context)


def rus(payload: dict) -> dict:
    return payload["metadata"]["rus"]


def ruo(payload: dict) -> dict:
    return payload["metadata"]["ruo"]


def objects_by(payload: dict, **match) -> list[dict]:
    return [o for o in ruo(payload)["objects"] if all(o[k] == v for k, v in match.items())]


def hashes(payload: dict) -> dict:
    meta = payload["metadata"]
    return {
        "reasoning_state_hash": meta["reasoning_state"]["hash"],
        "state_transition_hash": meta["state_causality"]["hashes"]["state_transition_hash"],
        "causal_relation_hash": meta["causal_trace"]["hashes"]["causal_relation_hash"],
        "rus_sequence_hash": rus(payload)["hashes"]["rus_sequence_hash"],
        "ruo_graph_hash": ruo(payload)["hashes"]["ruo_graph_hash"],
    }


def oracle_objects(n: int) -> dict:
    """Independent model: the RUS field sequence and the RUO (RU, status, before, after) sequence."""
    remaining, bound, candidate, current = n, isqrt(n), 2, None
    revision = 0

    def fields(goal: str) -> dict:
        return {"remaining": remaining, "search_bound": bound, "current_candidate": current,
                "active_constraint_count": 0, "goal_status": goal}

    states = [fields("ACTIVE")]
    units: list[tuple[str, str, int, int]] = [("hypothesis", "COMPLETED", 0, 0)]  # REASON_STATE_CREATED

    def move(kind: str, status: str, changes: bool) -> None:
        nonlocal revision
        units.append((kind, status, revision, revision + int(changes)))
        revision += int(changes)

    while candidate * candidate <= remaining:
        changed = current != candidate
        current = candidate
        move("hypothesis", "COMPLETED", changed)
        if changed:
            states.append(fields("ACTIVE"))
        if remaining % candidate == 0:
            remaining //= candidate
            bound = isqrt(remaining)
            move("verification", "VERIFIED", True)
            states.append(fields("ACTIVE"))
        else:
            move("verification", "REJECTED", False)
            candidate += 1
    move("goal-evaluation", "VERIFIED", True)
    states.append(fields("REACHED"))
    move("termination-check", "VERIFIED", False)
    return {
        "states": states,
        "objects": [
            {"ru": f"ru:{kind}:{index + 1:08}", "status": status, "before": before, "after": after}
            for index, (kind, status, before, after) in enumerate(units)
        ],
    }


def rus_id(revision: int) -> str:
    return f"rus:runtime:{revision:08}"


def dangling(payload: dict) -> list[str]:
    """Referential integrity from the artifacts alone."""
    meta = payload["metadata"]
    units = {u["id"]: u for u in meta["reason_unit_trace"]["reason_units"]}
    evidence = {e["id"] for e in meta["reason_unit_trace"]["evidence"]}
    reason_relations = {r["id"] for r in meta["reason_unit_trace"]["relations"]}
    rus_relations = {r["id"]: r for r in rus(payload)["relations"]}
    rus_ids = {s["id"] for s in rus(payload)["states"]}
    transitions = {t["id"]: t for t in meta["state_causality"]["transitions"]}
    causal = {r["id"]: r for r in meta["causal_trace"]["relations"]}
    problems = []
    for state in rus(payload)["states"]:
        if state["source_ru_ref"] is not None and state["source_ru_ref"] not in units:
            problems.append(f"{state['id']} source_ru_ref")
        problems += [f"{state['id']} {e}" for e in state["evidence_refs"] if e not in evidence]
        if state["transition_ref"] is not None and state["transition_ref"] not in transitions:
            problems.append(f"{state['id']} transition_ref")
    seen = set()
    for obj in ruo(payload)["objects"]:
        if obj["id"] in seen:
            problems.append(f"{obj['id']} duplicate")
        seen.add(obj["id"])
        if obj["ru_ref"] not in units or obj["id"] != f"ruo:{obj['ru_ref']}":
            problems.append(f"{obj['id']} ru_ref")
        problems += [f"{obj['id']} {r}" for r in (obj["rus_before_ref"], obj["rus_after_ref"]) if r not in rus_ids]
        problems += [f"{obj['id']} {e}" for e in obj["evidence_refs"] if e not in evidence]
        problems += [f"{obj['id']} {r}" for r in obj["relation_refs"] if r not in reason_relations and r not in rus_relations]
        near = {obj["ru_ref"], obj["rus_before_ref"], obj["rus_after_ref"]}
        near |= {s["transition_ref"] for s in rus(payload)["states"] if s["id"] in (obj["rus_before_ref"], obj["rus_after_ref"]) and s["transition_ref"]}
        for ref in obj["causal_relation_refs"]:
            if ref not in causal:
                problems.append(f"{obj['id']} {ref}")
            elif not ({causal[ref]["source_ref"], causal[ref]["target_ref"]} & near):
                problems.append(f"{obj['id']} {ref} unrelated")
    return problems


# --- Groups A-D: RUS revisions ---------------------------------------------------


def test_group_a_initial_rus_for_77():
    payload = run(77)
    first = rus(payload)["states"][0]
    assert (first["id"], first["revision"], first["parent_revision"]) == ("rus:runtime:00000000", 0, None)
    assert (first["fields"]["remaining"], first["fields"]["search_bound"], first["fields"]["goal_status"]) == (77, 8, "ACTIVE")
    assert first["transition_ref"] is None and first["evidence_refs"] == []
    init_ru = objects_by(payload, rus_before_ref=first["id"], rus_after_ref=first["id"])[0]["ru_ref"]
    assert first["source_ru_ref"] == init_ru == "ru:hypothesis:00000001"


def test_group_b_every_candidate_update_makes_a_new_revision():
    payload = run(77)
    candidates = [s["fields"]["current_candidate"] for s in rus(payload)["states"]]
    assert candidates[:7] == [None, 2, 3, 4, 5, 6, 7]
    assert [s["parent_revision"] for s in rus(payload)["states"][1:4]] == [0, 1, 2]


def test_group_c_factor_update_is_one_rus_revision():
    payload = run(77)
    before, after = rus(payload)["states"][6], rus(payload)["states"][7]
    assert (before["fields"]["remaining"], before["fields"]["search_bound"]) == (77, 8)
    assert (after["fields"]["remaining"], after["fields"]["search_bound"]) == (11, 3)
    assert after["revision"] == before["revision"] + 1
    assert after["evidence_refs"] and after["transition_ref"] == "state-transition:00000007"


def test_group_d_goal_rus():
    payload = run(77)
    before, after = rus(payload)["states"][-2:]
    assert (before["fields"]["goal_status"], after["fields"]["goal_status"]) == ("ACTIVE", "REACHED")
    assert {k: v for k, v in before["fields"].items() if k != "goal_status"} == {k: v for k, v in after["fields"].items() if k != "goal_status"}


# --- Groups E-J: RUO ---------------------------------------------------------------


def test_group_e_verification_ruo_binds_the_factor_update():
    payload = run(77)
    (verification,) = [o for o in objects_by(payload, status="VERIFIED") if o["ru_ref"].startswith("ru:verification")]
    assert (verification["rus_before_ref"], verification["rus_after_ref"]) == (rus_id(6), rus_id(7))
    evidence = {e["id"]: e for e in payload["metadata"]["reason_unit_trace"]["evidence"]}
    assert [evidence[e]["kind"] for e in verification["evidence_refs"]] == ["FACTOR_CONFIRMED"]
    assert rus(payload)["states"][6]["fields"]["remaining"] == 77 and rus(payload)["states"][7]["fields"]["remaining"] == 11
    assert verification["lifecycle"] == ["CREATED", "ACTIVE", "VERIFIED", "COMPLETED"]


def test_group_f_rejected_ruo_keeps_the_state():
    payload = run(77)
    rejected = objects_by(payload, status="REJECTED")
    assert len(rejected) == 5  # candidates 2..6
    assert all(o["rus_before_ref"] == o["rus_after_ref"] for o in rejected)
    five = rejected[3]
    assert "|HYPOTHESIS_REJECTED|5|" in five["semantic_signature"]
    assert five["evidence_refs"], "rejected Evidence is kept"
    assert five["lifecycle"] == ["CREATED", "ACTIVE", "REJECTED", "COMPLETED"]


def test_group_g_goal_ruo():
    payload = run(77)
    (goal,) = objects_by(payload, ru_ref="ru:goal-evaluation:00000014")
    before, after = (rus(payload)["states"][int(goal[k][-8:])] for k in ("rus_before_ref", "rus_after_ref"))
    assert (before["fields"]["goal_status"], after["fields"]["goal_status"]) == ("ACTIVE", "REACHED")


def test_group_h_termination_ruo_exists_without_a_state_change():
    payload = run(77)
    (termination,) = [o for o in ruo(payload)["objects"] if o["ru_ref"].startswith("ru:termination-check")]
    assert termination["rus_before_ref"] == termination["rus_after_ref"] == rus_id(len(rus(payload)["states"]) - 1)


def test_group_i_ruo_reaches_the_state_change_relation():
    payload = run(77)
    causal = {r["id"]: r for r in payload["metadata"]["causal_trace"]["relations"]}
    (verification,) = [o for o in objects_by(payload, status="VERIFIED") if o["ru_ref"].startswith("ru:verification")]
    linked = [causal[ref] for ref in verification["causal_relation_refs"]]
    (change,) = [r for r in linked if r["relation_kind"] == "CAUSES_STATE_CHANGE"]
    assert change["source_ref"] == verification["ru_ref"] and change["target_ref"] == "state-transition:00000007"
    # incoming (candidate transition -> this RU) and outgoing (its own transition -> next RU)
    assert any(r["relation_kind"] == "ENABLES" and r["target_ref"] == verification["ru_ref"] for r in linked)
    assert any(r["relation_kind"] == "ENABLES" and r["source_ref"] == "state-transition:00000007" for r in linked)


def test_group_j_full_chain_for_77():
    payload = run(77)
    by_ru = {o["ru_ref"]: o for o in ruo(payload)["objects"]}
    order = [o["ru_ref"] for o in ruo(payload)["objects"]]
    chain = [
        by_ru["ru:verification:00000013"],
        by_ru["ru:goal-evaluation:00000014"],
        by_ru["ru:termination-check:00000015"],
    ]
    assert order.index(chain[0]["ru_ref"]) < order.index(chain[1]["ru_ref"]) < order.index(chain[2]["ru_ref"])
    factor_state, goal_state = rus(payload)["states"][7], rus(payload)["states"][8]
    assert chain[0]["rus_after_ref"] == factor_state["id"] == chain[1]["rus_before_ref"]
    assert chain[1]["rus_after_ref"] == goal_state["id"] == chain[2]["rus_before_ref"] == chain[2]["rus_after_ref"]
    relations = {(r["kind"], r["source_ref"], r["target_ref"]) for r in rus(payload)["relations"]}
    assert ("READS_STATE", factor_state["id"], "ru:goal-evaluation:00000014") in relations
    assert ("UPDATES", "ru:verification:00000013", factor_state["id"]) in relations
    assert ("DERIVES_STATE", rus_id(6), factor_state["id"]) in relations
    terminates = [r for r in payload["metadata"]["causal_trace"]["relations"] if r["relation_kind"] == "TERMINATES"]
    assert terminates[0]["source_ref"] == goal_state["transition_ref"]
    assert terminates[0]["id"] in chain[2]["causal_relation_refs"]


# --- Groups K-L: other inputs ------------------------------------------------------


def test_group_k_multi_factor_84():
    payload = run(84)
    assert [s["fields"]["remaining"] for s in rus(payload)["states"]] == [84, 84, 42, 21, 21, 7, 7]
    verified = [o for o in objects_by(payload, status="VERIFIED") if o["ru_ref"].startswith("ru:verification")]
    assert len(verified) == 3 and all(int(o["rus_after_ref"][-8:]) == int(o["rus_before_ref"][-8:]) + 1 for o in verified)
    assert dangling(payload) == []


def test_group_l_prime_97_has_objects_but_no_remaining_update():
    payload = run(97)
    assert {s["fields"]["remaining"] for s in rus(payload)["states"]} == {97}
    assert not [o for o in ruo(payload)["objects"] if o["status"] == "VERIFIED" and o["ru_ref"].startswith("ru:verification")]
    assert dangling(payload) == [] and ruo(payload)["diagnostics"] == rus(payload)["diagnostics"] == []


# --- Group M: determinism / hashes ------------------------------------------------------


def test_group_m_three_run_determinism():
    runs = [hashes(run(84)) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    assert all(len(v) == 71 for v in runs[0].values())


def test_final_rus_is_the_runtime_state_and_hashes_recompute_from_artifacts():
    payload = run(84)
    final = rus(payload)["states"][-1]
    assert final["semantic_state_hash"] == payload["metadata"]["reasoning_state"]["hash"]
    assert rus(payload)["states"][0]["semantic_state_hash"] == payload["metadata"]["reasoning_state"]["initial_hash"]
    for state in rus(payload)["states"]:
        assert state["semantic_state_hash"] == base.state_hash(state["revision"], state["fields"])
    assert rus(payload)["metrics"]["rus_projection_count"] == len(rus(payload)["states"])
    assert ruo(payload)["metrics"]["ruo_count"] == len(ruo(payload)["objects"]) == len(payload["metadata"]["reason_unit_trace"]["reason_units"])


def canonical_hash(records: list) -> str:
    text = json.dumps(records, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("n", [2, 77, 84, 97, 221])
def test_rus_and_ruo_hashes_recompute_from_the_artifacts_alone(n):
    payload = run(n)
    states, relations, objects = rus(payload)["states"], rus(payload)["relations"], ruo(payload)["objects"]
    assert rus(payload)["hashes"]["rus_sequence_hash"] == canonical_hash([
        [s["id"], s["parent_revision"], s["source_ru_ref"], s["transition_ref"], s["evidence_refs"], s["semantic_state_hash"]]
        for s in states
    ])
    assert rus(payload)["hashes"]["rus_relation_hash"] == canonical_hash(
        [[r["id"], r["kind"], r["source_ref"], r["target_ref"]] for r in relations]
    )
    assert ruo(payload)["hashes"]["ruo_graph_hash"] == canonical_hash([
        [o["id"], o["ru_ref"], o["rus_before_ref"], o["rus_after_ref"], o["evidence_refs"], o["relation_refs"],
         o["causal_relation_refs"], o["lifecycle"], o["status"], o["semantic_signature"]]
        for o in objects
    ])


# --- Group N: replay from the RUS artifact alone -----------------------------------------


def test_group_n_state_sequence_is_rebuilt_from_rus_artifacts_alone():
    payload = run(84)
    states = rus(payload)["states"]
    transitions = payload["metadata"]["state_causality"]["transitions"]
    current = dict(states[0]["fields"])
    for parent, state in zip(states, states[1:]):
        assert state["parent_revision"] == parent["revision"] == state["revision"] - 1
        changed = {k: v for k, v in state["fields"].items() if current[k] != v}
        transition = transitions[state["revision"] - 1]
        assert state["transition_ref"] == transition["id"] and state["source_ru_ref"] == transition["source_ru"]
        assert changed == transition["after_values"] and {k: current[k] for k in changed} == transition["before_values"]
        current = dict(state["fields"])
    assert current == payload["metadata"]["reasoning_state"]["fields"]


# --- Group O: referential integrity -------------------------------------------------------


@pytest.mark.parametrize("n", [49, 77, 84, 97, 221, 10007])
def test_group_o_no_dangling_references(n):
    payload = run(n)
    assert dangling(payload) == []
    assert rus(payload)["metrics"]["dangling_reference_count"] == ruo(payload)["metrics"]["dangling_reference_count"] == 0


# --- Group P: nothing existing changes -----------------------------------------------------


def strip_objects(payload: dict) -> dict:
    meta = {k: v for k, v in payload["metadata"].items() if k not in ("rus", "ruo")}
    return base.without_timing({**payload, "metadata": meta})


@pytest.mark.parametrize("n", [49, 77, 84, 97, 221])
def test_group_p_existing_artifacts_and_hashes_are_unchanged(n):
    plain, with_rus, with_objects = base.factorize(n), run(n, "rus"), run(n)
    assert strip_objects(with_objects) == strip_objects(plain) == base.without_timing(plain)
    assert strip_objects(with_rus) == strip_objects(plain)
    assert "rus" not in plain["metadata"] and "ruo" not in plain["metadata"]
    assert "ruo" not in with_rus["metadata"]
    assert json.dumps(strip_objects(with_objects)) == json.dumps(strip_objects(plain))  # key order too


def test_legacy_reason_structure_projection_is_untouched():
    legacy = {"reason_units": "ru_rus_ruo"}
    plain, extended = base.factorize(77, **legacy), run(77, **legacy)
    for key in ("reason_structure_trace", "reason_unit_trace"):
        assert extended["metadata"][key] == plain["metadata"][key]
    assert plain["metadata"]["reason_structure_trace"]["reason_unit_objects"]


@pytest.mark.parametrize("n", range(2, 90))
def test_runtime_projection_equals_independent_oracle_for_every_small_n(n):
    payload = run(n)
    expected = oracle_objects(n)
    assert [s["fields"] for s in rus(payload)["states"]] == expected["states"]
    assert [
        {"ru": o["ru_ref"], "status": o["status"], "before": int(o["rus_before_ref"][-8:]), "after": int(o["rus_after_ref"][-8:])}
        for o in ruo(payload)["objects"]
    ] == expected["objects"]
    assert dangling(payload) == [] and rus(payload)["diagnostics"] == ruo(payload)["diagnostics"] == []


def test_golden_cases_match_the_runtime_states_from_the_reasoning_state_golden():
    for case in base.GOLDEN["cases"]:
        payload = run(case["n"])
        assert len(rus(payload)["states"]) == case["revision_count"] + 1
        assert rus(payload)["states"][-1]["fields"] == case["final_state"]


def test_native_relation_filter_projects_without_an_initialization_ru():
    payload = base.execute(
        """module Factorization {
            struct Candidate { value: int }
            calculation Factors {
                let n = 77
                let candidates = [Candidate { value: 2 }, Candidate { value: 5 }, Candidate { value: 7 }, Candidate { value: 8 }]
                let factors = relation.filter(candidates, n % candidate.value == 0)
                result = factors.length
            }
        }""",
        reason_objects="rus_ruo",
    )
    states = rus(payload)["states"]
    assert len(states) == len(payload["metadata"]["state_causality"]["transitions"]) + 1 == 7
    assert states[0]["source_ru_ref"] is None and states[0]["fields"]["remaining"] is None
    assert states[-1]["semantic_state_hash"] == payload["metadata"]["reasoning_state"]["hash"]
    (goal,) = [o for o in ruo(payload)["objects"] if o["ru_ref"].startswith("ru:goal-evaluation")]
    assert (states[int(goal["rus_before_ref"][-8:])]["fields"]["goal_status"], states[int(goal["rus_after_ref"][-8:])]["fields"]["goal_status"]) == ("ACTIVE", "REACHED")
    accepted = [o for o in ruo(payload)["objects"] if o["status"] == "VERIFIED" and o["ru_ref"].startswith("ru:verification")]
    assert len(accepted) == 1 and accepted[0]["rus_after_ref"] != accepted[0]["rus_before_ref"]
    assert dangling(payload) == [] and len(ruo(payload)["objects"]) == len(payload["metadata"]["reason_unit_trace"]["reason_units"])


# --- Configuration ---------------------------------------------------------------------------


def test_rus_mode_needs_only_the_reasoning_state_and_reports_no_state_causality():
    payload = base.factorize(77, state_causality="off", reasoning_state="lightweight", reason_objects="rus")
    assert len(rus(payload)["states"]) == 9 and rus(payload)["diagnostics"] == []
    assert payload["metadata"]["state_causality"]["transitions"] == [] and payload["metadata"]["state_causality"]["mode"] == "off"
    assert rus(payload)["states"][-1]["semantic_state_hash"] == payload["metadata"]["reasoning_state"]["hash"]


def test_configuration_errors():
    def code(**context):
        return base.execute(base.MINIMAL, expect_ok=False, **context)["diagnostics"][0]["code"]

    assert code(reason_objects="sometimes") == "RTH-PROTO-004"
    assert code(state_causality="off", reasoning_state="off", executable_reason_units="off", reason_objects="rus") == "RUO-001"
    assert code(state_causality="off", reasoning_state="off", reason_objects="rus") == "RUO-002"
    assert code(state_causality="trace", reason_objects="rus_ruo") == "RUO-002"
    assert code(state_causality="off", reasoning_state="lightweight", reason_objects="rus_ruo") == "RUO-002"


# --- Schemas ------------------------------------------------------------------------------------


def test_artifacts_validate_against_the_rus_and_ruo_schemas():
    jsonschema = pytest.importorskip("jsonschema")
    load = lambda name: json.loads((base.ROOT / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))  # noqa: E731
    for n in (2, 77, 84, 97):
        payload = run(n)
        jsonschema.validate(rus(payload), load("rus"))
        jsonschema.validate(ruo(payload), load("ruo"))
    jsonschema.validate(rus(run(77, "rus")), load("rus"))
    request = base.request(base.TEMPLATE.replace("__N__", "77"), reason_objects="rus_ruo")
    jsonschema.validate(request, load("runtime_request"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(base.request(base.TEMPLATE.replace("__N__", "77"), reason_objects="everything"), load("runtime_request"))
    broken = json.loads(json.dumps(ruo(run(77))))
    broken["objects"][0].pop("rus_before_ref")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(broken, load("ruo"))


def test_the_independent_validator_detects_dangling_references():
    payload = run(77)
    payload["metadata"]["ruo"]["objects"][3]["evidence_refs"].append("evidence:ru:99999999")
    payload["metadata"]["ruo"]["objects"][4]["causal_relation_refs"].append("causal-relation:99999999")
    payload["metadata"]["ruo"]["objects"][5]["rus_after_ref"] = rus_id(99)
    problems = dangling(payload)
    for injected in ("evidence:ru:99999999", "causal-relation:99999999", "rus:runtime:00000099"):
        assert any(injected in problem for problem in problems), injected
