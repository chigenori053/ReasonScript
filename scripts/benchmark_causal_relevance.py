#!/usr/bin/env python3
"""Causal Relevance Filtering: does the relevant view pay for its own analysis?

Host boundary, `executable_reason_units=full`, `state_causality=full`,
`causal_evaluation=counterfactual` (native RUs), release build. Configurations:

* `r4`        no projection (the hot-path reference);
* `full`      `reason_objects=rus_ruo` (the Full RUO projection);
* `annotate`  `causal_relevance=annotate` (classification only);
* `relevant`  `causal_relevance=filter` with `reason_objects=off`: the relevant
              projection alone, including its own analysis;
* `both`      `reason_objects=rus_ruo` + `filter` (what `filter` emits when the
              full view is also requested).

Traces are trial-division factorizations of primes with `noise` unrelated
reasoning events (`RU_ACTIVATED`, no state effect) mixed in after every rejected
candidate. Net Projection Gain = the full projection's cost minus the relevant
projection's cost including the relevance analysis (both taken from the
runtime's own response-phase metrics, medians over the samples). The canonical
factorization has no noise at all, so `noise = 0` is the honest lower bound.

    scripts/benchmark_causal_relevance.py --binary <host> [--baseline-binary <host>]

A formal evaluation additionally needs `working_tree_dirty == false`.
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
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frontend.computation_ir import lower_program
from frontend.language_surface import parse
from scripts import benchmark_reasoning_state as bench

BASE = {"executable_reason_units": "full", "state_causality": "full", "causal_evaluation": "counterfactual", "causal_observation_source": "native"}
CONFIGS = {
    "r4": {},
    "full": {"reason_objects": "rus_ruo"},
    "annotate": {"causal_relevance": "annotate"},
    "relevant": {"causal_relevance": "filter"},
    "both": {"reason_objects": "rus_ruo", "causal_relevance": "filter"},
}
CASES = (997, 10007, 100003)  # primes: every candidate is rejected (search exclusions)
NOISE = (0, 1, 3, 9)  # unrelated events per rejected candidate
_programs: dict[tuple[int, int], dict] = {}


def program(n: int, noise: int) -> dict:
    if (n, noise) not in _programs:
        events = "".join(f'        reasoning.event("RU_ACTIVATED", candidate, "noise{i}")\n' for i in range(noise))
        source = bench.TEMPLATE.replace("__N__", str(n)).replace(
            '        reasoning.event("HYPOTHESIS_REJECTED", candidate, false)\n',
            '        reasoning.event("HYPOTHESIS_REJECTED", candidate, false)\n' + events)
        _programs[(n, noise)] = lower_program(parse(source))
    return _programs[(n, noise)]


def timed(binary: Path, n: int, noise: int, context: dict) -> tuple[dict, int, int]:
    request = json.dumps({
        "schema": "reasonscript-runtime-request/1.0", "request_id": "causal-relevance-benchmark", "operation": "execute",
        "program": program(n, noise),
        "context": {"resource_root": ".", "capabilities": {}, "limits": {"max_loop_iterations": 10_000_000},
                    "trace": {"enabled": False}, "numeric_mode": "compat-reference", "benchmark_metrics": True, **BASE, **context},
    })
    started = time.perf_counter_ns()
    completed = subprocess.run([str(binary)], input=request, text=True, capture_output=True)
    wall = time.perf_counter_ns() - started
    payload = json.loads(completed.stdout)
    assert payload["ok"], payload
    return payload["metadata"], wall, len(completed.stdout.encode())


def full_projection_ns(meta: dict) -> int:
    rus, ruo = meta["rus"]["metrics"], meta["ruo"]["metrics"]
    return rus["rus_materialization_ns"] + rus["rus_hash_ns"] + ruo["ruo_materialization_ns"] + ruo["ruo_hash_ns"]


def relevant_projection_ns(meta: dict) -> tuple[int, int]:
    metrics = meta["causal_relevance"]["metrics"]
    return metrics["causal_relevance_ns"], metrics["relevant_projection_ns"]


def measure(binary: Path, warmup: int, samples: int) -> dict:
    result: dict = {}
    for n in CASES:
        for noise in NOISE:
            key = f"{n}/noise{noise}"
            wall = {name: [] for name in CONFIGS}
            size = {name: 0 for name in CONFIGS}
            hot = {name: [] for name in CONFIGS}
            full_ns, analysis_ns, projection_ns = [], [], []
            info: dict = {}
            for sample in range(warmup + samples):
                for name, context in CONFIGS.items():
                    meta, wall_ns, nbytes = timed(binary, n, noise, context)
                    size[name] = nbytes
                    if sample < warmup:
                        continue
                    wall[name].append(wall_ns)
                    hot[name].append(meta["runtime_metrics"]["runtime_execution_ns"])
                    if name == "full":
                        full_ns.append(full_projection_ns(meta))
                    if name == "relevant":
                        analysis, projection = relevant_projection_ns(meta)
                        analysis_ns.append(analysis)
                        projection_ns.append(projection)
                        info = meta["causal_relevance"]["metrics"] | {"diagnostics": meta["causal_relevance"]["diagnostics"]}
            full_median = int(statistics.median(full_ns))
            relevant_median = int(statistics.median(analysis_ns)) + int(statistics.median(projection_ns))
            result[key] = {
                "n": n, "noise_per_candidate": noise,
                "ru_count": info["total_ru_count"], "noise_ru_count": info["noise_ru_count"],
                "reasoning_noise_reduction_ratio": info["reasoning_noise_reduction_ratio"],
                "essential_preservation_rate": info["essential_preservation_rate"],
                "relation_reduction_ratio": info["relation_reduction_ratio"],
                "diagnostics": info["diagnostics"],
                "wall_ns": {k: int(statistics.median(v)) for k, v in wall.items()},
                "hot_path_ns": {k: int(statistics.median(v)) for k, v in hot.items()},
                "response_bytes": size,
                "full_projection_ns": full_median,
                "relevance_analysis_ns": int(statistics.median(analysis_ns)),
                "relevant_projection_ns": int(statistics.median(projection_ns)),
                "relevant_total_ns": relevant_median,
                "net_projection_gain_ns": full_median - relevant_median,
                "net_projection_gain_ratio": (full_median - relevant_median) / full_median,
            }
    return result


def break_even(cases: dict, value) -> dict:
    """Noise ratio at which `value(case)` crosses zero (linear between measured points), per N."""
    result = {}
    for n in CASES:
        points = sorted((c["reasoning_noise_reduction_ratio"], value(c)) for c in cases.values() if c["n"] == n)
        crossing = None
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if y0 <= 0 < y1:
                crossing = x0 + (0 - y0) * (x1 - x0) / (y1 - y0)
                break
        result[str(n)] = crossing
    return result


def hot_path_guard(baseline: Path, binary: Path, warmup: int, samples: int) -> dict:
    """Relevance off: `runtime_execution_ns` against the build before this change."""
    hot = {"baseline": [], "current": []}
    for n in CASES:
        for sample in range(warmup + samples):
            for label, host in (("baseline", baseline), ("current", binary)):
                meta, _, _ = timed(host, n, 0, CONFIGS["full"])
                if sample >= warmup:
                    hot[label].append(meta["runtime_metrics"]["runtime_execution_ns"])
    ratio = sum(hot["current"]) / sum(hot["baseline"])
    return {"aggregate_ratio": ratio, "limit": 1.10, "ok": ratio <= 1.10}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--baseline-binary", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/causal_relevance")
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--samples", type=int, default=15)
    args = parser.parse_args()
    dirty = bool(bench.git("status", "--porcelain"))
    cases = measure(args.binary, args.warmup, args.samples)
    large = [c for c in cases.values() if c["noise_ru_count"] > 0 and c["ru_count"] >= 300]
    summary = {
        "schema": "reasonscript-causal-relevance-benchmark/1.0",
        "head": bench.git("rev-parse", "HEAD"),
        "working_tree_dirty": dirty,
        "formal_evaluation": not dirty,
        "runtime_binary_sha256": hashlib.sha256(args.binary.read_bytes()).hexdigest(),
        "compiler_version": subprocess.run(["rustc", "--version"], capture_output=True, text=True).stdout.strip(),
        "os": platform.platform(), "cpu_architecture": platform.machine(), "build_profile": "release",
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "warmup": args.warmup, "samples": args.samples,
        "essential_preservation_all_cases": all(c["essential_preservation_rate"] == 1.0 for c in cases.values()),
        "net_gain_positive_on_large_noisy_traces": bool(large) and all(c["net_projection_gain_ns"] > 0 for c in large),
        "net_gain_positive_when_noise_at_least_half": all(c["net_projection_gain_ns"] > 0 for c in cases.values() if c["reasoning_noise_reduction_ratio"] >= 0.5 and c["ru_count"] >= 300),
        "break_even_noise_ratio_projection": break_even(cases, lambda c: c["net_projection_gain_ns"]),
        "break_even_noise_ratio_wall": break_even(cases, lambda c: c["wall_ns"]["full"] - c["wall_ns"]["relevant"]),
        "hot_path_guard_relevance_off_vs_baseline": hot_path_guard(args.baseline_binary, args.binary, args.warmup, args.samples) if args.baseline_binary else None,
        "cases": cases,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with (args.out / "comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case", "ru_count", "noise_ru_count", "noise_ratio", "relation_reduction", "full_projection_ns", "analysis_ns",
                         "relevant_projection_ns", "net_gain_ns", "net_gain_ratio", "wall_full_ns", "wall_relevant_ns", "bytes_full", "bytes_relevant"])
        for key, c in cases.items():
            writer.writerow([key, c["ru_count"], c["noise_ru_count"], f"{c['reasoning_noise_reduction_ratio']:.4f}", f"{c['relation_reduction_ratio']:.4f}",
                             c["full_projection_ns"], c["relevance_analysis_ns"], c["relevant_projection_ns"], c["net_projection_gain_ns"],
                             f"{c['net_projection_gain_ratio']:.4f}", c["wall_ns"]["full"], c["wall_ns"]["relevant"],
                             c["response_bytes"]["full"], c["response_bytes"]["relevant"]])
    print(json.dumps({k: summary[k] for k in ("working_tree_dirty", "essential_preservation_all_cases", "net_gain_positive_on_large_noisy_traces",
                                              "net_gain_positive_when_noise_at_least_half", "break_even_noise_ratio_projection",
                                              "break_even_noise_ratio_wall", "hot_path_guard_relevance_off_vs_baseline")}, indent=2))
    for key, c in cases.items():
        print(f"{key:18s} ru={c['ru_count']:5d} noise={c['reasoning_noise_reduction_ratio']:.2f} "
              f"full={c['full_projection_ns'] / 1e6:8.2f}ms relevant={c['relevant_total_ns'] / 1e6:8.2f}ms "
              f"net={c['net_projection_gain_ns'] / 1e6:+8.2f}ms ({c['net_projection_gain_ratio']:+.0%}) "
              f"bytes {c['response_bytes']['full']}→{c['response_bytes']['relevant']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
