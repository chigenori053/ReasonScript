"""RRI-015 through RRI-017: non-destructive RUO compatibility projection."""

import copy

from toolchain.reason_object_graph import project_to_graph, reverse_project, validate_graph
from toolchain.reasonunit_object.universal import reference_object


def legacy_fixture() -> dict:
    return {
        "object_id": "legacy:example",
        "units": [
            {
                "unit_id": "ruo:unit:a",
                "kind": "claim",
                "state": {"value": "A"},
                "relations": [{"relation_id": "legacy:a-causes-b", "target": "ruo:unit:b", "type": "causes"}],
            },
            {"unit_id": "ruo:unit:b", "kind": "claim", "state": {"value": "B"}},
        ],
    }


def test_rri_015_legacy_ruo_migrates_to_a_valid_reason_graph() -> None:
    source = legacy_fixture()
    original = copy.deepcopy(source)
    projection = project_to_graph(source)
    assert validate_graph(projection["graph"]) == []
    assert projection["report"]["lossless"]
    assert projection["report"]["canonical_coverage"]
    assert projection["report"]["relation_counts"] == {"source": 1, "promoted": 1, "retained_for_reverse_projection": 0}
    assert projection["graph"]["relations"][0]["relation_type"] == "causes"
    assert source == original


def test_rri_016_reverse_projection_restores_the_original_legacy_value() -> None:
    source = legacy_fixture()
    assert reverse_project(project_to_graph(source)) == {"lossless": True, "value": source, "loss_records": []}


def test_rri_017_migration_loss_and_noncoverage_are_explicit() -> None:
    source = reference_object()
    projection = project_to_graph(source)
    assert projection["report"]["lossless"]
    assert not projection["report"]["canonical_coverage"]
    assert projection["report"]["relation_counts"] == {"source": 1, "promoted": 0, "retained_for_reverse_projection": 1}
    assert reverse_project(projection)["value"] == source


def test_non_json_compatible_source_is_reported_as_lossy_without_mutation() -> None:
    source = {"units": [{"unit_id": "ruo:unit:a", "opaque": object()}]}
    projection = project_to_graph(source)
    assert not projection["report"]["lossless"]
    assert projection["report"]["loss_records"][0]["code"] == "RRG-COMP-001"
    assert reverse_project(projection)["value"] is None
