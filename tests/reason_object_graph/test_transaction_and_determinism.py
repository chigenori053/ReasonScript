"""RRI-018 through RRI-025: atomicity and deterministic ReasonGraph behavior."""

import copy
import subprocess
import sys
from pathlib import Path

from toolchain.reason_object_graph import (
    GraphTransaction,
    canonicalize_graph,
    graph_hash,
    reference_graph,
    relation_hash,
    unit_hash,
    validate_graph,
)


ROOT = Path(__file__).resolve().parents[2]


def _new_unit(graph: dict) -> dict:
    unit = copy.deepcopy(graph["units"][1])
    unit.update({"unit_id": "ruo:unit:c", "payload": {"symbol": "C"}})
    return unit


def _new_relation(graph: dict) -> dict:
    relation = copy.deepcopy(graph["relations"][0])
    relation.update({
        "relation_id": "ruo:relation:c-supports-b",
        "source": {"entity_kind": "unit", "entity_id": "ruo:unit:c"},
        "target": {"entity_kind": "unit", "entity_id": "ruo:unit:b"},
        "relation_type": "supports",
    })
    return relation


def test_rri_018_atomic_graph_update_commits_all_valid_changes() -> None:
    graph = reference_graph()
    before = graph_hash(graph)
    result = GraphTransaction(graph).commit(
        {"unit_additions": [_new_unit(graph)], "relation_additions": [_new_relation(graph)]},
        expected_graph_hash=before,
        transaction_id="ruo:transaction:add-c",
    )
    assert result["committed"] and result["partial_commit_count"] == 0
    assert result["changed_unit_ids"] == ["ruo:unit:c"]
    assert result["changed_relation_ids"] == ["ruo:relation:c-supports-b"]
    assert graph_hash(graph) == result["graph_hash"]
    assert validate_graph(graph) == []


def test_rri_019_rollback_retains_the_exact_pre_transaction_graph() -> None:
    graph = reference_graph()
    before_graph = copy.deepcopy(graph)
    before = graph_hash(graph)
    invalid = _new_relation(graph)
    invalid["target"] = {"entity_kind": "unit", "entity_id": "ruo:unit:missing"}
    result = GraphTransaction(graph).commit(
        {"unit_additions": [_new_unit(graph)], "relation_additions": [invalid]},
        expected_graph_hash=before,
        transaction_id="ruo:transaction:rollback",
    )
    assert not result["committed"] and result["partial_commit_count"] == 0
    assert result["reason"] == "validation_failed"
    assert graph == before_graph and graph_hash(graph) == before


def test_rri_020_canonical_serialization_normalizes_equivalent_graphs() -> None:
    graph = reference_graph()
    reordered = copy.deepcopy(graph)
    reordered["units"].reverse()
    reordered["relations"][0]["evidence_refs"] = list(reversed(reordered["relations"][0]["evidence_refs"]))
    assert canonicalize_graph(graph) == canonicalize_graph(reordered)


def test_rri_021_three_independent_runs_are_byte_identical() -> None:
    command = [
        sys.executable,
        "-c",
        "from toolchain.reason_object_graph import canonicalize_graph, reference_graph; print(canonicalize_graph(reference_graph()))",
    ]
    outputs = [subprocess.check_output(command, cwd=ROOT, text=True) for _ in range(3)]
    assert outputs[0] == outputs[1] == outputs[2]


def test_rri_022_input_order_does_not_change_graph_identity() -> None:
    graph = reference_graph()
    reordered = copy.deepcopy(graph)
    reordered["units"].reverse()
    assert graph_hash(graph) == graph_hash(reordered)


def test_rri_023_unit_hash_is_stable() -> None:
    unit = reference_graph()["units"][0]
    reordered = {key: copy.deepcopy(unit[key]) for key in reversed(list(unit))}
    assert unit_hash(unit) == unit_hash(reordered)


def test_rri_024_relation_hash_is_stable() -> None:
    relation = reference_graph()["relations"][0]
    reordered = {key: copy.deepcopy(relation[key]) for key in reversed(list(relation))}
    assert relation_hash(relation) == relation_hash(reordered)


def test_rri_025_graph_hash_is_independent_of_registry_order() -> None:
    graph = reference_graph()
    reordered = copy.deepcopy(graph)
    reordered["units"].reverse()
    reordered["relations"] = list(reversed(reordered["relations"]))
    assert graph_hash(graph) == graph_hash(reordered)
