"""RRI-026 through RRI-028: Domain Relations and MIRP logical projection."""

import copy

import pytest

from toolchain.reason_object_graph import (
    MIRP_GRAPH_FRAGMENT_SCHEMA,
    project_mirp_fragment,
    project_mirp_relation,
    reference_graph,
    validate_graph,
)


def test_rri_026_domain_relation_is_valid_without_core_override() -> None:
    graph = reference_graph()
    graph["relations"][0].update({"relation_type": "domain:vision:occludes", "direction": "bidirectional"})
    assert validate_graph(graph) == []


def test_rri_027_invalid_relation_namespace_is_rejected() -> None:
    graph = reference_graph()
    graph["relations"][0]["relation_type"] = "vision:occludes"
    assert "RRG-011" in {item["code"] for item in validate_graph(graph)}


def test_rri_028_mirp_graph_fragment_closes_relation_endpoints_deterministically() -> None:
    graph = reference_graph()
    relation_id = graph["relations"][0]["relation_id"]
    first = project_mirp_relation(graph, relation_id)
    second = project_mirp_fragment(copy.deepcopy(graph), relation_ids=[relation_id], fragment_kind="relation")
    assert first["schema"] == MIRP_GRAPH_FRAGMENT_SCHEMA
    assert first["fragment_hash"] == second["fragment_hash"]
    assert [unit["unit_id"] for unit in first["graph"]["units"]] == ["ruo:unit:a", "ruo:unit:b"]
    assert [relation["relation_id"] for relation in first["graph"]["relations"]] == [relation_id]
    assert validate_graph(first["graph"]) == []


def test_mirp_projection_rejects_unresolved_selection() -> None:
    with pytest.raises(ValueError, match="does not resolve"):
        project_mirp_fragment(reference_graph(), unit_ids=["ruo:unit:missing"])
