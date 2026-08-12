"""Phase 8: explicit RUO-U1 to ReasonGraph integration tests."""

import copy

import pytest

from toolchain.reason_object_graph import (
    project_u1_to_graph,
    reverse_u1_projection,
    validate_graph,
)
from toolchain.reasonunit_object.universal import reference_object


def u1_with_unit_relation() -> dict:
    source = reference_object()
    source["relations"][0].update({
        "source_id": "ruo:unit:text",
        "target_id": "ruo:unit:numeric",
        "relation_class": "internal",
        "endpoint_resolution": "resolved",
    })
    return source


def test_phase8_promotes_valid_u1_unit_to_unit_relations_without_mutation() -> None:
    source = u1_with_unit_relation()
    original = copy.deepcopy(source)
    projection = project_u1_to_graph(source)
    assert source == original
    assert validate_graph(projection["graph"]) == []
    assert projection["report"]["canonical_coverage"] is True
    assert projection["report"]["relation_counts"] == {"source": 1, "promoted": 1, "retained_for_reverse_projection": 0}
    assert projection["graph"]["relations"][0]["source"]["entity_id"] == "ruo:unit:text"


def test_phase8_retains_non_unit_u1_relation_losslessly() -> None:
    source = reference_object()
    projection = project_u1_to_graph(source)
    assert projection["report"]["lossless"] is True
    assert projection["report"]["canonical_coverage"] is False
    assert projection["report"]["relation_counts"]["retained_for_reverse_projection"] == 1
    assert reverse_u1_projection(projection)["value"] == source


def test_phase8_rejects_invalid_u1_before_projection() -> None:
    source = u1_with_unit_relation()
    source["relations"][0]["target_id"] = "ruo:unit:missing"
    with pytest.raises(ValueError, match="RGO-U1-002"):
        project_u1_to_graph(source)


def test_phase8_rejects_wrong_reverse_profile() -> None:
    with pytest.raises(ValueError, match="RGO-U1-004"):
        reverse_u1_projection({"report": {"profile": "wrong"}})
