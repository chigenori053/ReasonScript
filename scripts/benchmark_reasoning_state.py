#!/usr/bin/env python3
"""Lightweight RUS v0.1 overhead benchmark (host boundary, trace off).

Correctness comes first: this only reports overhead against the spec's
reference targets (Lightweight RUS <= 10%, with State Causality <= 20%, both
relative to executable RU `full`). A formal evaluation additionally needs
`working_tree_dirty == false`, which the report records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frontend.computation_ir import lower_program
from frontend.computation_ir.rust_bridge import find_binary
from frontend.language_surface import parse

TEMPLATE = ROOT / "computation_ir_tests/golden_reasoning_state/factorize.rsn.template"
DEFAULT_OUT = ROOT / "artifacts/reasoning_state_benchmark/summary.json"
CASES = (77, 997, 10007, 30030, 10403)  # semiprime, primes, highly composite, larger semiprime
CONFIGS = {
    "normal": {"executable_reason_units": "off"},
    "ru_full": {"executable_reason_units": "full"},
    "lightweight_rus": {"executable_reason_units": "full", "reasoning_state": "lightweight"},
    "state_causality": {"executable_reason_units": "full", "state_causality": "full"},
    "state_causality_native_causal": {
        "executable_reason_units": "full",
        "state_causality": "full",
        "causal_evaluation": "counterfactual",
        "causal_observation_source": "native",
    },
}
TARGETS = {"lightweight_rus": 0.10, "state_causality": 0.20}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()


def run(binary: Path, program: dict, context: dict) -> dict:
    request = {
        "schema": "reasonscript-runtime-request/1.0",
        "request_id": "reasoning-state-benchmark",
        "operation": "execute",
        "program": program,
        "context": {
            "resource_root": ".",
            "capabilities": {},
            "limits": {"max_loop_iterations": 1_000_000},
            "trace": {"enabled": False},
            "numeric_mode": "compat-reference",
            "benchmark_metrics": True,
            **context,
        },
    }
    completed = subprocess.run([str(binary)], input=json.dumps(request), text=True, capture_output=True)
    payload = json.loads(completed.stdout)
    assert payload["ok"], payload
    return payload


def median_ns(binary: Path, program: dict, context: dict, warmup: int, samples: int) -> tuple[int, dict]:
    for _ in range(warmup):
        run(binary, program, context)
    payloads = [run(binary, program, context) for _ in range(samples)]
    return int(statistics.median(p["metadata"]["runtime_metrics"]["runtime_execution_ns"] for p in payloads)), payloads[-1]


def component_ns(payload: dict) -> dict:
    meta = payload["metadata"]
    return {
        "normal_runtime_ns": meta["causal_trace"]["metrics"]["normal_runtime_ns"],
        "reasoning_state_runtime_ns": meta["reasoning_state"]["metrics"]["reasoning_state_runtime_ns"],
        "state_causality_runtime_ns": meta["state_causality"]["metrics"]["state_causality_runtime_ns"],
        "causal_bridge_runtime_ns": meta["causal_bridge"]["metrics"]["causal_bridge_runtime_ns"],
        "causal_evaluation_ns": meta["causal_trace"]["metrics"]["causal_evaluation_ns"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, default=find_binary())
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--samples", type=int, default=15)
    args = parser.parse_args()
    binary = args.binary.resolve()
    dirty = bool(git("status", "--porcelain"))
    cases = []
    for n in CASES:
        program = lower_program(parse(TEMPLATE.read_text().replace("__N__", str(n))))
        medians, last = {}, {}
        for name, context in CONFIGS.items():
            medians[name], last[name] = median_ns(binary, program, context, args.warmup, args.samples)
        overhead = {name: medians[name] / medians["ru_full"] - 1 for name in TARGETS}
        cases.append(
            {
                "n": n,
                "runtime_execution_ns": medians,
                "overhead_vs_ru_full": overhead,
                "state_revision_count": last["state_causality"]["metadata"]["reasoning_state"]["revision"],
                "components_ns": component_ns(last["state_causality_native_causal"]),
            }
        )
    totals = {name: sum(case["runtime_execution_ns"][name] for case in cases) for name in CONFIGS}
    summary = {
        "schema": "reasonscript-reasoning-state-benchmark/1.0",
        "source_commit": git("rev-parse", "HEAD"),
        "working_tree_dirty": dirty,
        "formal_evaluation": not dirty,
        "runtime_binary_path": str(binary),
        "runtime_binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "warmup": args.warmup,
        "samples": args.samples,
        "cases": cases,
        "total_runtime_execution_ns": totals,
        "overhead_vs_ru_full": {name: totals[name] / totals["ru_full"] - 1 for name in TARGETS},
        "reference_targets": TARGETS,
        "within_reference": {name: totals[name] / totals["ru_full"] - 1 <= limit for name, limit in TARGETS.items()},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ("working_tree_dirty", "total_runtime_execution_ns", "overhead_vs_ru_full", "within_reference")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
