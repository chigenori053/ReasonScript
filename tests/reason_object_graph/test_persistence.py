"""Phase 13: atomic RGO-F1 persistence transaction tests."""

import json

from toolchain.reason_object_graph import graph_hash, reference_graph, transact_graph_file
from toolchain.reason_object_graph.format import read_graph, write_graph
from toolchain.reason_object_graph_cmd import run


def test_phase13_commits_valid_update_and_rejects_stale_update_without_file_mutation(tmp_path) -> None:
    path = tmp_path / "graph.rgraph"
    write_graph(reference_graph(), path)
    before = graph_hash(reference_graph())
    committed = transact_graph_file(path, {"graph_updates": {"metadata": {"persisted": True}}}, expected_graph_hash=before, transaction_id="ruo:transaction:persist")
    assert committed["committed"] and read_graph(path)["metadata"] == {"persisted": True}
    bytes_after_commit = path.read_bytes()
    rejected = transact_graph_file(path, {}, expected_graph_hash=before, transaction_id="ruo:transaction:stale")
    assert not rejected["committed"] and rejected["source_bytes_unchanged"] and path.read_bytes() == bytes_after_commit


def test_phase13_cli_commits_a_proposal_file(tmp_path, capsys) -> None:
    path, proposal = tmp_path / "graph.rgraph", tmp_path / "proposal.json"
    graph = reference_graph(); write_graph(graph, path)
    proposal.write_text(json.dumps({"graph_updates": {"metadata": {"via": "cli"}}}), encoding="utf-8")
    assert run(["transact", str(path), "--proposal", str(proposal), "--expected-hash", graph_hash(graph), "--transaction-id", "ruo:transaction:cli", "--json"], tmp_path) == 0
    assert json.loads(capsys.readouterr().out)["committed"] is True
