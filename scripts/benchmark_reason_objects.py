#!/usr/bin/env python3
"""RUS / RUO projection overhead: R4 vs R4 + RUS vs R4 + RUS + RUO.

Host boundary, all configurations with `executable_reason_units=full` and
`state_causality=full` (RUO needs the causal relations it references). Two costs
are kept apart (RUS / RUO Runtime Integration v0.1, §114):

* execution hot path: `runtime_execution_ns` (`run_calculations`); reference
  targets RUS <= +5%, RUO <= +10%, HOLD above +20%;
* end to end: whole host process wall time, which also contains projection,
  serialization, and printing of the response; reference target <= +20%.

The baseline binary (main before the projection) only runs the `r4`
configuration, so the projection build is also checked for hot-path regressions.

    scripts/benchmark_reason_objects.py --baseline-binary <main host> --binary <host> \
        [--profile <in-process harness>]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import benchmark_reasoning_state as bench

CONFIGS = {
    "r4": {"executable_reason_units": "full", "state_causality": "full"},
    "rus": {"executable_reason_units": "full", "state_causality": "full", "reason_objects": "rus"},
    "rus_ruo": {"executable_reason_units": "full", "state_causality": "full", "reason_objects": "rus_ruo"},
}
TARGETS = {"rus": 0.05, "rus_ruo": 0.10}  # hot-path reference targets
HOLD = 0.20
END_TO_END_TARGET = 0.20


def timed(binary: Path, n: int, context: dict) -> tuple[int, int, dict]:
    request = json.dumps({
        "schema": "reasonscript-runtime-request/1.0",
        "request_id": "reason-objects-benchmark",
        "operation": "execute",
        "program": bench.program(n),
        "context": {"resource_root": ".", "capabilities": {}, "limits": {"max_loop_iterations": 1_000_000},
                    "trace": {"enabled": False}, "numeric_mode": "compat-reference", "benchmark_metrics": True, **context},
    })
    started = time.perf_counter_ns()
    completed = subprocess.run([str(binary)], input=request, text=True, capture_output=True)
    wall = time.perf_counter_ns() - started
    payload = json.loads(completed.stdout)
    assert payload["ok"], payload
    return payload["metadata"]["runtime_metrics"]["runtime_execution_ns"], wall, payload["metadata"]


def measure(baseline: Path, binary: Path, warmup: int, samples: int) -> dict:
    result: dict = {}
    for n in bench.CASES:
        hot = {key: [] for key in ("baseline_r4", *CONFIGS)}
        wall = {key: [] for key in ("baseline_r4", *CONFIGS)}
        last = {}
        for sample in range(warmup + samples):
            plan = [("baseline_r4", baseline, CONFIGS["r4"]), *((name, binary, context) for name, context in CONFIGS.items())]
            for name, host, context in plan:
                execution_ns, wall_ns, metadata = timed(host, n, context)
                if sample >= warmup:
                    hot[name].append(execution_ns)
                    wall[name].append(wall_ns)
                last[name] = metadata
        result[n] = {
            "hot_path_ns": {k: int(statistics.median(v)) for k, v in hot.items()},
            "wall_ns": {k: int(statistics.median(v)) for k, v in wall.items()},
            "transitions": last["r4"]["state_causality"]["metrics"]["state_transition_count"],
            "rus_states": last["rus_ruo"]["rus"]["metrics"]["rus_projection_count"],
            "ruo_objects": last["rus_ruo"]["ruo"]["metrics"]["ruo_count"],
            "projection_ns": {
                "rus_materialization_ns": last["rus_ruo"]["rus"]["metrics"]["rus_materialization_ns"],
                "rus_hash_ns": last["rus_ruo"]["rus"]["metrics"]["rus_hash_ns"],
                "ruo_materialization_ns": last["rus_ruo"]["ruo"]["metrics"]["ruo_materialization_ns"],
                "ruo_hash_ns": last["rus_ruo"]["ruo"]["metrics"]["ruo_hash_ns"],
            },
        }
    return result


def overhead(cases: dict, key: str, metric: str, reference: str = "r4") -> float:
    return sum(c[metric][key] for c in cases.values()) / sum(c[metric][reference] for c in cases.values()) - 1


def in_process(profile: Path, iterations: int) -> dict:
    result: dict = {}
    with tempfile.TemporaryDirectory() as directory:
        for n in bench.CASES:
            path = Path(directory) / f"program-{n}.json"
            path.write_text(json.dumps(bench.program(n)), encoding="utf-8")
            for config in ("causality", "objects_rus", "objects_ruo"):
                completed = subprocess.run([str(profile), str(path), config, str(iterations)], text=True, capture_output=True, check=True)
                result.setdefault(n, {})[config] = json.loads(completed.stdout)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-binary", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/reason_objects")
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--samples", type=int, default=25)
    parser.add_argument("--profile-iterations", type=int, default=2000)
    args = parser.parse_args()
    dirty = bool(bench.git("status", "--porcelain"))
    cases = measure(args.baseline_binary, args.binary, args.warmup, args.samples)
    hot = {name: overhead(cases, name, "hot_path_ns") for name in TARGETS}
    end_to_end = {name: overhead(cases, name, "wall_ns") for name in TARGETS}
    guard = overhead(cases, "r4", "hot_path_ns", "baseline_r4")
    per_case = {
        n: {name: c["hot_path_ns"][name] / c["hot_path_ns"]["r4"] - 1 for name in TARGETS} for n, c in cases.items()
    }
    verdict = {name: "PASS" if hot[name] <= limit else "HOLD" if hot[name] > HOLD else "INTERMEDIATE" for name, limit in TARGETS.items()}
    summary = {
        "schema": "reasonscript-reason-objects-benchmark/1.0",
        "baseline_commit_note": "baseline binary = main before the RUS/RUO projection",
        "head": bench.git("rev-parse", "HEAD"),
        "working_tree_dirty": dirty,
        "formal_evaluation": not dirty,
        "binaries": {label: {"file": path.name, "runtime_binary_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                     for label, path in (("baseline_r4", args.baseline_binary), ("projection", args.binary))},
        "compiler_version": subprocess.run(["rustc", "--version"], capture_output=True, text=True).stdout.strip(),
        "os": platform.platform(),
        "cpu_architecture": platform.machine(),
        "build_profile": "release",
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "warmup": args.warmup,
        "samples": args.samples,
        "hot_path_overhead_vs_r4": hot,
        "hot_path_reference_targets": TARGETS,
        "hot_path_verdict": verdict,
        "hold": any(v == "HOLD" for v in verdict.values()),
        "hot_path_per_case": per_case,
        "hot_path_regression_guard_projection_off_vs_baseline": {"aggregate_ratio": 1 + guard, "limit": 1.10, "ok": 1 + guard <= 1.10},
        "end_to_end_wall_overhead_vs_r4": end_to_end,
        "end_to_end_reference_target": END_TO_END_TARGET,
        "end_to_end_note": "whole host process wall time (startup, execution, projection, serialization, printing)",
        "cases": cases,
        "in_process": in_process(args.profile, args.profile_iterations) if args.profile else {},
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with (args.out / "comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["N", "transitions", "rus_states", "ruo_objects", "hot_r4", "hot_rus", "hot_rus_ruo", "wall_r4", "wall_rus", "wall_rus_ruo",
                         "rus_hot_overhead", "ruo_hot_overhead", "rus_wall_overhead", "ruo_wall_overhead"])
        for n, c in cases.items():
            h, w = c["hot_path_ns"], c["wall_ns"]
            writer.writerow([n, c["transitions"], c["rus_states"], c["ruo_objects"], h["r4"], h["rus"], h["rus_ruo"], w["r4"], w["rus"], w["rus_ruo"],
                             f"{h['rus'] / h['r4'] - 1:.4f}", f"{h['rus_ruo'] / h['r4'] - 1:.4f}",
                             f"{w['rus'] / w['r4'] - 1:.4f}", f"{w['rus_ruo'] / w['r4'] - 1:.4f}"])
    print(json.dumps({k: summary[k] for k in ("working_tree_dirty", "hot_path_overhead_vs_r4", "hot_path_verdict", "hold",
                                              "hot_path_regression_guard_projection_off_vs_baseline", "end_to_end_wall_overhead_vs_r4")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
