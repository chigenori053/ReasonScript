"""Phase 17: ReasonScript read-only ReasonGraph operation tests."""

import json
import subprocess
from pathlib import Path

import pytest

from toolchain.reason_object_graph import compile_graph_source, execute_graph_source, graph_hash, reference_graph, write_graph
from toolchain.reason_object_graph_cmd import run


ROOT = Path(__file__).resolve().parents[2]
SOURCE = '''module GraphProbe {
reason_graph graph from "graph.rgraph" as "ruo:graph:phase2-fixture";
query graph neighbors "ruo:unit:a";
query graph summary;
}
'''


def test_phase17_compiles_and_executes_read_only_reason_graph_source(tmp_path: Path) -> None:
    build = subprocess.run(["cargo", "build", "--manifest-path", "ReasonRuntime/crates/reason-object-core/Cargo.toml", "--offline", "--quiet"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert build.returncode == 0, build.stderr
    source_path = tmp_path / "probe.rsn"; graph_path = tmp_path / "graph.rgraph"
    source_path.write_text(SOURCE, encoding="utf-8"); write_graph(reference_graph(), graph_path)
    compiled = compile_graph_source(SOURCE)
    assert compiled["read_only"] is True and len(compiled["operations"]) == 2
    result = execute_graph_source(SOURCE, source_path, root=ROOT, filesystem_read=True)
    assert [item["result_parity"] for item in result["results"]] == [True, True]


def test_phase17_requires_explicit_read_capability_and_safe_source_shape(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source_path = tmp_path / "probe.rsn"; source_path.write_text(SOURCE, encoding="utf-8")
    with pytest.raises(PermissionError, match="RGO-LANG-004"):
        execute_graph_source(SOURCE, source_path, root=ROOT, filesystem_read=False)
    assert run(["source-check", str(source_path), "--json"], ROOT) == 0
    assert json.loads(capsys.readouterr().out)["read_only"] is True
    with pytest.raises(ValueError, match="RGO-LANG-002"):
        compile_graph_source('module Bad {\nreason_graph graph from "../secret.rgraph";\nquery graph summary;\n}\n')


def test_phase20_source_transaction_requires_write_capability(tmp_path: Path) -> None:
    graph = reference_graph(); write_graph(graph, tmp_path / "graph.rgraph")
    (tmp_path / "proposal.json").write_text(json.dumps({"graph_updates": {"metadata": {"via": "source"}}}), encoding="utf-8")
    source = f'module Update {{\nreason_graph graph from "graph.rgraph";\ntransact graph "proposal.json" "{graph_hash(graph)}" "ruo:transaction:source";\n}}\n'
    source_path = tmp_path / "update.rsn"; source_path.write_text(source, encoding="utf-8")
    with pytest.raises(PermissionError, match="RGO-LANG-008"):
        execute_graph_source(source, source_path, root=ROOT, filesystem_read=True)
    result = execute_graph_source(source, source_path, root=ROOT, filesystem_read=True, filesystem_write=True)
    assert result["read_only"] is False and result["results"][0]["transaction"]["committed"] is True
