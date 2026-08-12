"""Phase 11: deterministic read-only ReasonGraph query tests."""

import json
from pathlib import Path

import pytest

from toolchain.reason_object_graph import query_graph, reference_graph
from toolchain.reason_object_graph_cmd import run
from toolchain.reason_object_graph.format import write_graph


ROOT = Path(__file__).resolve().parents[2]


def test_phase11_queries_are_sorted_read_only_and_include_graph_identity() -> None:
    graph = reference_graph()
    original = json.loads(json.dumps(graph))
    result = query_graph(graph, "neighbors", "ruo:unit:a")
    assert graph == original
    assert result["read_only"] is True
    assert result["result"] == [{"relation_id": "ruo:relation:a-causes-b", "direction": "outgoing", "entity_ref": {"entity_kind": "unit", "entity_id": "ruo:unit:b"}}]
    assert result["graph_hash"].startswith("sha256:")


def test_phase11_rejects_unknown_operations_and_entities() -> None:
    with pytest.raises(ValueError, match="RGO-QUERY-002"):
        query_graph(reference_graph(), "mutate")
    with pytest.raises(ValueError, match="RGO-QUERY-003"):
        query_graph(reference_graph(), "entity", "ruo:unit:missing")


def test_phase11_cli_queries_rgraph(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "graph.rgraph"
    write_graph(reference_graph(), source)
    assert run(["query", str(source), "outgoing", "ruo:unit:a", "--json"], ROOT) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["query"] == "outgoing" and len(result["result"]) == 1
