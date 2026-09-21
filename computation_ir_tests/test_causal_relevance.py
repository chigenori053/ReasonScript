"""Causal Relevance Filtering v0.1: which reasoning objects the result needed.

Classifications are checked against an independent model of the reasoning
(`oracle_classes`, which never looks at the causal graph) and against synthetic
causal graphs built from external observations. The relevant view is validated
from the response artifacts alone.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from computation_ir_tests import test_reason_objects as objs
from computation_ir_tests import test_reasoning_state as base

pytestmark = pytest.mark.skipif(base.HOST is None, reason="reason-runtime-host binary not built")

FULL = {"reason_objects": "rus_ruo"}
GOAL_HASHES = objs.GOAL_HASHES
CLASSES = ("ESSENTIAL", "SUPPORTING", "EXCLUSION", "UNRESOLVED", "NOISE")


def run(n: int, relevance: str = "filter", objects: str | None = "rus_ruo", **context) -> dict:
    if objects:
        context["reason_objects"] = objects
    return base.factorize(n, causal_relevance=relevance, **context)


def relevance(payload: dict) -> dict:
    return payload["metadata"]["causal_relevance"]


def classes(payload: dict) -> dict[str, str]:
    return {c["ru_ref"]: c["class"] for c in relevance(payload)["classifications"]}


def entry(payload: dict, ru: str) -> dict:
    return next(c for c in relevance(payload)["classifications"] if c["ru_ref"] == ru)


def noisy(n: int, per_candidate: int = 2, head: int = 1, tail: int = 1) -> str:
    """The factorization with unrelated (no-state) reasoning events mixed in."""
    def events(count: int, tag: str) -> str:
        return "".join(f'    reasoning.event("RU_ACTIVATED", n, "{tag}")\n' for _ in range(count))

    text = base.TEMPLATE.replace("__N__", str(n))
    text = text.replace('    let remaining = n\n', events(head, "head") + "    let remaining = n\n", 1)
    inner = "".join(f'        reasoning.event("RU_ACTIVATED", candidate, "c{i}")\n' for i in range(per_candidate))
    text = text.replace('        reasoning.event("HYPOTHESIS_REJECTED", candidate, false)\n',
                        '        reasoning.event("HYPOTHESIS_REJECTED", candidate, false)\n' + inner)
    return text.replace('    reasoning.event("GOAL_UPDATED", n, remaining)', events(tail, "tail") + '    reasoning.event("GOAL_UPDATED", n, remaining)')


def oracle_classes(n: int) -> dict[str, str]:
    """What the classification must be, derived from the reasoning alone: state
    changers, the goal chain, rejected candidate checks, and the initial state."""
    result = {}
    for index, unit in enumerate(objs.oracle_objects(n)["objects"]):
        kind = unit["ru"].split(":")[1]
        if kind in ("goal-evaluation", "termination-check") or unit["after"] != unit["before"]:
            cls = "ESSENTIAL"
        elif index == 0:
            cls = "SUPPORTING"
        elif kind == "verification" and unit["status"] == "REJECTED":
            cls = "EXCLUSION"
        else:
            cls = "NOISE"
        result[unit["ru"]] = cls
    return result


def canonical(records) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(records, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def relevant_problems(payload: dict) -> list[str]:
    """Referential integrity of the relevant view, from the artifacts alone."""
    meta = payload["metadata"]
    view = relevance(payload)["relevant"]
    units = {u["id"]: u for u in meta["reason_unit_trace"]["reason_units"]}
    evidence_owner = {e["id"]: e["source_ru"] for e in meta["reason_unit_trace"]["evidence"]}
    reason_relations = {r["id"]: r for r in meta["reason_unit_trace"]["relations"]}
    causal = {r["id"]: r for r in meta["causal_trace"]["relations"]}
    kept_rus = {s["id"]: s for s in view["rus"]["states"]}
    kept_rus_relations = {r["id"]: r for r in view["rus"]["relations"]}
    objects = {o["ru_ref"]: o for o in view["ruo"]["objects"]}
    kept_evidence = {e for o in objects.values() for e in o["evidence_refs"]}
    transitions = {s["transition_ref"] for s in kept_rus.values() if s["transition_ref"]}
    problems = []

    def endpoint_ok(ref: str) -> bool:
        return ref in objects or ref in kept_rus or ref in kept_evidence or ref in transitions

    for state in kept_rus.values():
        parent = state["parent_revision"]
        if parent is not None and f"rus:runtime:{parent:08}" not in kept_rus:
            problems.append(f"{state['id']} parent")
        if state["source_ru_ref"] is not None and state["source_ru_ref"] not in objects:
            problems.append(f"{state['id']} source_ru_ref {state['source_ru_ref']}")
        problems += [f"{state['id']} {e}" for e in state["evidence_refs"] if e not in kept_evidence]
    for relation in kept_rus_relations.values():
        problems += [f"{relation['id']} {ref}" for ref in (relation["source_ref"], relation["target_ref"]) if ref not in objects and ref not in kept_rus]
    for ru, obj in objects.items():
        if ru not in units or obj["id"] != f"ruo:{ru}":
            problems.append(f"{obj['id']} ru_ref")
        problems += [f"{obj['id']} {r}" for r in (obj["rus_before_ref"], obj["rus_after_ref"]) if r not in kept_rus]
        problems += [f"{obj['id']} {e}" for e in obj["evidence_refs"] if evidence_owner.get(e) != ru]
        for ref in obj["relation_refs"]:
            if ref in kept_rus_relations:
                continue
            relation = reason_relations.get(ref)
            if relation is None or not (endpoint_ok(relation["source_ref"]) and endpoint_ok(relation["target_ref"])):
                problems.append(f"{obj['id']} {ref}")
        for ref in obj["causal_relation_refs"]:
            relation = causal.get(ref)
            if ref not in view["causal_relation_refs"] or relation is None:
                problems.append(f"{obj['id']} {ref}")
            elif relation["relation_kind"] == "TEMPORAL" or not (endpoint_ok(relation["source_ref"]) and endpoint_ok(relation["target_ref"])):
                problems.append(f"{obj['id']} {ref} endpoint")
    for ref in view["causal_relation_refs"]:
        relation = causal.get(ref)
        if relation is None or relation["relation_kind"] == "TEMPORAL":
            problems.append(f"view {ref}")
        elif not (endpoint_ok(relation["source_ref"]) and endpoint_ok(relation["target_ref"])):
            problems.append(f"view {ref} endpoint")
    return problems


# --- A-D, G-J: classification of the factorization -------------------------------------------


def test_group_a_and_b_state_causes_are_essential():
    payload = run(77)
    verification = entry(payload, "ru:verification:00000013")  # candidate 7: remaining and search_bound change
    assert (verification["class"], verification["reasons"]) == ("ESSENTIAL", ["STATE_CAUSE"])
    kinds = {(r["source_ref"], r["relation_kind"], r["status"]) for r in payload["metadata"]["causal_trace"]["relations"]}
    assert ("ru:verification:00000013", "CAUSES_STATE_CHANGE", "CONFIRMED") in kinds
    assert all(entry(payload, f"ru:hypothesis:{i:08}")["class"] == "ESSENTIAL" for i in (2, 4, 6, 8, 10, 12))


def test_group_c_enables_chain_reaches_the_goal():
    payload = run(77)
    kinds = {(r["source_ref"], r["target_ref"], r["relation_kind"]) for r in payload["metadata"]["causal_trace"]["relations"]}
    assert ("state-transition:00000007", "ru:goal-evaluation:00000014", "ENABLES") in kinds
    assert entry(payload, "ru:goal-evaluation:00000014")["class"] == "ESSENTIAL"  # promoted: it is in the goal chain
    assert entry(payload, "ru:hypothesis:00000001")["class"] == "SUPPORTING"  # initializes RUS 0


def test_group_g_search_rejections_are_exclusions():
    payload = run(77)
    for ru in (3, 5, 7, 9, 11):  # candidates 2..6
        item = entry(payload, f"ru:verification:{ru:08}")
        assert (item["class"], item["reasons"]) == ("EXCLUSION", ["SEARCH_EXCLUSION"])


def test_group_h_i_j_verified_factor_goal_and_termination_are_essential():
    payload = run(77)
    assert entry(payload, "ru:verification:00000013")["class"] == "ESSENTIAL"
    assert entry(payload, "ru:goal-evaluation:00000014")["reasons"] == ["GOAL_TERMINATION", "STATE_CAUSE"]
    assert entry(payload, "ru:termination-check:00000015")["reasons"] == ["GOAL_TERMINATION"]
    roots = {r["kind"]: r["ref"] for r in relevance(payload)["roots"]}
    assert roots == {"GOAL_EVALUATION": "ru:goal-evaluation:00000014", "TERMINATION_CHECK": "ru:termination-check:00000015",
                     "FINAL_RUS": "rus:runtime:00000008", "GOAL_STATUS_TRANSITION": "state-transition:00000008"}
    assert [r["ref"] for r in relevance(payload)["roots"]] == sorted(r["ref"] for r in relevance(payload)["roots"])


def test_group_k_full_and_relevant_view_for_77():
    payload = run(77)
    view = relevance(payload)["relevant"]
    assert relevance(payload)["metrics"]["noise_ru_count"] == 0
    # Nothing is noise, so the relevant RUO objects are the full RUO objects up to dropped TEMPORAL references.
    full = {o["ru_ref"]: o for o in objs.ruo(payload)["objects"]}
    assert [o["ru_ref"] for o in view["ruo"]["objects"]] == list(full)
    temporal = {r["id"] for r in payload["metadata"]["causal_trace"]["relations"] if r["relation_kind"] == "TEMPORAL"}
    for obj in view["ruo"]["objects"]:
        expected = [r for r in full[obj["ru_ref"]]["causal_relation_refs"] if r not in temporal]
        assert obj["causal_relation_refs"] == expected
        assert {k: v for k, v in obj.items() if k not in ("causal_relation_refs", "relation_refs")} == {
            k: v for k, v in full[obj["ru_ref"]].items() if k not in ("causal_relation_refs", "relation_refs")}
    # Every state revision stays, so the RUS sequence is the full one.
    assert view["rus"]["states"] == objs.rus(payload)["states"]
    assert relevance(payload)["hashes"]["relevant_rus_sequence_hash"] == objs.rus(payload)["hashes"]["rus_sequence_hash"]
    chain = [c["ru_ref"] for c in relevance(payload)["classifications"] if c["class"] in ("EXCLUSION", "ESSENTIAL")]
    assert chain[-3:] == ["ru:verification:00000013", "ru:goal-evaluation:00000014", "ru:termination-check:00000015"]


def test_group_l_multi_factor_84_keeps_every_factor_chain():
    payload = run(84)
    verified = [o["ru_ref"] for o in objs.objects_by(payload, status="VERIFIED") if o["ru_ref"].startswith("ru:verification")]
    assert len(verified) == 3  # 2 * 2 * 3 * 7: factors 2, 2, 3 leave 7
    retained = {o["ru_ref"] for o in relevance(payload)["relevant"]["ruo"]["objects"]}
    assert set(verified) <= retained and all(classes(payload)[ru] == "ESSENTIAL" for ru in verified)
    assert relevant_problems(payload) == []
    # The only noise are hypotheses that repeat a candidate and change no state.
    noise = [ru for ru, cls in classes(payload).items() if cls == "NOISE"]
    assert noise and all(ru.startswith("ru:hypothesis") for ru in noise)
    assert all(entry(payload, ru)["reasons"] == ["TEMPORAL_ONLY"] for ru in noise)
    assert not (set(noise) & retained)


def test_group_m_prime_97_keeps_exclusions_goal_and_termination():
    payload = run(97)
    counts = relevance(payload)["metrics"]
    assert (counts["exclusion_ru_count"], counts["noise_ru_count"]) == (8, 0)  # candidates 2..9
    assert classes(payload)["ru:goal-evaluation:00000018"] == "ESSENTIAL"
    assert classes(payload)["ru:termination-check:00000019"] == "ESSENTIAL"
    assert not any(o["status"] == "VERIFIED" and o["ru_ref"].startswith("ru:verification") for o in objs.ruo(payload)["objects"])


def test_group_n_unrelated_rus_are_noise_and_change_nothing_else():
    payload = base.execute(noisy(77), causal_relevance="filter", **FULL)
    reference = run(77)
    noise = [ru for ru, cls in classes(payload).items() if cls == "NOISE"]
    injected = [u["id"] for u in payload["metadata"]["reason_unit_trace"]["reason_units"] if "RU_ACTIVATED" in u["semantic_signature"]]
    assert len(injected) == 1 + 5 * 2 + 1  # head, two per rejected candidate 2..6, tail
    assert sorted(noise) == sorted(injected)
    # Everything that mattered is classified as in the run without the noise.
    def signature(run_payload, keep):
        by_id = {u["id"]: u["semantic_signature"] for u in run_payload["metadata"]["reason_unit_trace"]["reason_units"]}
        return [(by_id[c["ru_ref"]], c["class"], c["reasons"]) for c in relevance(run_payload)["classifications"] if keep(c)]
    assert signature(payload, lambda c: c["class"] != "NOISE") == signature(reference, lambda c: True)
    # The relevant RUS sequence is the same reasoning-state history.
    assert [s["fields"] for s in relevance(payload)["relevant"]["rus"]["states"]] == [s["fields"] for s in objs.rus(reference)["states"]]
    retained = {o["ru_ref"] for o in relevance(payload)["relevant"]["ruo"]["objects"]}
    assert not (set(noise) & retained)
    assert relevant_problems(payload) == []
    ratio = relevance(payload)["metrics"]["reasoning_noise_reduction_ratio"]
    assert ratio == pytest.approx(len(noise) / len(classes(payload)))


def test_group_p_three_run_determinism():
    runs = [run(84, causal_relevance_roots=[]) for _ in range(3)]
    for name in ("causal_relevance_hash", "relevant_ruo_graph_hash", "relevant_rus_sequence_hash", "relevant_rus_relation_hash"):
        assert len({relevance(r)["hashes"][name] for r in runs}) == 1, name

    def stable(payload):  # byte sizes count the digits of the embedded *_ns timings, so they may differ by a byte
        item = json.loads(json.dumps(base.without_timing(relevance(payload))))
        for key in ("full_json_bytes", "relevant_json_bytes", "response_reduction_ratio"):
            item["metrics"].pop(key)
        return json.dumps(item)

    assert len({stable(r) for r in runs}) == 1


@pytest.mark.parametrize("n", [49, 77, 84, 97, 221, 10007])
def test_group_q_existing_hashes_and_artifacts_do_not_change(n):
    plain = base.factorize(n, **FULL, limits={"max_loop_iterations": 1_000_000})
    for mode in ("annotate", "filter"):
        payload = run(n, mode, limits={"max_loop_iterations": 1_000_000})
        assert objs.hashes(payload) == objs.hashes(plain)
        assert payload["metadata"]["causal_bridge"]["observation_hash"] == plain["metadata"]["causal_bridge"]["observation_hash"]
        assert set(GOAL_HASHES) <= set(objs.hashes(payload))
        stripped = json.loads(json.dumps(payload))
        del stripped["metadata"]["causal_relevance"]
        assert json.dumps(base.without_timing(stripped)) == json.dumps(base.without_timing(plain))  # incl. key order


def test_group_r_off_is_byte_compatible_with_the_existing_response():
    for context in ({}, FULL):
        plain = base.factorize(84, **context)
        off = base.factorize(84, causal_relevance="off", **context)
        assert "causal_relevance" not in off["metadata"]
        assert json.dumps(base.without_timing(off)) == json.dumps(base.without_timing(plain))


@pytest.mark.parametrize("n", [49, 77, 84, 97, 221, 10007])
def test_group_s_relevant_view_has_no_dangling_references(n):
    payload = run(n, limits={"max_loop_iterations": 1_000_000})
    assert relevant_problems(payload) == []
    assert relevance(payload)["relevant"]["rus"]["metrics"]["dangling_reference_count"] == 0
    assert relevance(payload)["relevant"]["ruo"]["metrics"]["dangling_reference_count"] == 0
    noisy_payload = base.execute(noisy(n, 1) if n < 300 else noisy(77), causal_relevance="filter", **FULL)
    assert relevant_problems(noisy_payload) == []


def test_the_relevant_view_validator_detects_dangling_references():
    payload = run(84)
    broken = json.loads(json.dumps(payload))
    view = relevance(broken)["relevant"]
    dropped = next(c for c, k in classes(broken).items() if k == "NOISE")
    view["ruo"]["objects"][0]["rus_after_ref"] = "rus:runtime:00000099"
    view["ruo"]["objects"][1]["evidence_refs"].append("evidence:ru:00000099")
    view["ruo"]["objects"][2]["causal_relation_refs"].append(
        next(r["id"] for r in broken["metadata"]["causal_trace"]["relations"] if r["relation_kind"] == "TEMPORAL"))
    view["ruo"]["objects"][3]["relation_refs"].append("relation:ru:99999999")
    view["rus"]["states"][2]["source_ru_ref"] = dropped
    problems = relevant_problems(broken)
    assert len(problems) >= 5
    for expected in ("rus:runtime:00000099", "evidence:ru:00000099", "relation:ru:99999999", dropped):
        assert any(expected in p for p in problems), expected


# --- classification vs the independent model ----------------------------------------------------


def test_golden_cases_match_the_independent_model():
    for case in base.GOLDEN["cases"]:
        payload = run(case["n"])
        assert classes(payload) == oracle_classes(case["n"]), case["n"]


@pytest.mark.parametrize("n", range(2, 90))
def test_differential_classification_and_view_for_every_small_n(n):
    payload = run(n)
    expected = oracle_classes(n)
    assert classes(payload) == expected
    view = relevance(payload)["relevant"]
    kept = [ru for ru, cls in expected.items() if cls != "NOISE"]
    assert [o["ru_ref"] for o in view["ruo"]["objects"]] == kept
    assert relevance(payload)["metrics"]["essential_preservation_rate"] == 1.0
    assert relevant_problems(payload) == []
    assert relevance(payload)["diagnostics"] == []


# --- metrics, hashes, artifacts -------------------------------------------------------------------


def test_metrics_reductions_and_hashes_recompute_from_the_artifacts():
    payload = base.execute(noisy(84), causal_relevance="filter", **FULL)
    item, meta = relevance(payload), payload["metadata"]
    metrics = item["metrics"]
    assert metrics["total_ru_count"] == len(item["classifications"]) == len(meta["reason_unit_trace"]["reason_units"])
    assert sum(metrics[f"{c.lower()}_ru_count"] for c in CLASSES) == metrics["total_ru_count"]
    assert metrics["noise_ru_count"] > 0 and metrics["essential_preservation_rate"] == 1.0
    assert metrics["reasoning_noise_reduction_ratio"] == metrics["ru_reduction_ratio"] == metrics["ruo_reduction_ratio"]
    assert metrics["rus_reduction_ratio"] == 0.0
    full_relations = len(meta["causal_trace"]["relations"]) + len(objs.rus(payload)["relations"]) + len(meta["reason_unit_trace"]["relations"])
    view = item["relevant"]
    retained_ru = {o["ru_ref"] for o in view["ruo"]["objects"]}
    evidence = {e for o in view["ruo"]["objects"] for e in o["evidence_refs"]}
    reason_kept = [r for r in meta["reason_unit_trace"]["relations"] if {r["source_ref"], r["target_ref"]} <= retained_ru | evidence]
    relevant_relations = len(view["causal_relation_refs"]) + len(view["rus"]["relations"]) + len(reason_kept)
    assert (metrics["full_relation_count"], metrics["relevant_relation_count"]) == (full_relations, relevant_relations)
    assert metrics["relation_reduction_ratio"] == pytest.approx(1 - relevant_relations / full_relations)
    full_bytes = len(json.dumps(objs.rus(payload), separators=(",", ":"), ensure_ascii=False)) + len(json.dumps(objs.ruo(payload), separators=(",", ":"), ensure_ascii=False))
    assert metrics["full_json_bytes"] == full_bytes
    assert metrics["relevant_json_bytes"] == len(json.dumps(view, separators=(",", ":"), ensure_ascii=False))
    assert 0 < metrics["response_reduction_ratio"] < 1
    # Hashes.
    by_id = {c["ru_ref"]: c for c in item["classifications"]}
    assert item["hashes"]["causal_relevance_hash"] == canonical([[c["ru_ref"], c["class"], c["reasons"]] for c in item["classifications"]])
    assert item["hashes"]["relevant_ruo_graph_hash"] == canonical([
        [o["id"], o["ru_ref"], o["rus_before_ref"], o["rus_after_ref"], o["evidence_refs"], o["relation_refs"], o["causal_relation_refs"],
         o["lifecycle"], o["status"], o["semantic_signature"]] for o in view["ruo"]["objects"]])
    assert item["hashes"]["relevant_rus_relation_hash"] == canonical([[r["id"], r["kind"], r["source_ref"], r["target_ref"]] for r in view["rus"]["relations"]])
    assert set(by_id) == {u["id"] for u in meta["reason_unit_trace"]["reason_units"]}
    # A relevant hash differs from the full one only when something was dropped.
    assert item["hashes"]["relevant_ruo_graph_hash"] != objs.ruo(payload)["hashes"]["ruo_graph_hash"]


def test_annotate_adds_classifications_only():
    payload = run(84, "annotate")
    assert "relevant" not in relevance(payload)
    assert relevance(payload)["mode"] == "annotate"
    assert classes(payload) == oracle_classes(84)
    assert relevance(payload)["metrics"]["relevant_json_bytes"] is None
    assert set(relevance(payload)["hashes"]) == {"causal_relevance_hash"}


def test_filter_without_the_full_view_still_yields_a_relevant_view():
    payload = base.factorize(84, causal_relevance="filter", **{})  # reason_objects off
    assert "rus" not in payload["metadata"] and "ruo" not in payload["metadata"]
    assert relevant_problems(payload) == []  # validator only needs relevance + causal + reason_unit_trace
    assert relevance(payload)["metrics"]["full_json_bytes"] is None


def test_relevant_view_keeps_full_view_ids():
    payload = run(84)
    full_rus = {r["id"]: r for r in objs.rus(payload)["relations"]}
    for relation in relevance(payload)["relevant"]["rus"]["relations"]:
        assert full_rus[relation["id"]] == relation  # same numbering, not a renumbered copy


# --- synthetic causal graphs (external observations) ------------------------------------------------


def graph(observations, roots, mode="counterfactual", relevance_mode="annotate", **context):
    return base.execute(
        base.MINIMAL, executable_reason_units="off", state_causality="off", causal_evaluation=mode, causal_observation_source="external",
        causal_observations=observations, causal_relevance=relevance_mode, causal_relevance_roots=roots, **context)


def obs(ru, produces=(), requires=(), requires_any=(), blocked_by=(), success=True):
    return {"ru_id": ru, "produces": list(produces), "requires": list(requires), "requires_any": [list(g) for g in requires_any],
            "blocked_by": list(blocked_by), "success": success}


def test_a_direct_cause_of_the_goal_root_is_essential():
    payload = graph([obs("A", ["E"]), obs("B", requires=["E"])], ["B"])
    assert (entry(payload, "A")["class"], entry(payload, "A")["reasons"]) == ("ESSENTIAL", ["DIRECT_CAUSE", "COUNTERFACTUAL_NECESSARY"])
    assert (entry(payload, "B")["class"], entry(payload, "B")["reasons"]) == ("ESSENTIAL", ["USER_ROOT"])


def test_d_temporal_only_is_noise():
    payload = graph([obs("A", ["E"]), obs("B", requires=["E"]), obs("C")], ["B"])
    assert (entry(payload, "C")["class"], entry(payload, "C")["reasons"]) == ("NOISE", ["TEMPORAL_ONLY"])
    early = graph([obs("X"), obs("A", ["E"]), obs("B", requires=["E"])], ["B"])
    assert entry(early, "X")["class"] == "NOISE"  # executed before, nothing more


def test_e_conflict_is_unresolved():
    payload = graph([obs("P", ["EV"]), obs("T", requires=["EV"], blocked_by=["EV"]), obs("Z")], ["Z"])
    relation = next(r for r in payload["metadata"]["causal_trace"]["relations"] if r["source_ref"] == "P" and r["target_ref"] == "T")
    assert relation["status"] == "CONFLICT"
    for ru in ("P", "T"):
        assert (entry(payload, ru)["class"], "CONFLICT" in entry(payload, ru)["reasons"]) == ("UNRESOLVED", True)


def test_f_insufficient_is_unresolved_when_the_counterfactual_budget_runs_out():
    payload = graph([obs("A", ["E"]), obs("B", requires=["E"]), obs("Z")], ["Z"], max_counterfactual_runs=0)
    assert "CAUSAL-BUDGET-001" in payload["metadata"]["causal_trace"]["diagnostics"]
    assert relevance(payload)["diagnostics"] == ["REL-005"]
    for ru in ("A", "B"):
        assert (entry(payload, ru)["class"], entry(payload, ru)["reasons"]) == ("UNRESOLVED", ["INSUFFICIENT"])


def test_o_alternative_evidence_is_supporting_not_noise():
    payload = graph([obs("A", ["E"]), obs("C", ["E2"]), obs("B", requires_any=[["E", "E2"]])], ["B"])
    for ru in ("A", "C"):
        assert (entry(payload, ru)["class"], entry(payload, ru)["reasons"]) == ("SUPPORTING", ["ALTERNATIVE_DEPENDENCY"])


def test_transitive_cause_is_supporting_and_direct_stays_essential():
    payload = graph([obs("A", ["E1"]), obs("B", ["E2"], requires=["E1"]), obs("C", requires=["E2"])], ["C"])
    assert entry(payload, "B")["class"] == "ESSENTIAL"
    assert (entry(payload, "A")["class"], entry(payload, "A")["reasons"]) == ("SUPPORTING", ["TRANSITIVE_CAUSE"])


def test_preventive_cause_is_essential_when_it_decides_a_relevant_outcome():
    payload = graph([obs("A", ["REJECTION"]), obs("B", blocked_by=["REJECTION"], success=False)], ["B"])
    assert (entry(payload, "A")["class"], entry(payload, "A")["reasons"]) == ("ESSENTIAL", ["PREVENTS"])


def test_depth_beyond_max_causal_depth_is_unresolved_never_dropped():
    chain = [obs("A", ["E1"]), obs("B", ["E2"], requires=["E1"]), obs("C", ["E3"], requires=["E2"]), obs("D", requires=["E3"])]
    payload = graph(chain, ["D"], max_causal_depth=1)
    assert [entry(payload, ru)["class"] for ru in "ABCD"] == ["UNRESOLVED", "UNRESOLVED", "ESSENTIAL", "ESSENTIAL"]
    assert "REL-004" in relevance(payload)["diagnostics"]
    assert all("DEPTH_EXCEEDED" in entry(payload, ru)["reasons"] for ru in "AB")


def test_missing_root_fails_open_to_unresolved():
    payload = graph([obs("A", ["E"]), obs("B", requires=["E"])], [])
    assert relevance(payload)["diagnostics"] == ["REL-001"]
    assert all(c["class"] == "UNRESOLVED" and c["reasons"] == ["NO_ROOT"] for c in relevance(payload)["classifications"])
    unknown = graph([obs("A")], ["nowhere"])
    assert "REL-002" in relevance(unknown)["diagnostics"]


def test_native_and_external_observations_share_one_classification():
    extra = obs("external:probe", ["E"])
    payload = base.execute(base.TEMPLATE.replace("__N__", "77"), causal_relevance="annotate", causal_observation_source="merge", causal_observations=[extra])
    assert classes(payload)["external:probe"] == "NOISE"
    assert {c["ru_ref"]: c["class"] for c in relevance(payload)["classifications"] if c["ru_ref"].startswith("ru:")} == oracle_classes(77)


# --- configuration, schemas ---------------------------------------------------------------------------


def test_configuration_errors():
    def error(**context):
        payload = base.execute(base.MINIMAL, expect_ok=False, **context)
        return payload["diagnostics"][0]["code"]

    assert error(causal_relevance="everything") == "RTH-PROTO-004"
    assert error(causal_relevance="annotate", causal_evaluation="off") == "REL-007"
    assert error(causal_relevance="annotate", causal_evaluation="counterfactual", causal_relevance_roots="ru") == "RTH-PROTO-004"
    off = {"executable_reason_units": "off", "state_causality": "off", "causal_observation_source": "external"}
    assert error(causal_relevance="filter", causal_evaluation="counterfactual", **off) == "RUO-001"
    assert error(causal_relevance="filter", causal_evaluation="counterfactual", state_causality="trace") == "RUO-002"


def test_artifacts_validate_against_the_schemas():
    jsonschema = pytest.importorskip("jsonschema")

    def load(name):
        return json.loads((base.ROOT / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))

    for payload in (run(77), run(84, "annotate"), base.execute(noisy(84), causal_relevance="filter", **FULL)):
        jsonschema.validate(relevance(payload), load("causal_relevance"))
        if "relevant" in relevance(payload):
            jsonschema.validate(relevance(payload)["relevant"]["rus"], load("rus"))
            jsonschema.validate(relevance(payload)["relevant"]["ruo"], load("ruo"))
    request = base.request(base.TEMPLATE.replace("__N__", "77"), causal_relevance="filter", causal_relevance_roots=["ru:x"])
    jsonschema.validate(request, load("runtime_request"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(base.request(base.MINIMAL, causal_relevance="sometimes"), load("runtime_request"))
    broken = json.loads(json.dumps(relevance(run(77))))
    broken["classifications"][0]["class"] = "IRRELEVANT"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(broken, load("causal_relevance"))
    broken = json.loads(json.dumps(relevance(run(77))))
    broken["classifications"][0]["reasons"] = ["BECAUSE"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(broken, load("causal_relevance"))
