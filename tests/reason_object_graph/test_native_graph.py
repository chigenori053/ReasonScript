"""Phase 14: immutable native RGO-F1 loader tests."""

import subprocess
from pathlib import Path

import json

from toolchain.reason_object_graph import graph_hash, load_native_graph_file, query_native_graph_file, reference_graph, transact_native_graph_file, write_graph


ROOT = Path(__file__).resolve().parents[2]


def test_phase14_native_graph_loader_has_rgo_f1_identity_parity(tmp_path: Path) -> None:
    build = subprocess.run(["cargo", "build", "--manifest-path", "ReasonRuntime/crates/reason-object-core/Cargo.toml", "--offline", "--quiet"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert build.returncode == 0, build.stderr
    source = tmp_path / "graph.rgraph"
    write_graph(reference_graph(), source)

    result = load_native_graph_file(source, root=ROOT)

    assert result["report"]["graph_identity_parity"] is True
    assert result["report"]["graph_entity_identity_parity"] is True
    assert result["native_graph"]["read_only"] is True


def test_phase14_native_graph_loader_rejects_tampered_rgo_f1(tmp_path: Path) -> None:
    build = subprocess.run(["cargo", "build", "--manifest-path", "ReasonRuntime/crates/reason-object-core/Cargo.toml", "--offline", "--quiet"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert build.returncode == 0, build.stderr
    source = tmp_path / "graph.rgraph"
    write_graph(reference_graph(), source)
    source.write_bytes(source.read_bytes().replace(b'"ordinal":1', b'"ordinal":9', 1))

    try:
        load_native_graph_file(source, root=ROOT)
    except ValueError as error:
        assert "rejected RGO-F1" in str(error)
    else:
        raise AssertionError("tampered RGO-F1 must be rejected")


def test_phase15_native_graph_queries_match_python_contract(tmp_path: Path) -> None:
    build = subprocess.run(["cargo", "build", "--manifest-path", "ReasonRuntime/crates/reason-object-core/Cargo.toml", "--offline", "--quiet"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert build.returncode == 0, build.stderr
    source = tmp_path / "graph.rgraph"
    write_graph(reference_graph(), source)

    for query, entity_id in [("summary", None), ("entity", "ruo:unit:a"), ("outgoing", "ruo:unit:a"), ("incoming", "ruo:unit:b"), ("neighbors", "ruo:unit:a")]:
        result = query_native_graph_file(source, query, entity_id, root=ROOT)
        assert result["report"]["result_parity"] is True
        assert result["result"]["read_only"] is True


def test_phase16_native_metadata_transaction_is_atomic_and_matches_python(tmp_path: Path) -> None:
    build = subprocess.run(["cargo", "build", "--manifest-path", "ReasonRuntime/crates/reason-object-core/Cargo.toml", "--offline", "--quiet"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert build.returncode == 0, build.stderr
    source, proposal = tmp_path / "graph.rgraph", tmp_path / "proposal.json"
    graph = reference_graph(); write_graph(graph, source)
    proposal.write_text(json.dumps({"graph_updates": {"metadata": {"native": True}}}), encoding="utf-8")

    committed = transact_native_graph_file(source, proposal, expected_graph_hash=graph_hash(graph), transaction_id="ruo:transaction:native-phase16", root=ROOT)
    assert committed["transaction"]["committed"] is True
    bytes_after_commit = source.read_bytes()
    rejected = transact_native_graph_file(source, proposal, expected_graph_hash=graph_hash(graph), transaction_id="ruo:transaction:native-stale", root=ROOT)
    assert rejected["transaction"]["committed"] is False
    assert source.read_bytes() == bytes_after_commit
