"""RRI-001 through RRI-014: Phase 2 Reason Object Graph reference tests."""

import copy

import pytest

from toolchain.reason_object_graph import MAX_RELATION_DEPTH, reference_graph, validate_graph


def codes(value: dict) -> set[str]:
    return {item["code"] for item in validate_graph(value)}


def test_rri_001_unit_to_unit_relation_is_valid() -> None:
    assert validate_graph(reference_graph()) == []


def test_rri_002_directed_relation_is_valid() -> None:
    graph = reference_graph()
    graph["relations"][0].update({"relation_type": "causes", "direction": "directed"})
    assert validate_graph(graph) == []


def test_rri_003_symmetric_relation_is_valid() -> None:
    graph = reference_graph()
    graph["relations"][0].update({"relation_type": "equivalent_to", "direction": "symmetric"})
    assert validate_graph(graph) == []


def test_rri_004_relation_evidence_is_retained() -> None:
    graph = reference_graph()
    graph["relations"][0]["evidence_refs"] = ["ruo:evidence:one", "ruo:evidence:two"]
    assert validate_graph(graph) == []


def test_rri_005_relation_provenance_is_required() -> None:
    graph = reference_graph()
    graph["relations"][0]["provenance"].pop("producer")
    assert "RRG-008" in codes(graph)


@pytest.mark.parametrize(
    "scope",
    [
        {"kind": "instant", "at": "T0"},
        {"kind": "interval", "valid_from": "T0", "valid_until": "T1"},
        {"kind": "persistent"},
        {"kind": "unknown"},
    ],
)
def test_rri_006_temporal_relation_is_valid(scope: dict) -> None:
    graph = reference_graph()
    graph["relations"][0]["temporal_scope"] = scope
    assert validate_graph(graph) == []


@pytest.mark.parametrize("lifecycle", ["proposed", "active", "suspended", "invalidated", "retired"])
def test_rri_007_relation_lifecycle_is_valid(lifecycle: str) -> None:
    graph = reference_graph()
    graph["relations"][0]["lifecycle"] = lifecycle
    assert validate_graph(graph) == []


@pytest.mark.parametrize("state", ["unverified", "validated", "disputed", "rejected"])
def test_rri_008_relation_validation_state_is_independent(state: str) -> None:
    graph = reference_graph()
    graph["relations"][0].update({"lifecycle": "active", "validation_state": state})
    assert validate_graph(graph) == []


def test_rri_009_contradictory_relations_are_valid_graph_data() -> None:
    graph = reference_graph()
    contradiction = copy.deepcopy(graph["relations"][0])
    contradiction.update({"relation_id": "ruo:relation:a-contradicts-b", "relation_type": "contradicts"})
    graph["relations"].append(contradiction)
    assert validate_graph(graph) == []


def test_rri_010_unit_to_relation_is_valid_at_depth_one() -> None:
    graph = reference_graph()
    support = copy.deepcopy(graph["relations"][0])
    support.update({
        "relation_id": "ruo:relation:b-supports-a-causes-b",
        "source": {"entity_kind": "unit", "entity_id": "ruo:unit:b"},
        "target": {"entity_kind": "relation", "entity_id": "ruo:relation:a-causes-b"},
        "relation_type": "supports",
    })
    graph["relations"].append(support)
    assert MAX_RELATION_DEPTH == 1
    assert validate_graph(graph) == []


def test_rri_011_illegal_recursion_is_rejected() -> None:
    graph = reference_graph()
    first = copy.deepcopy(graph["relations"][0])
    first.update({
        "relation_id": "ruo:relation:b-supports-a-causes-b",
        "source": {"entity_kind": "unit", "entity_id": "ruo:unit:b"},
        "target": {"entity_kind": "relation", "entity_id": "ruo:relation:a-causes-b"},
        "relation_type": "supports",
    })
    second = copy.deepcopy(first)
    second.update({
        "relation_id": "ruo:relation:a-supports-b-supports-a-causes-b",
        "source": {"entity_kind": "unit", "entity_id": "ruo:unit:a"},
        "target": {"entity_kind": "relation", "entity_id": first["relation_id"]},
    })
    graph["relations"].extend([first, second])
    assert "RRG-017" in codes(graph)


def test_rri_012_missing_unit_is_rejected() -> None:
    graph = reference_graph()
    graph["relations"][0]["target"]["entity_id"] = "ruo:unit:missing"
    assert "RRG-014" in codes(graph)


def test_rri_013_duplicate_unit_id_is_rejected() -> None:
    graph = reference_graph()
    graph["units"].append(copy.deepcopy(graph["units"][0]))
    assert "RRG-004" in codes(graph)


def test_rri_014_duplicate_relation_id_is_rejected() -> None:
    graph = reference_graph()
    graph["relations"].append(copy.deepcopy(graph["relations"][0]))
    assert "RRG-006" in codes(graph)
