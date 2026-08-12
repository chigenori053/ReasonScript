"""Phase 9: read-only RUO-F1 to ReasonGraph integration tests."""

from pathlib import Path

import pytest

from toolchain.reason_object_graph import (
    decode_graph,
    project_ruo_file,
    project_ruo_file_to_rgraph,
    validate_graph,
)
from toolchain.reasonunit_file import write_file
from toolchain.reasonunit_object.universal import reference_object


def u1_with_unit_relation() -> dict:
    source = reference_object()
    source["relations"][0].update({"source_id": "ruo:unit:text", "target_id": "ruo:unit:numeric", "relation_class": "internal", "endpoint_resolution": "resolved"})
    return source


def test_phase9_projects_a_verified_ruo_file_without_changing_its_bytes(tmp_path: Path) -> None:
    source = tmp_path / "source.ruo"
    write_file(u1_with_unit_relation(), source)
    before = source.read_bytes()
    projection = project_ruo_file(source)
    assert source.read_bytes() == before
    assert validate_graph(projection["graph"]) == []
    assert projection["report"]["source_path"] == "source.ruo"
    assert projection["report"]["canonical_coverage"] is True


def test_phase9_publishes_a_canonical_rgraph_from_ruo(tmp_path: Path) -> None:
    source, target = tmp_path / "source.ruo", tmp_path / "graph.rgraph"
    write_file(u1_with_unit_relation(), source)
    result = project_ruo_file_to_rgraph(source, target)
    assert result["publication"]["ok"] is True
    assert decode_graph(target.read_bytes()) == result["graph"]


def test_phase9_rejects_invalid_ruo_before_projection(tmp_path: Path) -> None:
    source = tmp_path / "invalid.ruo"
    source.write_text("not a canonical RUO file\n", encoding="utf-8")
    with pytest.raises(ValueError, match="RGO-F1-001"):
        project_ruo_file(source)
