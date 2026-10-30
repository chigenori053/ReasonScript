"""Native graph reasoning: ordering, evidence safety, and large independent input."""
from copy import deepcopy
from pathlib import Path
import pytest
from frontend.language_surface import parse
from frontend.computation_ir import lower_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/inference_scale/main.rsn"
pytestmark = pytest.mark.skipif(find_binary() is None, reason="native host not built")


def unit(uid, subject, target, status="VERIFIED"):
    return dict(unit_id=uid, unit_kind="RU", semantic_status=status,
                state_representation="discrete", evidence=[uid], dependencies=[],
                proof_path=[], revision=1, provenance=["test"], validation_status="VALID",
                subject=subject, object=target, predicate=1, polarity=1,
                current_revision=1, negative_evidence=[], revoked=False)


def binding(u):
    return dict(evidence_id=u["evidence"][0], **{k: u[k] for k in
                ("unit_id", "subject", "predicate", "object", "polarity", "revision")})


def derive(units, trusted=None, **overrides):
    inputs = dict(units=units, trusted=[binding(u) for u in units] if trusted is None else trusted,
                  entities=[0, 1, 2, 3], start=0, goal=3, depth=3, path_budget=100)
    inputs.update(overrides)
    outcome = run_ir(lower_program(parse(SOURCE.read_text())), entry="UnifiedB::Derive",
                     inputs=inputs, limits=dict(max_input_elements=5_000_000,
                                               max_input_bytes=536_870_912,
                                               max_loop_iterations=10_000_000))
    assert outcome.ok, outcome.error_message
    return next(iter(outcome.calculation_results.values()))["fields"]


def test_stable_paths_unknown_dependencies_and_contradiction():
    units = [unit("z", 0, 1), unit("b", 1, 3), unit("a", 0, 2),
             unit("c", 2, 3, "UNKNOWN")]
    r = derive(units)
    assert r["status"] == "VERIFIED"
    assert r["proof_path"] == ["z", "b"]
    assert r["all_paths"] == [["z", "b"], ["a", "c"]]
    assert r["dependencies"] == ["c"]
    negative = unit("negative", 0, 3); negative["polarity"] = -1
    assert derive(units + [negative])["status"] == "CONTRADICTED"


def test_duplicate_empty_id_and_path_budget_are_rejected():
    u = unit("", 0, 3)
    assert not derive([u, deepcopy(u)])["admitted"]
    assert derive([u])["status"] == "VERIFIED"
    r = derive([unit("a", 0, 3), unit("b", 0, 3)], path_budget=1)
    assert r["resource_limit"] and not r["admitted"] and r["proof_path"] == []


@pytest.mark.parametrize("field,value", [("unit_id", "other"), ("subject", 8),
    ("predicate", 2), ("object", 8), ("polarity", -1), ("revision", 2)])
def test_evidence_cannot_be_rebound(field, value):
    u = unit("a", 0, 3); bad = binding(u); bad[field] = value
    assert derive([u], trusted=[bad])["status"] == "UNKNOWN"
    # Equal evidence IDs may legitimately have multiple bindings. Search the whole bucket.
    assert derive([u], trusted=[bad, binding(u)])["status"] == "VERIFIED"


@pytest.mark.parametrize("field,value", [("revoked", True), ("current_revision", 2),
    ("provenance", []), ("evidence", [])])
def test_invalid_units_never_verify(field, value):
    u = unit("a", 0, 3); trusted = [binding(u)]; u[field] = value
    assert derive([u], trusted=trusted)["status"] == "UNKNOWN"


def test_ten_thousand_units_with_real_proof():
    units = [unit(str(i), i + 10, i + 11) for i in range(9_998)]
    units += [unit("start", 0, 1), unit("goal", 1, 3)]
    r = derive(units)
    assert r["admitted"] and r["status"] == "VERIFIED"
    assert r["proof_path"] == ["start", "goal"]


def test_shared_evidence_id_does_not_scan_all_units():
    units = [unit(str(i), i + 10, i + 11) for i in range(9_998)]
    units += [unit("start", 0, 1), unit("goal", 1, 3)]
    for u in units:
        u["evidence"] = ["shared-evidence"]
    r = derive(units)
    assert r["admitted"] and r["status"] == "VERIFIED"
    assert r["proof_path"] == ["start", "goal"]
