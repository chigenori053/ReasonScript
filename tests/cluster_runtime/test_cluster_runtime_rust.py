"""Repository integration tests for the Rust Cluster Runtime extension."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CRATE = ROOT / "ClusterRuntime"
REASON = ROOT / "reason"
SOURCE = ROOT / "examples" / "v0_8" / "reasoning_runtime" / "calculation_chain.rsn"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(REASON), "cluster", *args, "--json"], cwd=ROOT, text=True, capture_output=True, check=False)


def test_rust_cluster_runtime_crate_passes() -> None:
    result = subprocess.run(["cargo", "test", "--offline", "--quiet"], cwd=CRATE, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_cluster_cli_simulation_and_single_node_comparison() -> None:
    simulation = _run("simulate", str(SOURCE), "--workers", "3")
    assert simulation.returncode == 0, simulation.stderr
    assert json.loads(simulation.stdout)["status"] == "completed"
    comparison = _run("compare", str(SOURCE), "--workers", "3")
    assert comparison.returncode == 0, comparison.stderr
    assert json.loads(comparison.stdout)["equivalent"] is True


def test_local_process_workers_and_all_artifacts(tmp_path: Path) -> None:
    local = _run("test-model", "--scenario", "independent-parallel", "--workers", "4", "--mode", "local_process")
    assert local.returncode == 0, local.stderr
    assert json.loads(local.stdout)["passed"] is True
    run = _run("run", str(SOURCE), "--artifacts-dir", str(tmp_path))
    assert run.returncode == 0, run.stderr
    validation = _run("validate", str(tmp_path))
    assert validation.returncode == 0, validation.stderr
    assert json.loads(validation.stdout) == {"artifact_count": 9, "diagnostics": [], "valid": True}


def test_dynamic_reason_unit_scenarios() -> None:
    scenarios = (
        "independent-parallel", "dependency-chain", "fan-out-fan-in", "state-conflict",
        "worker-failure", "determinism", "single-node-equivalence", "fallback",
        "molecular-partition",
    )
    for scenario in scenarios:
        result = _run("test-model", "--scenario", scenario, "--workers", "4")
        assert result.returncode == 0, f"{scenario}: {result.stderr}"
        assert json.loads(result.stdout)["passed"] is True
