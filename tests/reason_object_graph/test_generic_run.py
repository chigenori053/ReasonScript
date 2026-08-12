"""Phase 19: generic `reason run` routing for graph query sources."""

import json
import subprocess
from pathlib import Path

from toolchain.reason_object_graph import reference_graph, write_graph


ROOT = Path(__file__).resolve().parents[2]


def test_phase19_reason_run_executes_explicit_graph_query_source(tmp_path: Path) -> None:
    build = subprocess.run(["cargo", "build", "--manifest-path", "NativeReasonUnitRuntime/Cargo.toml", "--offline", "--quiet"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert build.returncode == 0, build.stderr
    write_graph(reference_graph(), tmp_path / "graph.rgraph")
    source = tmp_path / "probe.rsn"
    source.write_text('module Probe {\nreason_graph graph from "graph.rgraph";\nquery graph summary;\n}\n', encoding="utf-8")
    completed = subprocess.run(["python3", "-m", "toolchain", "run", str(source), "--allow-read", "--json"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stdout
    assert json.loads(completed.stdout)["results"][0]["result"]["query"] == "summary"
