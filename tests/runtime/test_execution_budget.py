"""P0-2: the fixed 10,000 loop cap is gone; Execution Budgets stop runs."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.runtime.conftest import HOST, execute

ROOT = Path(__file__).resolve().parents[2]

COUNT_LOOP = """
    let i = 0
    while i < {n} {{
        i = i + 1
    }}
    result = i
"""


def test_no_fixed_loop_cap_without_limits():
    # P0-A: 50,000 iterations used to die with RT-LOOP-001 at 10,000.
    outcome = execute(COUNT_LOOP.format(n=50_000))
    assert outcome.ok, (outcome.error_code, outcome.error_message)
    assert outcome.calculation_results == {"Answer": 50_000}
    metrics = outcome.metadata["runtime_metrics"]
    assert metrics["loop_iteration_count"] == 50_000
    assert outcome.metadata["termination_reason"] == "completed"


def test_loop_iteration_budget_stops_with_rt_budget_005():
    outcome = execute(COUNT_LOOP.format(n=10), limits={"max_loop_iterations": 5})
    assert not outcome.ok
    assert outcome.error_code == "RT-BUDGET-005"
    assert outcome.metadata["termination_reason"] == "loop_iteration_budget"
    # Metrics are reported for a stopped run too, showing how far it got.
    assert outcome.metadata["runtime_metrics"]["loop_iteration_count"] == 6


def test_zero_means_unlimited():
    outcome = execute(COUNT_LOOP.format(n=20), limits={"max_loop_iterations": 0})
    assert outcome.ok and outcome.calculation_results == {"Answer": 20}


def test_reasoning_step_budget_stops_with_rt_budget_004():
    outcome = execute("""
        let i = 0
        while i < 10 {
            reasoning.event("HYPOTHESIS_REJECTED", "candidate", i)
            i = i + 1
        }
        result = i
    """, limits={"max_reasoning_steps": 3})
    assert outcome.error_code == "RT-BUDGET-004"
    assert outcome.metadata["termination_reason"] == "reasoning_step_budget"
    assert outcome.metadata["runtime_metrics"]["reasoning_step_count"] == 4


def test_vm_instruction_budget_stops_with_rt_budget_003():
    outcome = execute(COUNT_LOOP.format(n=1000), limits={"max_vm_instructions": 100})
    assert outcome.error_code == "RT-BUDGET-003"
    assert outcome.metadata["termination_reason"] == "vm_instruction_budget"
    assert outcome.metadata["runtime_metrics"]["vm_instruction_count"] == 101


def test_wall_time_budget_stops_with_rt_budget_001():
    outcome = execute("""
        let i = 0
        while true {
            i = i + 1
        }
        result = i
    """, limits={"max_wall_time_ms": 100})
    assert outcome.error_code == "RT-BUDGET-001"
    assert outcome.metadata["termination_reason"] == "wall_time_budget"
    assert outcome.metadata["runtime_metrics"]["loop_iteration_count"] > 0


def test_wall_time_budget_wins_over_loop_budget_when_both_exhausted():
    # Priority order (spec section 16): a run that is already past its wall
    # budget reports RT-BUDGET-001 even though the loop budget is exhausted too.
    outcome = execute("""
        let i = 0
        while true {
            i = i + 1
        }
        result = i
    """, limits={"max_wall_time_ms": 50, "max_loop_iterations": 10_000_000_000})
    assert outcome.error_code == "RT-BUDGET-001"


def test_cli_flags_and_termination_reason(tmp_path):
    source = tmp_path / "loop.rsn"
    source.write_text("module Loop {\n  calculation Main {\n    let i = 0\n    while i < 100 {\n      i = i + 1\n    }\n    result = i\n  }\n}\n")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "reason"), "run", str(source), "--json", "--trace=off", "--max-loop-iterations", "5"],
        capture_output=True, text=True, cwd=ROOT,
    )
    payload = json.loads(completed.stdout)
    assert not payload["ok"]
    diagnostic = payload["diagnostics"][0]
    assert diagnostic["code"] == "RT-BUDGET-005"
    assert diagnostic["termination_reason"] == "loop_iteration_budget"
    assert diagnostic["runtime_metrics"]["loop_iteration_count"] == 6

    completed = subprocess.run(
        [sys.executable, str(ROOT / "reason"), "run", str(source), "--json", "--trace=summary", "--max-reasoning-steps=100000"],
        capture_output=True, text=True, cwd=ROOT,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"], payload.get("diagnostics")
    assert payload["runtime_result"]["termination_reason"] == "completed"
    assert payload["runtime_result"]["runtime_metrics"]["trace_mode"] == "off"
